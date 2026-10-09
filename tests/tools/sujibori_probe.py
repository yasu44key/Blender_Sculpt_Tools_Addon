"""Sujibori design probe: GN live groove vs Boolean cutter (timing + groove depth)."""
import math
import sys
import time

import bpy
from mathutils import Vector

def P(*a):
    print("P", *a, flush=True)

P("version", bpy.app.version_string)
P("boolean node solvers", [i.identifier for i in bpy.types.GeometryNodeMeshBoolean.bl_rna.properties["solver"].enum_items])
P("boolean modifier solvers", [i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items])


def set_input(mod, identifier, value):
    """5.2: modifier.properties.inputs.<Socket_n>.value; 5.1: modifier["Socket_n"]."""
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props.inputs, identifier):
        getattr(props.inputs, identifier).value = value
    else:
        mod[identifier] = value


def build_group():
    ng = bpy.data.node_groups.new("STS Sujibori", 'GeometryNodeTree')
    itf = ng.interface
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    itf.new_socket("Lines", in_out='INPUT', socket_type='NodeSocketCollection')
    s = itf.new_socket("Width", in_out='INPUT', socket_type='NodeSocketFloat')
    s.default_value = 0.02
    s = itf.new_socket("Resolution", in_out='INPUT', socket_type='NodeSocketInt')
    s.default_value = 8
    itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    ci = N.new('GeometryNodeCollectionInfo')
    ci.transform_space = 'RELATIVE'
    real = N.new('GeometryNodeRealizeInstances')
    prox = N.new('GeometryNodeProximity')
    prox.target_element = 'FACES'
    setp = N.new('GeometryNodeSetPosition')
    circ = N.new('GeometryNodeCurvePrimitiveCircle')
    half = N.new('ShaderNodeMath'); half.operation = 'MULTIPLY'; half.inputs[1].default_value = 0.5
    c2m = N.new('GeometryNodeCurveToMesh')
    boo = N.new('GeometryNodeMeshBoolean'); boo.operation = 'DIFFERENCE'
    L.new(gi.outputs["Lines"], ci.inputs["Collection"])
    L.new(ci.outputs[0], real.inputs[0])
    L.new(real.outputs[0], setp.inputs["Geometry"])
    L.new(gi.outputs["Geometry"], prox.inputs[0])            # target
    L.new(prox.outputs["Position"], setp.inputs["Position"])
    L.new(gi.outputs["Width"], half.inputs[0])
    L.new(half.outputs[0], circ.inputs["Radius"])
    L.new(gi.outputs["Resolution"], circ.inputs["Resolution"])
    L.new(setp.outputs[0], c2m.inputs["Curve"])
    L.new(circ.outputs["Curve"], c2m.inputs["Profile Curve"])
    if "Fill Caps" in c2m.inputs:
        c2m.inputs["Fill Caps"].default_value = True
    L.new(gi.outputs["Geometry"], boo.inputs[0])
    L.new(c2m.outputs[0], boo.inputs[1])
    L.new(boo.outputs[0], go.inputs[0])
    return ng, boo


def scene(subdiv):
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
    tgt = bpy.context.object
    if subdiv:
        m = tgt.modifiers.new("S", 'SUBSURF'); m.levels = subdiv
        bpy.ops.object.modifier_apply(modifier="S")
    col = bpy.data.collections.new("Lines")
    bpy.context.scene.collection.children.link(col)
    # an equator-ish line slightly OFF the surface (as drawn), 3 lines
    for k, z in enumerate((-0.3, 0.0, 0.3)):
        cd = bpy.data.curves.new(f"L{k}", 'CURVE'); cd.dimensions = '3D'
        sp = cd.splines.new('BEZIER'); n = 16
        sp.bezier_points.add(n - 1); sp.use_cyclic_u = True
        r = math.sqrt(1 - z * z) * 1.05     # 5% outside the surface
        for i, bp in enumerate(sp.bezier_points):
            a = 2 * math.pi * i / n
            bp.co = (r * math.cos(a), r * math.sin(a), z * 1.05)
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        o = bpy.data.objects.new(f"L{k}", cd); col.objects.link(o)
    return tgt, col


def eval_time(obj, reps=3):
    ts = []
    for _ in range(reps):
        obj.data.update()                     # force re-evaluation
        t = time.perf_counter()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = obj.evaluated_get(dg)
        n = len(ev.data.polygons)
        ts.append(time.perf_counter() - t)
    return min(ts), n


def groove_depth(obj):
    """Smallest |v| among evaluated verts near the equator line -> groove bottom radius."""
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    near = [v.co.length for v in ev.data.vertices if abs(v.co.z) < 0.01]
    return min(near) if near else None


W = 0.04
for subdiv in (0, 2):
    for solver in ('EXACT', 'MANIFOLD', 'FLOAT'):
        tgt, col = scene(subdiv)
        base_faces = len(tgt.data.polygons)
        ng, boo = build_group()
        if solver not in [i.identifier for i in boo.bl_rna.properties["solver"].enum_items]:
            continue
        boo.solver = solver
        mod = tgt.modifiers.new("STS Sujibori", 'NODES'); mod.node_group = ng
        for item in ng.interface.items_tree:
            if getattr(item, "in_out", "") == 'INPUT' and item.name == "Lines":
                set_input(mod, item.identifier, col)
            if getattr(item, "in_out", "") == 'INPUT' and item.name == "Width":
                set_input(mod, item.identifier, W)
        t, n = eval_time(tgt)
        d = groove_depth(tgt)
        P(f"GN  subdiv={subdiv} faces={base_faces} solver={solver}: {t*1000:.0f} ms -> {n} faces, groove bottom r={d}")
        # live update: move one line
        line = col.objects[0]
        t0 = time.perf_counter()
        line.location.z += 0.05
        dg = bpy.context.evaluated_depsgraph_get(); dg.update()
        P(f"GN  subdiv={subdiv} solver={solver}: line moved -> re-eval {1000*(time.perf_counter()-t0):.0f} ms")

    # Boolean-modifier method (cutter = curve converted to mesh tube)
    for solver in ('EXACT', 'MANIFOLD', 'FLOAT'):
        tgt, col = scene(subdiv)
        if solver not in [i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items]:
            continue
        cutters = []
        for o in col.objects:
            o.data.bevel_depth = W / 2; o.data.use_fill_caps = True; o.data.bevel_resolution = 2
            me = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            c = bpy.data.objects.new(o.name + "_cut", me); c.matrix_world = o.matrix_world
            bpy.context.scene.collection.objects.link(c); cutters.append(c)
        cc = bpy.data.collections.new("Cutters"); bpy.context.scene.collection.children.link(cc)
        for c in cutters:
            bpy.context.scene.collection.objects.unlink(c); cc.objects.link(c)
        m = tgt.modifiers.new("B", 'BOOLEAN'); m.operation = 'DIFFERENCE'
        m.operand_type = 'COLLECTION'; m.collection = cc; m.solver = solver
        t, n = eval_time(tgt)
        d = groove_depth(tgt)
        P(f"BOOL subdiv={subdiv} solver={solver}: {t*1000:.0f} ms -> {n} faces, groove bottom r={d} (line drawn 5% outside: no cut expected)")
