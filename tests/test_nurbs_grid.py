"""Spec for modules/nurbs_grid (headless part). The mouse drawing is checked by
tests/gui/gui_nurbs_grid.py. Run through tests/run_tests.sh.

  Drawing (surface.sts_nurbs_grid_draw, modal): click points row by row, U points per
  row; Enter builds a NURBS surface from the full rows. The building is in
  modules/nurbs_grid/logic.py so it can be checked here:

    logic.build_grid(context, points, u_count, view_vector=None) -> Object | None
      points: list of (Vector co, float weight), row after row (U points each).
      Only full rows are used; fewer than 2 rows -> None (nothing created).
      Makes a SURFACE object "NURBS Grid" at the world origin (points are world
      coordinates) holding ONE NURBS spline of u x v points: co = (x, y, z, weight),
      use_endpoint_u / _v on, order_u = min(3, u), order_v = min(3, v).
      With view_vector (the direction the view looks in) the surface is turned to
      face the viewer (the old tool made them face away and needed Flip every time).
      The new object is the only selected one and active; Object Mode.

    logic.flip(obj) -> bool: reverse the V rows of every NURBS spline (normals flip),
      using spline.point_count_u (no custom property needed).

  Helpers: object.sts_nurbs_flip (selected surfaces), surface.sts_nurbs_cyclic
  (axis U / V, every spline of the active surface, stays in Object Mode),
  object.sts_nurbs_join (2+ selected surfaces -> one object, then Edit Mode).
  Settings: scene.sts_nurbs_grid.
"""

import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

DOWN = Vector((0, 0, -1))   # looking down from above


def logic():
    return submodule("modules.nurbs_grid.logic")


def grid_points(u=4, v=3, w=1.0, reverse_rows=False, z=0.0):
    rows = []
    for j in range(v):
        row = [(Vector((i * 1.0, j * 1.0, z + 0.2 * (i - (u - 1) / 2) ** 2)), w) for i in range(u)]
        rows.append(row[::-1] if reverse_rows else row)
    return [p for row in rows for p in row]


def mean_normal(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    n = Vector()
    for p in me.polygons:
        n += p.normal * p.area
    ev.to_mesh_clear()
    return n.normalized() if n.length else n


def test_registered():
    check("module listed in MODULES", "nurbs_grid" in sys.modules[package()].MODULES)
    check("META tabs is ('Curve',)", submodule("modules.nurbs_grid").META["tabs"] == ("Curve",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_nurbs_grid", None)
    check("panel in the Curve tab", p is not None and p.bl_category == submodule("core.tabs").CURVE)
    for op in ("surface.sts_nurbs_grid_draw", "object.sts_nurbs_flip", "surface.sts_nurbs_cyclic",
               "object.sts_nurbs_join"):
        mod, name = op.split(".")
        check(f"operator {op}", hasattr(getattr(bpy.ops, mod), name) and
              getattr(getattr(bpy.ops, mod), name).get_rna_type() is not None)
    S = bpy.types.Scene.bl_rna.properties.get("sts_nurbs_grid")
    check("settings on scene.sts_nurbs_grid", S is not None)
    s = bpy.context.scene.sts_nurbs_grid
    P = s.bl_rna.properties
    check("u_count default 4 (2..100)", P["u_count"].default == 4 and P["u_count"].hard_min == 2)
    check("use_drag default on, drag_interval is a length",
          P["use_drag"].default is True and P["drag_interval"].unit == 'LENGTH')
    check("snap NONE / VERTEX / FACE / GRID",
          {i.identifier for i in P["snap"].enum_items} == {'NONE', 'VERTEX', 'FACE', 'GRID'})
    check("snap_nurbs_only, weight (default 1.0)", "snap_nurbs_only" in P and abs(P["weight"].default - 1.0) < 1e-9)
    check("no old scene properties", not any(k.startswith("nurbs_grid_") for k in bpy.types.Scene.bl_rna.properties.keys()))


def test_build_grid():
    pts = grid_points(u=4, v=3, w=1.0)
    pts[5] = (pts[5][0], 2.5)                       # one heavier point
    o = logic().build_grid(bpy.context, pts, 4, view_vector=DOWN)
    check("build: object made", o is not None and o.type == 'SURFACE')
    if o is None:
        return
    sp = o.data.splines
    check("build: one NURBS spline, 4 x 3", len(sp) == 1 and sp[0].type == 'NURBS' and
          sp[0].point_count_u == 4 and sp[0].point_count_v == 3, f"{len(sp)}")
    s = sp[0]
    check("build: endpoints and orders 3 / 3", s.use_endpoint_u and s.use_endpoint_v and
          s.order_u == 3 and s.order_v == 3)
    have = sorted((round(p.co[0], 5), round(p.co[1], 5), round(p.co[2], 5), round(p.co[3], 5)) for p in s.points)
    want = sorted((round(c.x, 5), round(c.y, 5), round(c.z, 5), round(w, 5)) for c, w in pts)
    check("build: control points at the clicked places, with their weights", have == want)
    check("build: at the world origin, named NURBS Grid",
          o.matrix_world.translation.length < 1e-9 and o.name.startswith("NURBS Grid"))
    check("build: only it selected, active, Object Mode",
          bpy.context.selected_objects == [o] and bpy.context.view_layer.objects.active is o
          and bpy.context.mode == 'OBJECT')


def test_partial_row_and_too_few():
    pts = grid_points(u=4, v=3) + [(Vector((9, 9, 9)), 1.0), (Vector((8, 8, 8)), 1.0)]
    o = logic().build_grid(bpy.context, pts, 4, view_vector=DOWN)
    check("partial last row dropped", o is not None and len(o.data.splines[0].points) == 12)
    bpy.ops.wm.read_homefile(use_empty=True)
    o = logic().build_grid(bpy.context, grid_points(u=4, v=1) + [(Vector((0, 5, 0)), 1.0)], 4)
    check("fewer than 2 rows -> None, nothing made", o is None and not bpy.data.objects)


def test_two_by_two_orders():
    o = logic().build_grid(bpy.context, grid_points(u=2, v=2), 2, view_vector=DOWN)
    s = o.data.splines[0]
    check("2 x 2: orders 2 / 2", s.order_u == 2 and s.order_v == 2)


def test_faces_the_viewer():
    a = logic().build_grid(bpy.context, grid_points(), 4, view_vector=DOWN)
    check("seen from above: normal up", mean_normal(a).z > 0.9, str(mean_normal(a)))
    b = logic().build_grid(bpy.context, grid_points(reverse_rows=True), 4, view_vector=DOWN)
    check("rows drawn the other way: still up", mean_normal(b).z > 0.9, str(mean_normal(b)))
    c = logic().build_grid(bpy.context, grid_points(), 4, view_vector=Vector((0, 0, 1)))
    check("seen from below: normal down", mean_normal(c).z < -0.9, str(mean_normal(c)))


def test_flip():
    a = logic().build_grid(bpy.context, grid_points(), 4, view_vector=DOWN)
    b = logic().build_grid(bpy.context, grid_points(z=3.0), 4, view_vector=DOWN)
    a.select_set(True)
    r = bpy.ops.object.sts_nurbs_flip()
    check("flip: finished", r == {'FINISHED'}, str(r))
    check("flip: both selected surfaces now face down", mean_normal(a).z < -0.9 and mean_normal(b).z < -0.9)
    check("flip: logic.flip on a 4 x 3 grid", logic().flip(a) is True and mean_normal(a).z > 0.9)
    bpy.ops.object.select_all(action='DESELECT')
    check("flip: nothing selected -> CANCELLED", bpy.ops.object.sts_nurbs_flip() == {'CANCELLED'})


def test_cyclic():
    o = logic().build_grid(bpy.context, grid_points(u=5, v=4), 5, view_vector=DOWN)
    r = bpy.ops.surface.sts_nurbs_cyclic(axis='U')
    check("cyclic U: finished, still Object Mode", r == {'FINISHED'} and bpy.context.mode == 'OBJECT', str(r))
    check("cyclic U on, V off", o.data.splines[0].use_cyclic_u and not o.data.splines[0].use_cyclic_v)
    bpy.ops.surface.sts_nurbs_cyclic(axis='V')
    bpy.ops.surface.sts_nurbs_cyclic(axis='U')
    check("toggles: U off, V on", not o.data.splines[0].use_cyclic_u and o.data.splines[0].use_cyclic_v)
    bpy.ops.mesh.primitive_cube_add()
    check("cyclic: not for a mesh (poll)", not bpy.ops.surface.sts_nurbs_cyclic.poll())


def test_join():
    a = logic().build_grid(bpy.context, grid_points(), 4, view_vector=DOWN)
    b = logic().build_grid(bpy.context, grid_points(z=3.0), 4, view_vector=DOWN)
    a.select_set(True)
    r = bpy.ops.object.sts_nurbs_join()
    surfaces = [o for o in bpy.data.objects if o.type == 'SURFACE' and o.users_scene]
    check("join: finished, one object with two splines, Edit Mode",
          r == {'FINISHED'} and len(surfaces) == 1 and len(surfaces[0].data.splines) == 2
          and bpy.context.mode == 'EDIT_SURFACE', f"{r} {len(surfaces)} {bpy.context.mode}")
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    surfaces[0].select_set(True)
    check("join: one surface -> CANCELLED", bpy.ops.object.sts_nurbs_join() == {'CANCELLED'})


run([
    test_registered,
    test_build_grid,
    test_partial_row_and_too_few,
    test_two_by_two_orders,
    test_faces_the_viewer,
    test_flip,
    test_cyclic,
    test_join,
])
