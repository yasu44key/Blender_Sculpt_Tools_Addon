"""Spec for modules/annotation_convert. Run through tests/run_tests.sh.

  curve.sts_annotation_convert — Object Mode. Turns the scene's annotation strokes
  (the frame shown at the current frame) into one new object at the world origin:
    target 'BEZIER': a 3D curve, one Bezier spline per stroke. Points thinned with
                     Ramer-Douglas-Peucker (`simplify`, a length; 0 = keep all),
                     smooth (FREE, Catmull-Rom-like) handles, VECTOR handles where the
                     stroke turns sharper than `corner_angle`.
    target 'MESH':   vertices + edges along each stroke (no faces: F fills).
  layers 'ACTIVE' (layers.active_index) or 'VISIBLE' (every layer not hidden).
  Strokes with fewer than 2 points are skipped. `hide_after` hides the converted
  layers. The new object is the only selected one and is active.

The fixture tests/data/annotation.blend (made in 5.2: Python can add annotation
strokes only from 5.2 on) holds:
  layer 0 "Other"  : one 2-point stroke at y = -2
  layer 1 "Notes"  : ACTIVE — an L (41 points, (0,0,0) -> (1,0,0) -> (1,1,0), sharp corner),
                     a half circle (41 points, centre (3,0,0.5), radius 1), a 1-point dot
  layer 2 "Hidden" : hidden, one 2-point stroke
"""

import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "data", "annotation.blend")
CENTRE = Vector((3.0, 0.0, 0.5))


def load():
    bpy.ops.wm.open_mainfile(filepath=FIXTURE)
    return bpy.context.scene.annotation


def convert(**kw):
    return bpy.ops.curve.sts_annotation_convert(**kw)


def new_objects():
    return [o for o in bpy.context.scene.objects]


def spline_points(sp):
    return [bp.co.copy() for bp in sp.bezier_points]


def test_registered():
    check("module listed in MODULES", "annotation_convert" in sys.modules[package()].MODULES)
    check("META tabs is ('Curve',)", submodule("modules.annotation_convert").META["tabs"] == ("Curve",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_annotation_convert", None)
    check("panel in the Curve tab", p is not None and p.bl_category == submodule("core.tabs").CURVE)
    P = bpy.ops.curve.sts_annotation_convert.get_rna_type().properties
    check("target BEZIER / MESH", {i.identifier for i in P["target"].enum_items} == {'BEZIER', 'MESH'})
    check("layers ACTIVE / VISIBLE", {i.identifier for i in P["layers"].enum_items} == {'ACTIVE', 'VISIBLE'})
    check("simplify is a length", P["simplify"].unit == 'LENGTH')
    check("corner_angle is an angle (60°)",
          P["corner_angle"].subtype == 'ANGLE' and abs(P["corner_angle"].default - math.radians(60)) < 1e-6)
    check("hide_after default on", P["hide_after"].default is True)
    check("undoable / F9", {'REGISTER', 'UNDO'} <= set(bpy.types.CURVE_OT_sts_annotation_convert.bl_options))
    check("fixture present", os.path.exists(FIXTURE))


def test_bezier_active_layer():
    ann = load()
    r = convert(target='BEZIER')
    check("bezier: finished", r == {'FINISHED'}, str(r))
    objs = [o for o in bpy.context.scene.objects if o.type == 'CURVE']
    check("bezier: one new curve object", len(objs) == 1)
    o = objs[0]
    check("bezier: only it is selected, and active",
          bpy.context.selected_objects == [o] and bpy.context.view_layer.objects.active is o)
    check("bezier: at the origin, 3D", o.matrix_world.translation.length < 1e-9 and o.data.dimensions == '3D')
    sps = o.data.splines
    check("bezier: the active layer's two lines (not the first layer, dot skipped)", len(sps) == 2,
          str(len(sps)))
    if len(sps) != 2:
        return
    lsp, arc = (sps[0], sps[1]) if len(sps[0].bezier_points) <= len(sps[1].bezier_points) else (sps[1], sps[0])
    lp = spline_points(lsp)
    check("bezier: L thinned to start / corner / end", len(lp) == 3, str(len(lp)))
    check("bezier: L ends in world coordinates",
          (lp[0] - Vector((0, 0, 0))).length < 1e-5 and (lp[-1] - Vector((1, 1, 0))).length < 1e-5)
    mid = lsp.bezier_points[1]
    check("bezier: sharp corner gets VECTOR handles", mid.handle_left_type == 'VECTOR' and
          mid.handle_right_type == 'VECTOR')
    ap = spline_points(arc)
    check("bezier: arc thinned (5..20 points)", 5 <= len(ap) <= 20, str(len(ap)))
    check("bezier: arc points stay on the circle", all(abs((p - CENTRE).length - 1.0) < 1e-4 for p in ap))
    inner = arc.bezier_points[len(ap) // 2]
    check("bezier: smooth points are not VECTOR", inner.handle_left_type != 'VECTOR')
    check("bezier: converted layer hidden", ann.layers[1].annotation_hide and not ann.layers[0].annotation_hide)


def test_curve_follows_the_stroke():
    load()
    convert(target='BEZIER', simplify=0.02)
    o = next(o for o in bpy.context.scene.objects if o.type == 'CURVE')
    me = o.to_mesh()
    far = max(abs((v.co - CENTRE).length - 1.0) for v in me.vertices if v.co.x > 1.5)
    o.to_mesh_clear()
    check("bezier: the evaluated arc stays within the simplify distance of the circle", far < 0.03, str(far))


def test_simplify_zero_keeps_all():
    load()
    convert(target='BEZIER', simplify=0.0)
    o = next(o for o in bpy.context.scene.objects if o.type == 'CURVE')
    check("simplify 0: every point kept", sorted(len(s.bezier_points) for s in o.data.splines) == [41, 41])


def test_mesh():
    load()
    r = convert(target='MESH', simplify=0.0, hide_after=False)
    check("mesh: finished", r == {'FINISHED'}, str(r))
    o = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    me = o.data
    check("mesh: vertices and edges along the strokes (no faces)",
          len(me.vertices) == 82 and len(me.edges) == 80 and len(me.polygons) == 0,
          f"{len(me.vertices)} / {len(me.edges)} / {len(me.polygons)}")
    check("mesh: only it is selected, active, Object Mode",
          bpy.context.selected_objects == [o] and bpy.context.view_layer.objects.active is o
          and bpy.context.mode == 'OBJECT')
    check("mesh: hide_after off keeps the layer visible", not bpy.context.scene.annotation.layers[1].annotation_hide)
    load()
    convert(target='MESH', simplify=0.02)
    o = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    check("mesh: thinned too", 3 + 5 <= len(o.data.vertices) <= 3 + 20, str(len(o.data.vertices)))


def test_visible_layers():
    ann = load()
    convert(target='BEZIER', layers='VISIBLE')
    o = next(o for o in bpy.context.scene.objects if o.type == 'CURVE')
    check("visible: all shown layers (Other + Notes), not the hidden one", len(o.data.splines) == 3,
          str(len(o.data.splines)))
    check("visible: converted layers hidden", ann.layers[0].annotation_hide and ann.layers[1].annotation_hide)


def test_long_stroke():
    # a zig-zag of 5000 points: the recursive thinning hit Python's recursion limit
    ann = load()
    fr = ann.layers[1].frames[0]
    if not hasattr(fr.strokes, "new"):       # 5.1 cannot add strokes from Python
        check("long stroke (5.2 only)", True)
        return
    st = fr.strokes.new()
    st.points.add(5000)
    for i, p in enumerate(st.points):
        p.co = (i * 0.001, 0.0005 * (i % 2), 0.0)
    r = convert(target='MESH', simplify=0.0001)
    check("long stroke: converted without error", r == {'FINISHED'}, str(r))


def test_refusals():
    bpy.ops.wm.read_homefile(use_empty=True)
    r = convert()
    check("no annotation -> CANCELLED", r == {'CANCELLED'} and not bpy.context.scene.objects, str(r))
    ann = load()
    ann.layers.active_index = 2
    ann.layers[2].frames.remove(ann.layers[2].frames[0])
    r = convert()
    check("active layer without strokes -> CANCELLED, no object", r == {'CANCELLED'} and
          not [o for o in bpy.context.scene.objects if o.type in {'CURVE', 'MESH'}], str(r))
    load()
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.object.mode_set(mode='EDIT')
    check("Edit Mode: not available (poll)", not bpy.ops.curve.sts_annotation_convert.poll())


run([
    test_registered,
    test_bezier_active_layer,
    test_curve_follows_the_stroke,
    test_simplify_zero_keeps_all,
    test_mesh,
    test_visible_layers,
    test_long_stroke,
    test_refusals,
])
