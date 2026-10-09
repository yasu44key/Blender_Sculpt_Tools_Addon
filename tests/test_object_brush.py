"""Functional tests for modules/object_brush. Run through tests/run_tests.sh.

logic.py (GUI-free):
  grid_snap_xy(co, size) -> Vector            (X and Y on the grid, Z unchanged)
  instance_rotation(normal, stroke_dir, align_to_normal, align_to_stroke, spin) -> Quaternion
  depth_fallback(origin, direction, last_depth, cursor) -> Vector
  place_instance(context, source, location, rotation, scale, collection) -> Object
  StrokeHistory: begin() / add(obj) / end() / undo(collection) / redo(collection) / purge()
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
    check("only one operator (the source picker has an eyedropper)", ops == ["object.sts_object_brush"], str(ops))
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
                 "align_to_stroke", "jitter_scale"):
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
    test_poll,
])
