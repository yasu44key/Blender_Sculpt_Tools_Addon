"""Functional tests for modules/bezier_draw. Run through tests/run_tests.sh."""

import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, prefs, run, submodule  # noqa: E402


# ---------------------------------------------------------------- helpers

def make_curve(coords, name="TestCurve", cyclic=False, handle='AUTO', extra=None):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    for cs in [coords] + list(extra or []):
        sp = data.splines.new('BEZIER')
        sp.bezier_points.add(len(cs) - 1)
        sp.use_cyclic_u = cyclic
        for bp, co in zip(sp.bezier_points, cs):
            bp.handle_left_type = bp.handle_right_type = handle
            bp.co = co
            bp.handle_left = Vector(co) + Vector((-0.1, 0, 0))
            bp.handle_right = Vector(co) + Vector((0.1, 0, 0))
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def line(n, y=0.0, length=10.0):
    return [(length * i / (n - 1), y, 0.0) for i in range(n)]


def select_points(obj, spline_idx, indices):
    for si, sp in enumerate(obj.data.splines):
        for i, p in enumerate(sp.bezier_points):
            s = si == spline_idx and i in indices
            p.select_control_point = p.select_left_handle = p.select_right_handle = s


def coords(obj, si=0):
    return [p.co.copy() for p in obj.data.splines[si].bezier_points]


def min_pair_dist(cs):
    return min((a - b).length for i, a in enumerate(cs) for b in cs[i + 1:])


# ---------------------------------------------------------------- tests

def test_module_toggle():
    p = prefs()
    check("module registered by default", hasattr(bpy.types, "CURVE_OT_sts_spiral"))
    p.use_bezier_draw = False
    check("toggle off unregisters operators", not hasattr(bpy.types, "CURVE_OT_sts_spiral"))
    check("toggle off unregisters panels", not hasattr(bpy.types, "VIEW3D_PT_sts_bezier_draw"))
    check("toggle off removes scene property", not hasattr(bpy.types.Scene, "sts_bezier_draw"))
    p.use_bezier_draw = True
    check("toggle on registers again", hasattr(bpy.types, "CURVE_OT_sts_spiral"))


def test_draw_start_finish():
    ds = bpy.context.scene.sts_bezier_draw
    ds.bevel_depth = 0.25
    ds.mirror_x = True
    bpy.ops.curve.sts_draw_start()
    obj = bpy.context.object
    check("start: in curve edit mode", bpy.context.mode == 'EDIT_CURVE', bpy.context.mode)
    check("start: empty curve", len(obj.data.splines) == 0)
    check("start: thickness applied", abs(obj.data.bevel_depth - 0.25) < 1e-6)
    mod = obj.modifiers.get("STS Mirror")
    check("start: mirror modifier X", mod is not None and tuple(mod.use_axis) == (True, False, False))
    name = obj.name
    bpy.ops.curve.sts_draw_finish()
    check("finish: object mode", bpy.context.mode == 'OBJECT')
    check("finish: empty curve removed", name not in bpy.data.objects)


def test_finish_keeps_drawn_curve():
    bpy.ops.curve.sts_draw_start()
    obj = bpy.context.object
    sp = obj.data.splines.new('BEZIER')  # stands in for a drawn stroke
    sp.bezier_points.add(2)
    name = obj.name
    bpy.ops.curve.sts_draw_finish()
    check("finish: drawn curve kept", name in bpy.data.objects)
    check("finish: no duplicate objects", len(bpy.data.objects) == 1, str(len(bpy.data.objects)))


def test_spiral_flat_curve_object_mode():
    obj = make_curve(line(10), handle='FREE')
    r = bpy.ops.curve.sts_spiral(turns=0.75, r_min=1.0, r_max=1.0)  # 1.0 would put both ends together
    cs = coords(obj)
    check("spiral object mode runs", r == {'FINISHED'})
    check("spiral: flat curve does not collapse", min_pair_dist(cs) > 1e-3, f"{min_pair_dist(cs):.5f}")
    p = obj.data.splines[0].bezier_points[3]
    check("spiral: handles travel with points",
          abs((p.handle_right - p.co).length - 0.1) < 1e-4, f"{(p.handle_right - p.co).length:.4f}")
    center = Vector((5.0, 0.0))  # centroid of line(10)
    check("spiral: points on radius 1", all(abs((c.xy - center).length - 1.0) < 1e-4 for c in cs))


def test_spiral_edit_selected_only():
    obj = make_curve(line(10))
    before = coords(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    select_points(obj, 0, {3, 4, 5, 6})
    bpy.ops.curve.sts_spiral(turns=1.0, r_min=1.0, r_max=1.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    after = coords(obj)
    unchanged = all((before[i] - after[i]).length < 1e-6 for i in (0, 1, 2, 7, 8, 9))
    changed = any((before[i] - after[i]).length > 1e-3 for i in (3, 4, 5, 6))
    check("spiral edit: unselected points untouched", unchanged)
    check("spiral edit: selected points moved", changed)


def test_effect_without_selection_cancels():
    obj = make_curve(line(5))
    bpy.ops.object.mode_set(mode='EDIT')
    select_points(obj, 0, set())
    r = bpy.ops.curve.sts_radius_profile()
    check("edit mode, nothing selected -> CANCELLED", r == {'CANCELLED'}, str(r))


def test_radius_profile_and_twist():
    obj = make_curve(line(5))
    bpy.ops.curve.sts_radius_profile(mode='LINEAR', min_value=0.5, max_value=2.0)
    radii = [p.radius for p in obj.data.splines[0].bezier_points]
    check("radius profile linear ends", abs(radii[0] - 0.5) < 1e-6 and abs(radii[-1] - 2.0) < 1e-6,
          str(radii))
    bpy.ops.curve.sts_tilt_step(base_angle=0.0, angle_step=0.1)
    tilts = [p.tilt for p in obj.data.splines[0].bezier_points]
    check("twist steps", all(abs(t - 0.1 * i) < 1e-5 for i, t in enumerate(tilts)), str(tilts))


def test_smooth_handles_vector():
    obj = make_curve(line(5), handle='FREE')
    bpy.ops.curve.sts_smooth_handles(handle_mode='VECTOR')
    types = {p.handle_left_type for p in obj.data.splines[0].bezier_points}
    check("handles set to vector", types == {'VECTOR'}, str(types))


def test_decimate_selection_only_and_preserves_spline():
    obj = make_curve(line(50), extra=[line(50, y=2.0)], handle='FREE')
    obj.data.splines[1].use_cyclic_u = True
    bpy.ops.object.mode_set(mode='EDIT')
    select_points(obj, 0, set(range(10, 31)))
    r = bpy.ops.curve.sts_decimate(error=0.01)
    s0, s1 = obj.data.splines[0], obj.data.splines[1]
    check("decimate runs", r == {'FINISHED'}, str(r))
    check("decimate: selected run reduced to its ends", len(s0.bezier_points) == 31,
          str(len(s0.bezier_points)))
    check("decimate: other spline untouched", len(s1.bezier_points) == 50, str(len(s1.bezier_points)))
    check("decimate: cyclic kept", s1.use_cyclic_u)
    check("decimate: handle type kept", s1.bezier_points[5].handle_left_type == 'FREE')
    sel = [i for i, p in enumerate(s0.bezier_points) if p.select_control_point]
    check("decimate: remaining selection restored", sel == [10, 11], str(sel))

    select_points(obj, -1, set())
    bpy.ops.curve.sts_decimate(error=0.01)
    check("decimate without selection: whole curve",
          len(obj.data.splines[0].bezier_points) == 2, str(len(obj.data.splines[0].bezier_points)))
    check("decimate: still two splines", len(obj.data.splines) == 2)
    bpy.ops.object.mode_set(mode='OBJECT')


def test_rdp_long_stroke():
    cu = submodule("core.curve_utils")
    pts = [Vector((i * 0.001, math.sin(i * 0.01), 0)) for i in range(5000)]
    keep = cu.rdp_indices(pts, 0.0001)
    check("rdp handles 5000 points", keep[0] == 0 and keep[-1] == 4999 and len(keep) < 5000)


def test_subdivide_whole_curve():
    obj = make_curve(line(4))
    bpy.ops.object.mode_set(mode='EDIT')
    select_points(obj, 0, set())
    bpy.ops.curve.sts_subdivide(cuts=1)
    bpy.ops.object.mode_set(mode='OBJECT')
    check("subdivide whole curve 4 -> 7", len(obj.data.splines[0].bezier_points) == 7)


def test_points_to_metaballs():
    obj = make_curve(line(6))
    bpy.ops.curve.sts_points_to_metaballs('EXEC_DEFAULT')
    mb = bpy.context.object
    check("metaballs: one per point", mb.type == 'META' and len(mb.data.elements) == 6)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    select_points(obj, 0, {0, 1})
    bpy.ops.curve.sts_points_to_metaballs('EXEC_DEFAULT')
    mb2 = bpy.context.object
    check("metaballs from edit mode: selected only", len(mb2.data.elements) == 2)
    check("metaballs from edit mode: back in object mode", bpy.context.mode == 'OBJECT')


def test_generators():
    keep = make_curve(line(3), name="Spiral")   # must survive
    cases = [
        ("sts_spiral_add", {}, 1),
        ("sts_lissajous_add", {}, 1),
        ("sts_strand_add", {"mode": 'BRAID', "strands": 3}, 3),
        ("sts_strand_add", {"mode": 'DIAMOND', "strands": 3}, 4),
        ("sts_strand_add", {"mode": 'WIRE', "strands": 2, "tilt_track": True}, 2),
        ("sts_crossnet_add", {"strands_a": 4, "strands_b": 6}, 10),
        ("sts_lissajous_add", {"bevel_depth": 0.1, "tilt_mode": 'PROGRESSIVE'}, 1),
    ]
    for op, kw, n_splines in cases:
        bpy.ops.object.select_all(action='DESELECT')
        r = getattr(bpy.ops.curve, op)(**kw)
        obj = bpy.context.object
        check(f"{op} {kw}", r == {'FINISHED'} and obj.type == 'CURVE'
              and len(obj.data.splines) == n_splines, f"{r} {len(obj.data.splines)}")
    check("existing object named Spiral kept", keep.name in bpy.data.objects)
    check("bevel option applied", abs(bpy.context.object.data.bevel_depth - 0.1) < 1e-6)

    bpy.ops.object.select_all(action='DESELECT')
    guide = make_curve([(0, 0, 0), (2, 0, 1), (4, 0, 0)], name="Guide")
    bpy.ops.curve.sts_strand_add(guide_name="Guide", steps=32, length=99.0)
    obj = bpy.context.object
    end = obj.data.splines[0].bezier_points[-1].co
    check("strand follows guide curve", (end - Vector((4, 0, 0))).length < 1.0, str(end))


def test_connect_g1():
    a = make_curve([(0, 0, 0), (1, 0, 0), (2, 1, 0)], name="A", handle='FREE')
    pa = a.data.splines[0].bezier_points[-1]
    pa.handle_left, pa.handle_right = Vector((1.7, 0.6, 0)), Vector((2.3, 1.4, 0))   # outward along (1, 1.33)
    # B is moved and turned; its start is the end closest to A's end (its other end is far away)
    b = make_curve([(0, 0, 0), (0, -2, 0), (0, -4, 0)], name="B", handle='FREE')
    b.location = (2.2, 1.3, 0.0)
    b.rotation_euler = (0.0, 0.0, 0.6)
    bpy.context.view_layer.update()
    for o in bpy.context.selected_objects:
        o.select_set(False)
    a.select_set(True)
    b.select_set(True)
    bpy.context.view_layer.objects.active = a
    r = bpy.ops.curve.sts_connect_g1()
    check("G1: finished", r == {'FINISHED'}, str(r))
    bpy.context.view_layer.update()
    wa = a.matrix_world @ pa.co
    pb = b.data.splines[0].bezier_points[0]
    wb = b.matrix_world @ pb.co
    check("G1: the other curve's nearest end sits on the active end (world space)", (wa - wb).length < 1e-5,
          f"{wa} {wb}")
    out_a = ((a.matrix_world @ pa.handle_right) - wa).normalized()
    out_b = ((b.matrix_world @ pb.handle_left) - wb).normalized()
    in_b = ((b.matrix_world @ pb.handle_right) - wb).normalized()
    check("G1: handles line up (tangent continuity)", out_a.dot(out_b) < -0.9999 and out_a.dot(in_b) > 0.9999,
          f"{out_a.dot(out_b)} {out_a.dot(in_b)}")
    check("G1: the far end did not move", (b.data.splines[0].bezier_points[-1].co - Vector((0, -4, 0))).length < 1e-6)
    b.select_set(False)
    check("G1: only one curve -> CANCELLED", bpy.ops.curve.sts_connect_g1() == {'CANCELLED'})


run([
    test_module_toggle,
    test_draw_start_finish,
    test_finish_keeps_drawn_curve,
    test_spiral_flat_curve_object_mode,
    test_spiral_edit_selected_only,
    test_effect_without_selection_cancels,
    test_radius_profile_and_twist,
    test_smooth_handles_vector,
    test_decimate_selection_only_and_preserves_spline,
    test_rdp_long_stroke,
    test_subdivide_whole_curve,
    test_points_to_metaballs,
    test_generators,
    test_connect_g1,
])
