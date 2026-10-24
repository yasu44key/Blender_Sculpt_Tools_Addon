"""Functional tests for modules/strip_draw (drawing itself: tests/gui/gui_strip_draw.py)."""

import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def S():
    return submodule("modules.strip_draw.strip")


def sphere():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
    return bpy.context.object


def stroke(reverse=False, name="Stroke", y=0.0):
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new('POLY')
    n = 30
    sp.points.add(n - 1)
    idx = list(range(n))[::-1] if reverse else list(range(n))
    for p, i in zip(sp.points, idx):
        a = -0.9 + 1.8 * i / (n - 1)
        v = Vector((math.sin(a), y, math.cos(a))).normalized()
        p.co = (*v, 1.0)
        p.radius = 1.0
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    return o


def select(active, *others):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in (active,) + others:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def band(o):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    verts = [o.matrix_world @ v.co for v in me.vertices]
    faces = len(me.polygons)
    edges = {}
    for p in me.polygons:
        for k in p.edge_keys:
            edges[k] = edges.get(k, 0) + 1
    open_edges = sum(1 for c in edges.values() if c == 1)
    ev.to_mesh_clear()
    return verts, faces, open_edges


def setup(**kw):
    s = bpy.context.scene.sts_strip_draw
    s.target = None
    for k, v in kw.items():
        setattr(s, k, v)
    t = sphere()
    c = stroke()
    select(t, c)
    return t, c


def test_registered():
    check("module listed in MODULES", "strip_draw" in sys.modules[package()].MODULES)
    check("META tabs is ('Sculpt',)", submodule("modules.strip_draw").META["tabs"] == ("Sculpt",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_strip_draw", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)
    P = bpy.context.scene.sts_strip_draw.bl_rna.properties
    check("settings: plain Blender units (no mm display)",
          all(P[k].unit == 'NONE' for k in ("width", "offset", "thickness", "voxel_size", "spacing")))
    d = {k: P[k].default for k in ("width", "offset", "thickness", "voxel_size", "spacing")}
    want = {"width": 5.0, "offset": 0.1, "thickness": 1.0, "voxel_size": 0.1, "spacing": 1.0}
    check("settings: defaults 5 / 0.1 / 1 / 0.1 / 1", all(abs(d[k] - want[k]) < 1e-6 for k in want), str(d))
    check("settings: styles", {i.identifier for i in P["style"].enum_items} == {'RIBBON', 'CLAY'})


def test_ribbon_lies_on_the_surface():
    t, c = setup(width=0.1, offset=0.01, thickness=0.0, style='RIBBON')
    r = bpy.ops.object.sts_strip_from_curves()
    check("from curves: finished, modifier with the target", r == {'FINISHED'} and S().get(c) is not None
          and S().get_input(S().get(c), "Target") is t)
    verts, faces, _open = band(c)
    rr = [v.length for v in verts]
    check("flat ribbon: on the surface + offset", verts and all(abs(x - 1.01) < 0.005 for x in rr), f"{min(rr)}..{max(rr)}")
    ys = [v.y for v in verts]
    check("ribbon: width across the stroke (y from -0.05 to 0.05)", abs(max(ys) - 0.05) < 0.003 and abs(min(ys) + 0.05) < 0.003,
          f"{min(ys)}..{max(ys)}")


def test_thick_band_outward_either_direction():
    for reverse in (False, True):
        bpy.ops.wm.read_homefile(use_empty=True)
        s = bpy.context.scene.sts_strip_draw
        s.target = None
        s.width, s.offset, s.thickness, s.style = 0.1, 0.0, 0.05, 'RIBBON'
        t = sphere()
        c = stroke(reverse=reverse)
        select(t, c)
        bpy.ops.object.sts_strip_from_curves()
        verts, faces, open_edges = band(c)
        rr = [v.length for v in verts]
        check(f"thick band (drawn {'backward' if reverse else 'forward'}): from the surface outward",
              min(rr) > 0.995 and max(rr) > 1.04 and max(rr) < 1.06, f"{min(rr)}..{max(rr)}")
        check(f"thick band ({'backward' if reverse else 'forward'}): a closed slab", open_edges == 0, str(open_edges))


def test_pressure_width():
    t, c = setup(width=0.1, offset=0.0, thickness=0.0)
    for i, p in enumerate(c.data.splines[0].points):
        p.radius = 0.2 if i < 15 else 1.0
    bpy.ops.object.sts_strip_from_curves()
    verts, _f, _o = band(c)
    narrow = [abs(v.y) for v in verts if v.x < -0.3]
    wide = [abs(v.y) for v in verts if v.x > 0.3]
    check("pen pressure (radius) scales the width", max(narrow) < 0.012 and max(wide) > 0.045,
          f"{max(narrow)} {max(wide)}")


def test_each_strip_keeps_its_own_values():
    t = sphere()
    s = bpy.context.scene.sts_strip_draw
    s.target = None
    s.width, s.thickness = 0.1, 0.0
    a = stroke(name="A", y=0.0)
    b = stroke(name="B", y=0.3)
    select(t, a, b)
    bpy.ops.object.sts_strip_from_curves()
    before = band(b)[0]
    S().set_input(S().get(a), "Width", 0.3)
    after = band(b)[0]
    check("changing one strip leaves the others alone (old armor rebuilt a shared group)",
          all((p - q).length < 1e-6 for p, q in zip(before, after)))
    check("the two strips share one node group", S().get(a).node_group is S().get(b).node_group)


def test_clay_and_to_mesh():
    t, c = setup(width=0.1, offset=0.0, thickness=0.03, style='CLAY', voxel_size=0.01)
    bpy.ops.object.sts_strip_from_curves()
    verts, faces, open_edges = band(c)
    check("clay: a closed remeshed lump", faces > 100 and open_edges == 0, f"{faces} {open_edges}")
    select(c)
    r = bpy.ops.object.sts_strip_to_mesh()
    o = bpy.context.active_object
    check("to mesh: a mesh object with the band", r == {'FINISHED'} and o.type == 'MESH' and len(o.data.polygons) > 100)


def test_start_finish():
    t = sphere()
    select(t)
    r = bpy.ops.curve.sts_strip_start()
    o = bpy.context.active_object
    check("start: a curve in Edit Mode with the strip modifier",
          r == {'FINISHED'} and o.type == 'CURVE' and bpy.context.mode == 'EDIT_CURVE' and S().get(o) is not None, str(r))
    check("start: the surface remembered", bpy.context.scene.sts_strip_draw.target is t)
    r = bpy.ops.curve.sts_strip_finish()
    check("finish with nothing drawn: back to Object Mode, empty strip removed",
          r == {'FINISHED'} and bpy.context.mode == 'OBJECT' and not [x for x in bpy.data.objects if x.type == 'CURVE'])
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.scene.sts_strip_draw.target = None
    bpy.ops.object.empty_add()
    check("start without a surface -> CANCELLED", bpy.ops.curve.sts_strip_start() == {'CANCELLED'})


def test_node_inputs_unitless_and_old_group_upgraded():
    t, c = setup(width=0.1)
    bpy.ops.object.sts_strip_from_curves()
    ng = S().get(c).node_group
    sub = {i.name: i.subtype for i in ng.interface.items_tree
           if getattr(i, "in_out", None) == 'INPUT' and i.socket_type == 'NodeSocketFloat'}
    check("node inputs: no Distance subtype", set(sub.values()) == {'NONE'}, str(sub))
    ng["sts_strip_version"] = 2                  # make it look like an old group
    S().set_input(S().get(c), "Width", 0.123)
    S().set_input(S().get(c), "Voxel Size", 0.0321)
    new = S().node_group()
    mod = S().get(c)
    check("old group: strips moved onto the current one, values kept",
          new is not ng and mod.node_group is new and new["sts_strip_version"] == S().VERSION
          and abs(S().get_input(mod, "Width") - 0.123) < 1e-6 and abs(S().get_input(mod, "Voxel Size") - 0.0321) < 1e-6
          and S().get_input(mod, "Target") is t)
    new["sts_strip_version"] = 3
    S().upgrade_old()
    check("upgrade_old (load / enable): moved again", S().get(c).node_group["sts_strip_version"] == S().VERSION)
    n = len(bpy.data.node_groups)
    S().upgrade_old()
    check("upgrade_old with nothing old: builds nothing", len(bpy.data.node_groups) == n)
    check("old group removed once unused",
          [g.get("sts_strip_version") for g in bpy.data.node_groups] == [S().VERSION])


def test_clay_voxel_size_is_used():
    t, c = setup(width=0.2, offset=0.0, thickness=0.05, style='CLAY', voxel_size=0.04)
    bpy.ops.object.sts_strip_from_curves()
    coarse = band(c)[1]
    S().set_input(S().get(c), "Voxel Size", 0.02)
    fine = band(c)[1]
    check("clay: a finer Voxel Size gives more faces (was ignored: voxel Amount)", fine > coarse * 2.5, f"{coarse} -> {fine}")
    S().set_input(S().get(c), "Voxel Size", 0.00001)
    guarded = band(c)[1]
    S().set_input(S().get(c), "Voxel Size", 0.2 / S().VOXELS_ACROSS)
    check("clay: never finer than Width / VOXELS_ACROSS (no freeze)", guarded == band(c)[1], f"{guarded}")


def test_target_follows_the_mesh_drawn_on():
    t = sphere()
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(8.0, 0.0, 0.0))
    decoy = bpy.context.object
    c = stroke()
    s = bpy.context.scene.sts_strip_draw
    s.target, s.width = decoy, 0.1
    select(c)
    bpy.ops.object.sts_strip_from_curves()
    mod = S().get(c)
    check("set up: target is the decoy", S().get_input(mod, "Target") is decoy)
    live = submodule("modules.strip_draw.live")
    found = live.even_last_stroke(bpy.context, c)
    check("the stroke tells the surface: Target -> the sphere", found is t and S().get_input(mod, "Target") is t
          and s.target is t, str(found))
    check("a Target already right is left alone", live.even_last_stroke(bpy.context, c) is None)


def test_point_functions():
    P = submodule("modules.strip_draw.points")
    line = [(Vector((x * 0.1, 0, 0)), 1.0 if x < 50 else 0.5, 0.0) for x in range(101)]   # 10 long, 101 points
    r = P.resample(line, 1.0)
    gaps = [(r[i + 1][0] - r[i][0]).length for i in range(len(r) - 1)]
    check("resample: 10 long at spacing 1 -> 11 evenly spaced points", len(r) == 11 and all(abs(g - 1.0) < 1e-5 for g in gaps),
          f"{len(r)} {gaps[:3]}")
    check("resample: ends kept", (r[0][0] - line[0][0]).length < 1e-6 and (r[-1][0] - line[-1][0]).length < 1e-6)
    check("resample: radius carried along", r[0][1] == 1.0 and r[-1][1] == 0.5)
    check("resample: spacing 0 keeps the points", P.resample(line, 0.0) is line)
    d = P.decimate(line, 2)
    check("decimate x2: 51 points, last kept", len(d) == 51 and d[-1] is line[-1], str(len(d)))
    d3 = P.decimate(line[:99], 3)                           # 0, 3 .. 96, then 98 added back
    check("decimate x3: the last point is added back", d3[-1] is line[98] and len(d3) == 34, str(len(d3)))
    sub = P.subdivide(line[:11], 2)
    check("subdivide 2 cuts: 10 segments -> 31 points", len(sub) == 31 and abs(sub[1][0].x - 0.1 / 3) < 1e-6, str(len(sub)))
    ring = [(Vector((x, y, 0)), 1.0, 0.0) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
    rr = P.resample(ring, 0.5, cyclic=True)
    check("resample a closed loop: 4 long -> 8 points, no duplicate start", len(rr) == 8, str(len(rr)))


def test_point_operators():
    t, c = setup(width=0.1)
    bpy.ops.object.sts_strip_from_curves()
    select(c)
    n0 = len(c.data.splines[0].points)                       # 30 points over ~1.8 of arc
    r = bpy.ops.curve.sts_strip_resample(spacing=0.3)
    n1 = len(c.data.splines[0].points)
    check("even spacing 0.3: ~6 segments", r == {'FINISHED'} and n1 == 7, f"{n0} -> {n1}")
    bpy.ops.curve.sts_strip_subdivide(cuts=1)
    check("subdivide: 7 -> 13", len(c.data.splines[0].points) == 13)
    bpy.ops.curve.sts_strip_decimate(keep_every=2)
    check("decimate: 13 -> 7", len(c.data.splines[0].points) == 7)
    check("still a strip with a band", S().get(c) is not None and band(c)[1] > 0)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.curve.select_all(action='DESELECT')
    r = bpy.ops.curve.sts_strip_subdivide(cuts=3)
    check("Edit Mode: works and stays in Edit Mode", r == {'FINISHED'} and bpy.context.mode == 'EDIT_CURVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    check("Edit Mode, nothing selected: all splines (7 -> 25)", len(c.data.splines[0].points) == 25)


def test_even_last_stroke_and_finish():
    t = sphere()
    select(t)
    bpy.context.scene.sts_strip_draw.spacing = 0.25
    bpy.ops.curve.sts_strip_start()
    o = bpy.context.active_object
    bpy.ops.object.mode_set(mode='OBJECT')
    first = o.data.splines.new('POLY')                  # an earlier stroke, already subdivided by hand
    first.points.add(9)
    for i, p in enumerate(first.points):
        p.co = (0.0, i * 0.01, 1.0, 1.0)
    sp = o.data.splines.new('POLY')                     # the newest stroke: dense pen samples
    sp.points.add(199)
    for i, p in enumerate(sp.points):
        p.co = (i * 0.01, 0.0, 1.0, 1.0)                # 1.99 long, 200 points
    tap = o.data.splines.new('POLY')
    tap.points[0].co = (0, 0, 1, 1)
    submodule("modules.strip_draw.live").even_last_stroke(bpy.context, o)
    n = [len(s.points) for s in o.data.splines]
    check("after a stroke: pen tap dropped, the newest stroke evened, earlier ones untouched", n == [10, 9], str(n))
    bpy.ops.object.mode_set(mode='EDIT')
    r = bpy.ops.curve.sts_strip_finish()
    n = [len(s.points) for s in o.data.splines]
    check("finish keeps the strokes as they are", r == {'FINISHED'} and n == [10, 9], str(n))


run([
    test_registered,
    test_ribbon_lies_on_the_surface,
    test_thick_band_outward_either_direction,
    test_pressure_width,
    test_each_strip_keeps_its_own_values,
    test_clay_and_to_mesh,
    test_start_finish,
    test_node_inputs_unitless_and_old_group_upgraded,
    test_point_functions,
    test_point_operators,
    test_clay_voxel_size_is_used,
    test_target_follows_the_mesh_drawn_on,
    test_even_last_stroke_and_finish,
])
