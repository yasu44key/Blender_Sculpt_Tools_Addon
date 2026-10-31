"""Functional tests for modules/object_brush. Run through tests/run_tests.sh.

logic.py (GUI-free):
  grid_snap_xy(co, size) -> Vector            (X and Y on the grid, Z unchanged)
  instance_rotation(normal, stroke_dir, align_to_normal, align_to_stroke, spin) -> Quaternion
  depth_fallback(origin, direction, last_depth, cursor) -> Vector
  place_instance(context, source, location, rotation, scale, collection) -> Object
  nearest_chain(points, start) -> [index]    (nearest-neighbour walk)
  centers_curve(points, collection, smooth, bevel_depth, cyclic) -> Object or None
  link_beads / line_beads / find_line / set_follow(context, line, 'NONE'|'OBJECTS'|'CURVE')
  StrokeHistory: begin() / add(obj) / current() / end() / undo(collection) / redo(collection) / purge()
    (undone copies that can no longer be redone are deleted, never left as orphans)
The modal brush itself is checked by tests/gui/gui_object_brush.py.
"""

import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def logic():
    return submodule("modules.object_brush.logic")


def near(a, b, eps=1e-4):
    return (Vector(a) - Vector(b)).length < eps


def z_axis(q):
    return q @ Vector((0, 0, 1))


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "object_brush" in sys.modules[package()].MODULES)
    check("META tabs is ('Sculpt',)", submodule("modules.object_brush").META["tabs"] == ("Sculpt",))
    op = getattr(bpy.types, "OBJECT_OT_sts_object_brush", None)
    check("operator registered", op is not None and op.bl_idname == "object.sts_object_brush")
    p = getattr(bpy.types, "VIEW3D_PT_sts_object_brush", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)
    pkg = package() + ".modules.object_brush"
    ops = [c.bl_idname for c in bpy.types.Operator.__subclasses__() if c.__module__.startswith(pkg)]
    check("brush / connect-selected / follow operators only (the source picker has an eyedropper)",
          sorted(ops) == ["object.sts_connect_selected", "object.sts_line_follow", "object.sts_object_brush"],
          str(ops))
    check("old tab 'Tool' not used", p is not None and p.bl_category != "Tool")


def test_settings():
    s = getattr(bpy.context.scene, "sts_object_brush", None)
    check("settings on Scene.sts_object_brush", s is not None)
    if s is None:
        return
    P = s.bl_rna.properties
    check("source OBJECT / COLLECTION", {i.identifier for i in P["source"].enum_items} == {'OBJECT', 'COLLECTION'})
    check("brush_mode STROKE / GRID", {i.identifier for i in P["brush_mode"].enum_items} == {'STROKE', 'GRID'})
    check("random_rotation is an angle", P["random_rotation"].subtype == 'ANGLE')
    for name in ("spacing", "grid_size", "jitter_x", "jitter_y", "jitter_z"):
        check(f"{name} is a length", P[name].unit == 'LENGTH', P[name].unit)
    for name in ("brush_object", "brush_collection", "use_output_collection", "target_collection",
                 "new_collection_name", "base_scale", "use_pressure", "align_to_normal",
                 "align_to_stroke", "jitter_scale", "connect_centers", "line_smooth",
                 "line_cyclic", "line_thickness"):
        check(f"setting {name}", name in P)


# ---------------------------------------------------------------- logic

def test_grid_snap_xy():
    f = logic().grid_snap_xy
    check("X and Y snap, Z kept", near(f(Vector((1.26, -0.74, 0.333)), 0.5), (1.5, -0.5, 0.333)),
          str(f(Vector((1.26, -0.74, 0.333)), 0.5)))
    check("size 1", near(f(Vector((2.4, 2.6, -1.7)), 1.0), (2.0, 3.0, -1.7)))


def test_instance_rotation_spin_around_normal():
    f = logic().instance_rotation
    n = Vector((1.0, 0.0, 1.0)).normalized()          # a 45 degree slope
    for spin in (0.0, 0.7, math.pi / 2, -2.0):
        q = f(n, Vector((0, 1, 0)), True, False, spin)
        check(f"spin {spin:.2f}: up axis stays on the normal", near(z_axis(q), n), str(z_axis(q)))
    q0 = f(n, Vector((0, 1, 0)), True, False, 0.0)
    q1 = f(n, Vector((0, 1, 0)), True, False, math.pi / 2)
    x0, x1 = q0 @ Vector((1, 0, 0)), q1 @ Vector((1, 0, 0))
    check("spin turns the object around the normal (90 deg)", abs(x0.dot(x1)) < 1e-4, f"{x0} {x1}")


def test_instance_rotation_options():
    f = logic().instance_rotation
    n = Vector((0.0, 1.0, 0.0))
    q = f(n, Vector((1, 0, 0)), False, False, 0.0)
    check("align_to_normal off -> world up", near(z_axis(q), (0, 0, 1)), str(z_axis(q)))
    q = f(Vector((0, 0, 1)), Vector((1, 0, 0)), True, True, 0.0)
    check("align_to_stroke: Y axis follows the stroke", near(q @ Vector((0, 1, 0)), (1, 0, 0)),
          str(q @ Vector((0, 1, 0))))


def test_depth_fallback():
    f = logic().depth_fallback
    p = f(Vector((0, 0, 10)), Vector((0, 0, -1)), 4.0, Vector((0, 0, 0)))
    check("keeps the last depth", near(p, (0, 0, 6)), str(p))
    p = f(Vector((0, 0, 10)), Vector((0, 0, -1)), None, Vector((5, 5, 3)))
    check("no last depth -> 3D cursor distance", near(p, (0, 0, 10 - (Vector((5, 5, 3)) - Vector((0, 0, 10))).length)),
          str(p))


def test_place_instance_ignores_parent():
    bpy.ops.object.empty_add(location=(10, 0, 0))
    parent = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(size=0.5, location=(11, 0, 0))
    src = bpy.context.object
    src.parent = parent
    src.matrix_parent_inverse = parent.matrix_world.inverted()
    col = bpy.data.collections.new("Out")
    bpy.context.scene.collection.children.link(col)
    obj = logic().place_instance(bpy.context, src, Vector((1, 2, 3)), Quaternion(), 2.0, col)
    bpy.context.view_layer.update()
    check("instance at the requested world position", near(obj.matrix_world.translation, (1, 2, 3)),
          str(obj.matrix_world.translation))
    check("instance has no parent", obj.parent is None)
    check("instance shares the mesh data", obj.data is src.data)
    check("instance linked to the output collection", obj.name in col.objects)
    check("scale applied (source scale x 2)", near(obj.scale, (2, 2, 2)), str(obj.scale))


def test_stroke_history():
    col = bpy.data.collections.new("Out")
    bpy.context.scene.collection.children.link(col)
    bpy.ops.mesh.primitive_cube_add()
    src = bpy.context.object
    L = logic()
    h = L.StrokeHistory()
    objs = []
    for stroke in range(2):
        h.begin()
        for i in range(3):
            o = L.place_instance(bpy.context, src, Vector((stroke, i, 0)), Quaternion(), 1.0, col)
            h.add(o)
            objs.append(o)
        h.end()
    check("6 instances placed", len(col.objects) == 6)
    check("undo removes the last stroke", h.undo(col) is True and len(col.objects) == 3)
    check("redo brings it back", h.redo(col) is True and len(col.objects) == 6)
    h.undo(col)
    names = [o.name for o in objs[3:]]
    h.purge()
    check("purge deletes undone instances for good", not [n for n in names if n in bpy.data.objects])
    check("purge keeps the rest", len(col.objects) == 3)
    # undo, then a new stroke: the undone copies can never come back -> deleted at once
    h.begin()
    o = L.place_instance(bpy.context, src, Vector((5, 5, 0)), Quaternion(), 1.0, col)
    h.add(o)
    h.end()
    h.undo(col)
    gone = o.name
    h.begin()
    h.add(L.place_instance(bpy.context, src, Vector((6, 6, 0)), Quaternion(), 1.0, col))
    h.end()
    check("a new stroke deletes the undone copies (no orphans)", gone not in bpy.data.objects)
    h2 = L.StrokeHistory()
    check("undo with nothing -> False", h2.undo(col) is False)
    h2.begin()
    h2.end()
    check("empty stroke is not recorded", h2.undo(col) is False)


def test_centers_curve():
    col = bpy.data.collections.new("Out")
    bpy.context.scene.collection.children.link(col)
    L = logic()
    pts = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((2, 1, 0)), Vector((3, 1, 1))]
    check("fewer than 2 points -> no curve", L.centers_curve(pts[:1], col) is None)
    line = L.centers_curve(pts, col, smooth=True, bevel_depth=0.1)
    sp = line.data.splines[0]
    check("smooth -> one Bezier spline", line.type == 'CURVE' and sp.type == 'BEZIER')
    check("passes through every center", all(near(bp.co, p) for bp, p in zip(sp.bezier_points, pts))
          and len(sp.bezier_points) == 4)
    check("bevel depth = thickness", abs(line.data.bevel_depth - 0.1) < 1e-6)
    check("3D curve, linked to the collection", line.data.dimensions == '3D' and line.name in col.objects)
    line = L.centers_curve(pts, col, smooth=False, cyclic=True)
    sp = line.data.splines[0]
    check("not smooth -> POLY spline through the centers",
          sp.type == 'POLY' and all(near(p.co.xyz, q) for p, q in zip(sp.points, pts)))
    check("cyclic closes the line", sp.use_cyclic_u)
    # the line rides on the stroke history: undo / redo / purge handle it too
    h = L.StrokeHistory()
    h.begin()
    bpy.ops.mesh.primitive_cube_add()
    src = bpy.context.object
    for p in pts:
        h.add(L.place_instance(bpy.context, src, p, Quaternion(), 1.0, col))
    check("current() lists the stroke's copies", [o.location for o in h.current()] == pts)
    line = L.centers_curve([o.location for o in h.current()], col)
    h.add(line)
    h.end()
    name, data = line.name, line.data.name
    h.undo(col)
    check("undo takes the line away with the copies", name not in col.objects)
    h.redo(col)
    check("redo brings the line back", name in col.objects)
    h.undo(col)
    h.purge()
    check("purge deletes the line and its curve data",
          name not in bpy.data.objects and data not in bpy.data.curves)


def test_nearest_chain():
    f = logic().nearest_chain
    pts = [Vector((0, 0, 0)), Vector((5, 0, 0)), Vector((1, 0, 0)), Vector((3, 0, 0))]
    check("walks to the closest point each step", f(pts, 0) == [0, 2, 3, 1], str(f(pts, 0)))
    check("starts where asked", f(pts, 1) == [1, 3, 2, 0], str(f(pts, 1)))
    check("empty -> []", f([]) == [])


def test_connect_selected():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    objs = []
    for name, x in (("B", 4.0), ("A", 0.0), ("C", 1.0)):
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=(x, 0, 0))
        bpy.context.object.name = name
        objs.append(bpy.context.object)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[1]  # A at x=0
    r = bpy.ops.object.sts_connect_selected(order='NEAREST', thickness=0.03)
    line = bpy.context.object
    check("connect selected: finished, the curve is active", r == {'FINISHED'} and line.type == 'CURVE', str(r))
    xs = [round(bp.co.x, 4) for bp in line.data.splines[0].bezier_points]
    check("nearest from the active: A(0) -> C(1) -> B(4)", xs == [0.0, 1.0, 4.0], str(xs))
    check("thickness on the curve", abs(line.data.bevel_depth - 0.03) < 1e-6)
    line.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.ops.object.sts_connect_selected(order='NAME', smooth=False)
    xs = [round(p.co.x, 4) for p in bpy.context.object.data.splines[0].points]
    check("name order: A(0) -> B(4) -> C(1), straight", xs == [0.0, 4.0, 1.0], str(xs))
    for o in bpy.data.objects:
        o.select_set(False)
    objs[0].select_set(True)
    check("needs two or more selected", not bpy.ops.object.sts_connect_selected.poll())


def _min_dist(obj, co):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    d = min((obj.matrix_world @ v.co - Vector(co)).length for v in me.vertices)
    ev.to_mesh_clear()
    return d


def test_follow_modes():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    objs = []
    for name, x in (("A", 0.0), ("B", 2.0), ("C", 4.0)):
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=(x, 0, 0))
        bpy.context.object.name = name
        objs.append(bpy.context.object)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.sts_connect_selected(order='NAME')
    line = bpy.context.object
    L = logic()
    check("the line remembers its objects", [o.name for _i, o in L.line_beads(line)] == ["A", "B", "C"])
    check("a bead finds its line", L.find_line(objs[1]) == line)
    line.location = (0, 0, 1)        # the line's own transform must not matter
    objs[1].location.z = 1.0         # (beads sit at z=0 / 1 from here on)
    for o in objs:
        o.location.z = 1.0
    bpy.context.view_layer.update()

    bpy.context.view_layer.objects.active = objs[1]   # works from a bead too
    r = bpy.ops.object.sts_line_follow(mode='OBJECTS')
    check("OBJECTS: finished", r == {'FINISHED'}, str(r))
    check("OBJECTS: one hook per bead", len([m for m in line.modifiers if m.type == 'HOOK']) == 3)
    check("OBJECTS: switching does not move the curve", _min_dist(line, (2, 0, 1)) < 1e-3,
          str(_min_dist(line, (2, 0, 1))))
    objs[1].location = (2, 3, 2)
    bpy.context.view_layer.update()
    check("OBJECTS: moving an object pulls the curve", _min_dist(line, (2, 3, 2)) < 1e-3,
          str(_min_dist(line, (2, 3, 2))))

    bpy.ops.object.sts_line_follow(mode='CURVE')
    check("CURVE: hooks gone", not [m for m in line.modifiers if m.type == 'HOOK'])
    check("CURVE: the curve kept the pulled shape", _min_dist(line, (2, 3, 2)) < 1e-3)
    check("CURVE: objects did not jump", (objs[1].matrix_world.translation - Vector((2, 3, 2))).length < 1e-4,
          str(objs[1].matrix_world.translation))
    check("CURVE: objects vertex-parented", all(o.parent == line and o.parent_type == 'VERTEX' for o in objs))
    bp = line.data.splines[0].bezier_points[2]
    bp.co = bp.co + Vector((0, 0, 5))
    bpy.context.view_layer.update()
    check("CURVE: moving a point carries its object", abs(objs[2].matrix_world.translation.z - 6.0) < 1e-4,
          str(objs[2].matrix_world.translation))
    check("CURVE: the others stay", abs(objs[0].matrix_world.translation.z - 1.0) < 1e-4)

    bpy.ops.object.sts_line_follow(mode='NONE')
    check("NONE: unparented, kept in place",
          objs[2].parent is None and abs(objs[2].matrix_world.translation.z - 6.0) < 1e-4,
          str(objs[2].matrix_world.translation))
    check("NONE: mode stored", line["sts_follow"] == 'NONE')
    bpy.data.objects.remove(objs[1])
    check("a deleted bead is skipped", [o.name for _i, o in L.line_beads(line)] == ["A", "C"])
    bpy.context.view_layer.objects.active = line
    check("switching still works without it", bpy.ops.object.sts_line_follow(mode='OBJECTS') == {'FINISHED'})


def test_poll():
    check("poll fails without a 3D view (background)", not bpy.ops.object.sts_object_brush.poll())


run([
    test_registered,
    test_settings,
    test_grid_snap_xy,
    test_instance_rotation_spin_around_normal,
    test_instance_rotation_options,
    test_depth_fallback,
    test_place_instance_ignores_parent,
    test_stroke_history,
    test_centers_curve,
    test_nearest_chain,
    test_connect_selected,
    test_follow_modes,
    test_poll,
])
