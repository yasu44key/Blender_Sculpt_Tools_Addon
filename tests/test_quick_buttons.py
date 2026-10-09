"""Functional tests for modules/quick_buttons."""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def two_cubes():
    bpy.ops.mesh.primitive_cube_add(location=(1, 2, 3), rotation=(0.1, 0.2, 0.3), scale=(2, 3, 4))
    a = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(location=(-1, -2, -3), rotation=(0.4, 0.5, 0.6), scale=(5, 6, 7))
    b = bpy.context.object
    a.select_set(True)
    return a, b


def close(u, v, eps=1e-5):
    return all(abs(x - y) < eps for x, y in zip(u, v))


def test_registered():
    check("module listed in MODULES", "quick_buttons" in sys.modules[package()].MODULES)
    check("META tabs is ('Utility',)", submodule("modules.quick_buttons").META["tabs"] == ("Utility",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_quick_buttons", None)
    check("panel in the Utility tab", p is not None and p.bl_category == submodule("core.tabs").UTILITY)


def test_reset_one_axis_on_all_selected():
    a, b = two_cubes()
    r = bpy.ops.object.sts_quick_reset(channel='LOCATION', axis='Y')
    check("reset location Y: finished", r == {'FINISHED'})
    check("location Y = 0 on every selected object (old: active only)",
          close(a.location, (1, 0, 3)) and close(b.location, (-1, 0, -3)), f"{a.location[:]} {b.location[:]}")
    bpy.ops.object.sts_quick_reset(channel='SCALE', axis='ALL')
    check("scale all = 1", close(a.scale, (1, 1, 1)) and close(b.scale, (1, 1, 1)))
    bpy.ops.object.sts_quick_reset(channel='ROTATION', axis='Z')
    check("rotation Z = 0, X/Y kept", close(a.rotation_euler, (0.1, 0.2, 0)) and close(b.rotation_euler, (0.4, 0.5, 0)))


def test_rotate_flatten_mirror_step_objects():
    bpy.ops.mesh.primitive_cube_add(location=(1, 0, 0))
    o = bpy.context.object
    bpy.context.scene.tool_settings.transform_pivot_point = 'INDIVIDUAL_ORIGINS'
    r = bpy.ops.view3d.sts_quick_rotate(axis='Z', angle=math.radians(90))
    check("rotate Z +90: counter-clockwise from above", r == {'FINISHED'} and abs(o.rotation_euler.z - math.pi / 2) < 1e-5,
          str(o.rotation_euler[:]))
    bpy.ops.view3d.sts_quick_mirror(axis='X')
    check("mirror X: a negative scale", o.scale[0] * o.scale[1] * o.scale[2] < 0, str(o.scale[:]))
    bpy.ops.view3d.sts_quick_step(axis='Y', distance=-0.5)
    check("step Y -0.5", close(o.location, (1, -0.5, 0)), str(o.location[:]))


def test_flatten_in_edit_mode():
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    o = bpy.context.object
    bpy.context.scene.tool_settings.transform_pivot_point = 'MEDIAN_POINT'
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    r = bpy.ops.view3d.sts_quick_flatten(axis='Z')
    bpy.ops.object.mode_set(mode='OBJECT')
    zs = {round(v.co.z, 5) for v in o.data.vertices}
    check("flatten Z in Edit Mode: all vertices at z=0", r == {'FINISHED'} and zs == {0.0}, str(zs))
    xs = {round(v.co.x, 5) for v in o.data.vertices}
    check("flatten Z leaves X alone", xs == {-1.0, 1.0}, str(xs))


def test_reset_needs_object_mode():
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.object.mode_set(mode='EDIT')
    check("reset is Object Mode only", not bpy.ops.object.sts_quick_reset.poll())
    bpy.ops.object.mode_set(mode='OBJECT')


run([
    test_registered,
    test_reset_one_axis_on_all_selected,
    test_rotate_flatten_mirror_step_objects,
    test_flatten_in_edit_mode,
    test_reset_needs_object_mode,
])
