"""Spec for modules/panel_raise. Run through tests/run_tests.sh.

  mesh.sts_panel_raise — Edit Mode, selected faces. One click, adjustable with F9:

      surface ─┐ margin ┌──────────── panel top (surface + panel_height) ───┐
               └ groove ┘ (groove_width wide, groove_depth below the surface)

  1. inset by `margin` (skipped when 0)
  2. push the inner part down by `groove_depth` (walls, not slopes)
  3. inset by `groove_width` -> the groove floor
  4. lift the inner part to `panel_height` above the ORIGINAL surface
     (0 = flush, negative = recessed)
  5. bevel the panel top's border (`bevel_width` 0 = none)
  `individual`: each face its own panel (default) / the selection as one panel.
  Afterwards only the panel top faces are selected. Lengths are in object units.
"""

import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def edit_cube_top():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bm = bmesh.from_edit_mesh(o.data)
    for f in bm.faces:
        f.select_set(f.normal.z > 0.9)
    bmesh.update_edit_mesh(o.data)
    return o


def edit_two_quads():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=2, y_subdivisions=1, size=2.0)
    o = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='SELECT')
    return o


def bm_of(o):
    return bmesh.from_edit_mesh(o.data)


def heights(o):
    return sorted({round(v.co.z, 4) for v in bm_of(o).verts if v.co.z > 0.5})


def raise_(**kw):
    return bpy.ops.mesh.sts_panel_raise(**kw)


def test_registered():
    check("module listed in MODULES", "panel_raise" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.panel_raise").META["tabs"] == ("Model",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_panel_raise", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    P = bpy.ops.mesh.sts_panel_raise.get_rna_type().properties
    lengths = ("margin", "groove_width", "groove_depth", "panel_height", "bevel_width")
    check("length properties", all(k in P and P[k].unit == 'LENGTH' for k in lengths),
          str([k for k in lengths if k not in P]))
    check("defaults 0.05 / 0.03 / 0.02 / 0.01 / 0.01",
          [round(P[k].default, 4) for k in lengths] == [0.05, 0.03, 0.02, 0.01, 0.01])
    check("bevel_segments / individual", "bevel_segments" in P and P["individual"].default is True)
    check("undoable / F9", {'REGISTER', 'UNDO'} <= set(bpy.types.MESH_OT_sts_panel_raise.bl_options))
    check("no settings left on the Scene", not any("panel_raise" in k or "panel_tools" in k
                                                   for k in bpy.types.Scene.bl_rna.properties.keys()))


def test_cube_top_defaults():
    o = edit_cube_top()
    r = raise_()
    check("finished", r == {'FINISHED'}, str(r))
    bm = bm_of(o)
    check("still closed", all(len(e.link_faces) == 2 for e in bm.edges))
    hs = heights(o)
    check("surface 1.0, groove floor 0.98, panel top 1.01 present", {1.0, 0.98, 1.01} <= set(hs), str(hs))
    check("nothing above the panel top", max(hs) <= 1.01 + 1e-6, str(hs))
    sides = [f for f in bm.faces if abs(f.normal.z) < 0.1 and abs(f.calc_area() - 4.0) < 1e-6]
    check("the four sides are untouched", len(sides) == 4, str(len(sides)))
    sel = [f for f in bm.faces if f.select]
    check("only the panel top is selected",
          len(sel) == 1 and all(abs(v.co.z - 1.01) < 1e-6 for v in sel[0].verts) and sel[0].normal.z > 0.99,
          str(len(sel)))
    check("panel top size: 2 - 2·(margin + groove) - 2·bevel", abs(sel[0].calc_area() - 1.82 ** 2) < 2e-3,
          str(sel[0].calc_area()))


def test_without_bevel_exact():
    o = edit_cube_top()
    raise_(bevel_width=0.0)
    sel = [f for f in bm_of(o).faces if f.select]
    check("no bevel: panel top exactly 1.84 square", len(sel) == 1 and abs(sel[0].calc_area() - 1.84 ** 2) < 1e-5,
          str([f.calc_area() for f in sel]))
    check("no bevel: heights exactly 0.98 / 1.0 / 1.01", heights(o) == [0.98, 1.0, 1.01], str(heights(o)))


def test_recessed_and_flush():
    o = edit_cube_top()
    raise_(panel_height=-0.005, bevel_width=0.0)
    sel = [f for f in bm_of(o).faces if f.select]
    check("negative height: recessed panel", sel and all(abs(v.co.z - 0.995) < 1e-6 for v in sel[0].verts))
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.read_homefile(use_empty=True)
    o = edit_cube_top()
    raise_(panel_height=0.0, bevel_width=0.0)
    sel = [f for f in bm_of(o).faces if f.select]
    check("zero height: flush with the surface", sel and all(abs(v.co.z - 1.0) < 1e-6 for v in sel[0].verts))


def test_no_margin():
    o = edit_cube_top()
    raise_(margin=0.0, bevel_width=0.0)
    top_ring = [v for v in bm_of(o).verts if abs(v.co.z - 1.0) < 1e-6]
    check("margin 0: the groove starts right at the edge (only the 4 corners at the surface)", len(top_ring) == 4,
          str(len(top_ring)))
    check("margin 0: still closed", all(len(e.link_faces) == 2 for e in bm_of(o).edges))


def test_individual_vs_region():
    o = edit_two_quads()
    raise_(bevel_width=0.0)
    top = {(round(v.co.x, 4), round(v.co.y, 4)) for v in bm_of(o).verts if abs(v.co.z - 0.01) < 1e-6}
    check("individual: two separate panels (8 corners)", len(top) == 8, str(len(top)))
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.read_homefile(use_empty=True)
    o = edit_two_quads()
    raise_(bevel_width=0.0, individual=False)
    top = {(round(v.co.x, 4), round(v.co.y, 4)) for v in bm_of(o).verts if abs(v.co.z - 0.01) < 1e-6}
    check("one region: one panel over both faces (6 corners)", len(top) == 6, str(len(top)))
    check("one region: no loose edges left between the faces",
          all(e.link_faces for e in bm_of(o).edges))


def test_region_on_curved_faces():
    # caps on a curved selection do not share one normal: they must still be found
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0)
    o = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bm = bm_of(o)
    side = sorted((f for f in bm.faces if abs(f.normal.z) < 0.1),
                  key=lambda f: math.atan2(f.calc_center_median().y, f.calc_center_median().x))
    for f in bm.faces:
        f.select_set(f in side[:3])
    bmesh.update_edit_mesh(o.data)
    r = raise_(individual=False, bevel_width=0.0)
    bm = bm_of(o)
    sel = [f for f in bm.faces if f.select]
    check("region on curved faces: finished, three panel top faces selected", r == {'FINISHED'} and len(sel) == 3,
          f"{r} {len(sel)}")
    check("region on curved faces: still closed", all(len(e.link_faces) == 2 for e in bm.edges))


def test_refusals():
    o = edit_cube_top()
    bpy.ops.mesh.select_all(action='DESELECT')
    check("nothing selected -> CANCELLED", raise_() == {'CANCELLED'})
    bpy.ops.object.mode_set(mode='OBJECT')
    check("Object Mode: not available (poll)", not bpy.ops.mesh.sts_panel_raise.poll())


run([
    test_registered,
    test_cube_top_defaults,
    test_without_bevel_exact,
    test_recessed_and_flush,
    test_no_margin,
    test_individual_vs_region,
    test_region_on_curved_faces,
    test_refusals,
])
