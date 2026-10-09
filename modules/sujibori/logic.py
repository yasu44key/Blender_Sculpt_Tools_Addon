"""Sujibori (panel lines): build the live Geometry Nodes groove and the Boolean cutters.

Lines are ordinary curve objects in a per-target collection. Both methods snap
the *centre line* to the surface first and only then give it thickness, so a
line drawn slightly off the surface still cuts, and the groove is never
flattened (the old Shrinkwrap-after-bevel problem).
"""

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from ...core import nodes

GN_MOD = "STS Sujibori"
BOOL_MOD = "STS Sujibori Boolean"


# ---------------------------------------------------------------- live (Geometry Nodes)

def build_node_group(name, solver):
    """Geometry -> minus (lines snapped to the surface, swept by a circle of Width)."""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    itf = ng.interface
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    itf.new_socket("Lines", in_out='INPUT', socket_type='NodeSocketCollection')
    width = itf.new_socket("Width", in_out='INPUT', socket_type='NodeSocketFloat')
    width.default_value = 0.01
    width.min_value = 0.0
    res = itf.new_socket("Resolution", in_out='INPUT', socket_type='NodeSocketInt')
    res.default_value = 8
    res.min_value = 3
    itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    n, link = ng.nodes, ng.links.new
    gin = n.new('NodeGroupInput')
    gout = n.new('NodeGroupOutput')
    info = n.new('GeometryNodeCollectionInfo')
    info.transform_space = 'RELATIVE'
    realize = n.new('GeometryNodeRealizeInstances')
    prox = n.new('GeometryNodeProximity')
    prox.target_element = 'FACES'
    snap = n.new('GeometryNodeSetPosition')
    half = n.new('ShaderNodeMath')
    half.operation = 'MULTIPLY'
    half.inputs[1].default_value = 0.5
    circle = n.new('GeometryNodeCurvePrimitiveCircle')
    sweep = n.new('GeometryNodeCurveToMesh')
    sweep.inputs["Fill Caps"].default_value = True
    cut = n.new('GeometryNodeMeshBoolean')
    cut.operation = 'DIFFERENCE'
    cut.solver = solver

    link(gin.outputs["Lines"], info.inputs["Collection"])
    link(info.outputs[0], realize.inputs[0])
    link(realize.outputs[0], snap.inputs["Geometry"])
    link(gin.outputs["Geometry"], prox.inputs["Geometry"])
    link(prox.outputs["Position"], snap.inputs["Position"])
    link(gin.outputs["Width"], half.inputs[0])
    link(half.outputs[0], circle.inputs["Radius"])
    link(gin.outputs["Resolution"], circle.inputs["Resolution"])
    link(snap.outputs[0], sweep.inputs["Curve"])
    link(circle.outputs["Curve"], sweep.inputs["Profile Curve"])
    link(gin.outputs["Geometry"], cut.inputs["Mesh 1"])
    link(sweep.outputs[0], cut.inputs["Mesh 2"])
    link(cut.outputs[0], gout.inputs[0])

    for i, node in enumerate((gin, info, realize, prox, snap, half, circle, sweep, cut, gout)):
        node.location = (i * 200, 0)
    return ng


def boolean_node(node_group):
    return next(nd for nd in node_group.nodes if nd.bl_idname == 'GeometryNodeMeshBoolean')


def push_live_inputs(mod, settings):
    ng = mod.node_group
    nodes.set_modifier_input(mod, nodes.socket_identifier(ng, "Lines"), settings.lines)
    nodes.set_modifier_input(mod, nodes.socket_identifier(ng, "Width"), settings.width)
    boolean_node(ng).solver = settings.solver


# ---------------------------------------------------------------- Boolean (cutter snapshot)

def is_set_up(target):
    return target.modifiers.get(GN_MOD) is not None or target.modifiers.get(BOOL_MOD) is not None


def make_line(curve_obj):
    """A line is a bare centre line: no bevel / extrude (Live reads it as a curve,
    and the groove width comes from the target's settings)."""
    curve_obj.data.bevel_depth = 0.0
    curve_obj.data.extrude = 0.0
    curve_obj.data.bevel_mode = 'ROUND'
    curve_obj.data.dimensions = '3D'
    curve_obj.hide_render = True


def line_curves(settings):
    if settings.lines is None:
        return []
    return [o for o in settings.lines.objects if o.type == 'CURVE']


def _surface_tree(target, context):
    """BVH of the target as it is *before* our Boolean (so cutters snap to the real surface)."""
    mod = target.modifiers.get(BOOL_MOD)
    was = mod.show_viewport if mod else None
    if mod:
        mod.show_viewport = False
    dg = context.evaluated_depsgraph_get()
    dg.update()
    tree = BVHTree.FromObject(target, dg)
    if mod:
        mod.show_viewport = was
    return tree


def _snap_curve_data(data, curve_mw, target_mw, tree):
    """Move every control point of `data` (a copy) onto the target surface."""
    to_target = target_mw.inverted() @ curve_mw
    back = to_target.inverted()

    def snapped(co_curve):
        co_t = to_target @ Vector(co_curve)
        hit = tree.find_nearest(co_t)
        if hit[0] is None:
            return Vector(co_curve)
        return back @ hit[0]

    for spline in data.splines:
        if spline.type == 'BEZIER':
            for p in spline.bezier_points:
                new = snapped(p.co)
                delta = new - p.co
                p.handle_left = p.handle_left + delta
                p.handle_right = p.handle_right + delta
                p.co = new
        else:
            for p in spline.points:
                new = snapped(p.co.xyz)
                p.co = (new.x, new.y, new.z, p.co.w)


def build_cutters(context, target, settings):
    """Rebuild one cutter mesh per line in settings.cutters. Returns the number built."""
    for o in list(settings.cutters.objects):
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.meshes.remove(data)
    tree = _surface_tree(target, context)
    built = 0
    for line in line_curves(settings):
        data = line.data.copy()
        _snap_curve_data(data, line.matrix_world, target.matrix_world, tree)
        data.bevel_mode = 'ROUND'
        data.bevel_depth = settings.width / 2.0
        data.bevel_resolution = 2
        data.use_fill_caps = True
        data.extrude = 0.0
        tmp = bpy.data.objects.new("_sts_tmp", data)
        tmp.matrix_world = line.matrix_world
        context.scene.collection.objects.link(tmp)
        dg = context.evaluated_depsgraph_get()
        dg.update()
        mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.curves.remove(data)
        if len(mesh.polygons) == 0:
            bpy.data.meshes.remove(mesh)
            continue
        cutter = bpy.data.objects.new("SujiboriCutter_" + line.name, mesh)
        cutter.matrix_world = line.matrix_world
        cutter.display_type = 'WIRE'
        cutter.hide_render = True
        settings.cutters.objects.link(cutter)
        built += 1
    return built


# ---------------------------------------------------------------- set up / switch method

def _collection(context, name):
    col = bpy.data.collections.new(name)
    context.scene.collection.children.link(col)
    return col


def _hide_collection(context, col):
    lc = _find_layer_collection(context.view_layer.layer_collection, col)
    if lc is not None:
        lc.hide_viewport = True
    col.hide_render = True


def _find_layer_collection(lc, col):
    if lc.collection == col:
        return lc
    for child in lc.children:
        found = _find_layer_collection(child, col)
        if found is not None:
            return found
    return None


def sync(context, target):
    """Make the target's modifiers match its settings (no duplicates)."""
    s = target.sts_sujibori
    if s.lines is None:
        s.lines = _collection(context, f"Sujibori Lines ({target.name})")
    if s.method == 'LIVE':
        bmod = target.modifiers.get(BOOL_MOD)
        if bmod:
            target.modifiers.remove(bmod)
        if s.cutters is not None:
            for o in list(s.cutters.objects):
                data = o.data
                bpy.data.objects.remove(o, do_unlink=True)
                if data is not None and data.users == 0:
                    bpy.data.meshes.remove(data)
        if s.node_group is None:
            s.node_group = build_node_group(f"STS Sujibori ({target.name})", s.solver)
        mod = target.modifiers.get(GN_MOD)
        if mod is None:
            mod = target.modifiers.new(GN_MOD, 'NODES')
        mod.node_group = s.node_group
        push_live_inputs(mod, s)
    else:
        gmod = target.modifiers.get(GN_MOD)
        if gmod:
            target.modifiers.remove(gmod)
        if s.cutters is None:
            s.cutters = _collection(context, f"Sujibori Cutters ({target.name})")
            _hide_collection(context, s.cutters)
        mod = target.modifiers.get(BOOL_MOD)
        if mod is None:
            mod = target.modifiers.new(BOOL_MOD, 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.operand_type = 'COLLECTION'
        mod.collection = s.cutters
        mod.solver = s.solver
        build_cutters(context, target, s)


def teardown(target):
    s = target.sts_sujibori
    for name in (GN_MOD, BOOL_MOD):
        mod = target.modifiers.get(name)
        if mod:
            target.modifiers.remove(mod)
    if s.cutters is not None:
        for o in list(s.cutters.objects):
            data = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)
        bpy.data.collections.remove(s.cutters)
        s.cutters = None
    ng, s.node_group = s.node_group, None      # the pointer itself counts as a user
    if ng is not None and ng.users == 0:
        bpy.data.node_groups.remove(ng)


def target_of_line(obj):
    """The target mesh whose line collection holds this curve, or None."""
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.sts_sujibori.lines is not None and obj.name in o.sts_sujibori.lines.objects:
            return o
    return None
