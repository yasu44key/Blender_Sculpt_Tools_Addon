"""Functional tests for modules/mesh_tools. Run through tests/run_tests.sh.

What is left of MeshTools / PolyMaker after edge_creation absorbed Draw Polygon:
  object.sts_add_solidify  — one-click Solidify (second press updates, never duplicates)
Everything else in the panel is a built-in operator (Apply, Tris to Quads, Triangulate).
"""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def solidifies(obj):
    return [m for m in obj.modifiers if m.type == 'SOLIDIFY']


def test_registered():
    check("module listed in MODULES", "mesh_tools" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.mesh_tools").META["tabs"] == ("Model",))
    op = getattr(bpy.types, "OBJECT_OT_sts_add_solidify", None)
    check("operator registered", op is not None and op.bl_idname == "object.sts_add_solidify")
    p = getattr(bpy.types, "VIEW3D_PT_sts_mesh_tools", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    pkg = package() + ".modules.mesh_tools"
    ops = [c.bl_idname for c in bpy.types.Operator.__subclasses__() if c.__module__.startswith(pkg)]
    check("only one operator (the rest are built-ins)", ops == ["object.sts_add_solidify"], str(ops))
    old = [n for n in ("MESH_OT_create_polygon_mesh", "MESH_OT_change_polygon_type",
                       "OBJECT_OT_toggle_object_edit_mode", "MESH_OT_draw_polygon")
           if hasattr(bpy.types, n)]
    check("no old MeshTools / PolyMaker operators", not old, str(old))
    check("no Scene settings (values live on the operator / modifier)",
          not [k for k in bpy.types.Scene.bl_rna.properties.keys() if "solidify" in k])


def test_props():
    P = bpy.ops.object.sts_add_solidify.get_rna_type().properties
    check("thickness is a length", P["thickness"].unit == 'LENGTH' and abs(P["thickness"].default - 0.1) < 1e-6)
    check("offset -1..1, default 0", P["offset"].hard_min == -1 and P["offset"].hard_max == 1
          and P["offset"].default == 0)
    check("use_even_offset default False", P["use_even_offset"].default is False)
    check("use_rim default True", P["use_rim"].default is True)


def test_add_solidify():
    bpy.ops.mesh.primitive_plane_add()
    obj = bpy.context.object
    r = bpy.ops.object.sts_add_solidify(thickness=0.25, offset=-1.0, use_even_offset=True, use_rim=False)
    s = solidifies(obj)
    check("adds one Solidify", r == {'FINISHED'} and len(s) == 1, f"{r} {len(s)}")
    if s:
        m = s[0]
        check("values applied", abs(m.thickness - 0.25) < 1e-6 and m.offset == -1.0
              and m.use_even_offset and not m.use_rim)


def test_second_press_updates():
    bpy.ops.mesh.primitive_plane_add()
    obj = bpy.context.object
    bpy.ops.object.sts_add_solidify(thickness=0.1)
    bpy.ops.object.sts_add_solidify(thickness=0.5)
    s = solidifies(obj)
    check("second press does not duplicate", len(s) == 1, str(len(s)))
    check("second press updates the value", s and abs(s[0].thickness - 0.5) < 1e-6)


def test_edit_mode_ok():
    bpy.ops.mesh.primitive_plane_add()
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    r = bpy.ops.object.sts_add_solidify()
    check("works in Edit Mode too", r == {'FINISHED'} and len(solidifies(obj)) == 1)
    check("stays in Edit Mode", bpy.context.mode == 'EDIT_MESH', bpy.context.mode)
    bpy.ops.object.mode_set(mode='OBJECT')


def test_poll():
    bpy.ops.object.empty_add()
    check("poll fails for a non-mesh", not bpy.ops.object.sts_add_solidify.poll())


run([
    test_registered,
    test_props,
    test_add_solidify,
    test_second_press_updates,
    test_edit_mode_ok,
    test_poll,
])
