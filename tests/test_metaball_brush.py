"""Functional tests for modules/metaball_brush. Run through tests/run_tests.sh.

logic.py (GUI-free):
  radius_from_pressure(pressure, min_size, max_size, curve) -> float
  mirror_offsets(offset, mirror_x, mirror_y, mirror_z) -> list of Vector (no duplicates)
  should_place(mode, now, last_time, interval, mouse_px, last_px, distance_px) -> bool
  StrokeBuilder(context, resolution)   add(world_co, radius, mirror=(x, y, z)) / count / object / finish()
The modal brush itself is checked by tests/gui/gui_metaball_brush.py.
"""

import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def logic():
    return submodule("modules.metaball_brush.logic")


def near(a, b, eps=1e-4):
    return (Vector(a) - Vector(b)).length < eps


def world_elements(obj):
    return sorted((tuple(round(c, 4) for c in obj.matrix_world @ e.co) for e in obj.data.elements))


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "metaball_brush" in sys.modules[package()].MODULES)
    check("META tabs is ('Sculpt',)", submodule("modules.metaball_brush").META["tabs"] == ("Sculpt",))
    op = getattr(bpy.types, "OBJECT_OT_sts_metaball_brush", None)
    check("operator registered", op is not None and op.bl_idname == "object.sts_metaball_brush")
    p = getattr(bpy.types, "VIEW3D_PT_sts_metaball_brush", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)
    pkg = package() + ".modules.metaball_brush"
    ops = [c.bl_idname for c in bpy.types.Operator.__subclasses__() if c.__module__.startswith(pkg)]
    check("only one operator", ops == ["object.sts_metaball_brush"], str(ops))


def test_settings():
    s = getattr(bpy.context.scene, "sts_metaball_brush", None)
    check("settings on Scene.sts_metaball_brush", s is not None)
    if s is None:
        return
    P = s.bl_rna.properties
    view3d = submodule("core.view3d")
    check("depth_mode uses core DEPTH_ITEMS",
          [i.identifier for i in P["depth_mode"].enum_items] == [i[0] for i in view3d.DEPTH_ITEMS])
    check("depth_mode default CURSOR", P["depth_mode"].default == 'CURSOR')
    check("plane_axis uses core PLANE_ITEMS",
          [i.identifier for i in P["plane_axis"].enum_items] == [i[0] for i in view3d.PLANE_ITEMS])
    check("placement_mode TIME / DISTANCE",
          {i.identifier for i in P["placement_mode"].enum_items} == {'TIME', 'DISTANCE'})
    check("undo_mode STROKE / ELEMENT",
          {i.identifier for i in P["undo_mode"].enum_items} == {'STROKE', 'ELEMENT'})
    check("sizes are lengths", P["min_size"].unit == 'LENGTH' and P["max_size"].unit == 'LENGTH')
    for name in ("interval", "distance_px", "pressure_curve", "resolution",
                 "mirror_x", "mirror_y", "mirror_z"):
        check(f"setting {name}", name in P)
    check("no View Depth mode (removed)", "view_depth" not in P)


# ---------------------------------------------------------------- logic

def test_radius_from_pressure():
    f = logic().radius_from_pressure
    check("no pressure -> max size", f(0.0, 0.25, 1.0, 0.5) == 1.0)
    check("None pressure -> max size", f(None, 0.25, 1.0, 0.5) == 1.0)
    check("full pressure -> max size", abs(f(1.0, 0.25, 1.0, 0.5) - 1.0) < 1e-6)
    want = 0.25 + 0.75 * (0.25 ** 2.0)
    check("curve applied (0.25 ** 2)", abs(f(0.25, 0.25, 1.0, 2.0) - want) < 1e-6, str(f(0.25, 0.25, 1.0, 2.0)))


def test_mirror_offsets():
    f = logic().mirror_offsets
    one = f(Vector((1, 2, 3)), False, False, False)
    check("no mirror -> one offset", len(one) == 1 and near(one[0], (1, 2, 3)))
    xs = f(Vector((1, 2, 3)), True, False, False)
    check("mirror X -> 2", len(xs) == 2 and any(near(v, (-1, 2, 3)) for v in xs))
    all3 = f(Vector((1, 2, 3)), True, True, True)
    check("mirror XYZ -> 8", len(all3) == 8)
    on_plane = f(Vector((0, 2, 3)), True, False, False)
    check("on the mirror plane -> no duplicate", len(on_plane) == 1, str(on_plane))


def test_should_place():
    f = logic().should_place
    check("TIME: first placement", f('TIME', 10.0, None, 0.1, (0, 0), None, 20) is True)
    check("TIME: too soon", f('TIME', 10.05, 10.0, 0.1, (0, 0), (0, 0), 20) is False)
    check("TIME: interval passed", f('TIME', 10.1, 10.0, 0.1, (0, 0), (0, 0), 20) is True)
    check("DISTANCE: first placement", f('DISTANCE', 0, None, 0.1, (5, 5), None, 20) is True)
    check("DISTANCE: too close", f('DISTANCE', 0, 0, 0.1, (10, 0), (0, 0), 20) is False)
    check("DISTANCE: far enough", f('DISTANCE', 0, 0, 0.1, (12, 16), (0, 0), 20) is True)


# ---------------------------------------------------------------- StrokeBuilder

def test_stroke_builder():
    bpy.context.scene.cursor.location = (2.0, 0.0, 0.0)
    n_before = len(bpy.data.objects)
    b = logic().StrokeBuilder(bpy.context, resolution=0.2)
    check("no object before the first ball", len(bpy.data.objects) == n_before and b.object is None)
    b.add(Vector((3.0, 0.0, 0.0)), 0.5, mirror=(True, False, False))
    obj = b.object
    check("metaball object created", obj is not None and obj.type == 'META')
    check("object at the 3D cursor (mirror center)", obj is not None and near(obj.location, (2, 0, 0)))
    check("mirror X around the 3D cursor", obj is not None and
          world_elements(obj) == [(1.0, 0.0, 0.0), (3.0, 0.0, 0.0)], str(obj and world_elements(obj)))
    check("radius set", obj is not None and all(abs(e.radius - 0.5) < 1e-6 for e in obj.data.elements))
    check("resolution set", obj is not None and abs(obj.data.resolution - 0.2) < 1e-6)
    b.add(Vector((2.0, 1.0, 0.0)), 0.5, mirror=(True, False, False))  # on the mirror plane
    check("ball on the mirror plane not doubled", b.count == 3, str(b.count))
    check("finish returns the object", b.finish() is obj)
    check("object kept", obj.name in bpy.data.objects)


def test_stroke_builder_empty():
    n_before = len(bpy.data.objects)
    b = logic().StrokeBuilder(bpy.context, resolution=0.1)
    check("empty stroke: finish -> None", b.finish() is None)
    check("empty stroke leaves no object", len(bpy.data.objects) == n_before)


def test_each_stroke_its_own_object():
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    a = logic().StrokeBuilder(bpy.context, resolution=0.1)
    a.add(Vector((0, 0, 0)), 1.0, mirror=(False, False, False))
    a.finish()
    b = logic().StrokeBuilder(bpy.context, resolution=0.1)
    b.add(Vector((1, 0, 0)), 1.0, mirror=(False, False, False))
    b.finish()
    check("two strokes -> two objects", a.object is not None and b.object is not None
          and a.object is not b.object)


def test_poll():
    check("poll fails without a 3D view (background)", not bpy.ops.object.sts_metaball_brush.poll())


run([
    test_registered,
    test_settings,
    test_radius_from_pressure,
    test_mirror_offsets,
    test_should_place,
    test_stroke_builder,
    test_stroke_builder_empty,
    test_each_stroke_its_own_object,
    test_poll,
])
