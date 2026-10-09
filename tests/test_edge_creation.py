"""Functional tests for modules/edge_creation. Run through tests/run_tests.sh.

The interactive part (the modal operator) only runs in the GUI, so the
decisions it makes live in modules/edge_creation/logic.py and are tested here:
  classify_event(event_type, value) -> action string
  surface_point(scene, depsgraph, origin, direction, fallback, offset=0.0, exclude=None)
  plane_point(origin, direction, axis) -> Vector or None
  drag_far_enough(last_co, co, interval) -> bool
  EdgeBuilder(context, target=None)   (add_point / undo_last / close_loop(fill) / finish / cancel)
"""

import os
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def logic():
    return submodule("modules.edge_creation.logic")


def add_plane(z, name, size=2.0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0.0, 0.0, z))
    obj = bpy.context.object
    obj.name = name
    return obj


def near(a, b, eps=1e-4):
    return (Vector(a) - Vector(b)).length < eps


def depsgraph():
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return dg


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "edge_creation" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.edge_creation").META["tabs"] == ("Model",))
    check("operator MESH_OT_sts_edge_draw registered", hasattr(bpy.types, "MESH_OT_sts_edge_draw"))
    op = getattr(bpy.types, "MESH_OT_sts_edge_draw", None)
    check("operator idname mesh.sts_edge_draw", op is not None and op.bl_idname == "mesh.sts_edge_draw")
    panel = getattr(bpy.types, "VIEW3D_PT_sts_edge_creation", None)
    tabs = submodule("core.tabs")
    check("panel VIEW3D_PT_sts_edge_creation in the Model tab",
          panel is not None and panel.bl_category == tabs.MODEL)
    check("settings on Scene.sts_edge_creation", hasattr(bpy.context.scene, "sts_edge_creation"))
    s = bpy.context.scene.sts_edge_creation
    check("settings: target is NEW / ACTIVE",
          {i.identifier for i in s.bl_rna.properties["target"].enum_items} == {'NEW', 'ACTIVE'})
    check("settings: surface_offset float", s.bl_rna.properties["surface_offset"].type == 'FLOAT')
    P = s.bl_rna.properties
    check("settings: depth_mode SURFACE / CURSOR / PLANE",
          {i.identifier for i in P["depth_mode"].enum_items} == {'SURFACE', 'CURSOR', 'PLANE'}
          and P["depth_mode"].default == 'SURFACE')
    check("settings: plane_axis XY / XZ / YZ",
          {i.identifier for i in P["plane_axis"].enum_items} == {'XY', 'XZ', 'YZ'})
    check("settings: drag_interval float > 0", P["drag_interval"].type == 'FLOAT'
          and P["drag_interval"].default > 0)
    check("settings: fill_on_close bool, off by default",
          P["fill_on_close"].type == 'BOOLEAN' and P["fill_on_close"].default is False)


def test_no_wrapper_operators():
    """Fill Face / Toggle Edit Mode only wrapped built-ins (F / Tab); use those instead."""
    pkg = package() + ".modules.edge_creation"
    ops = [c for c in bpy.types.Operator.__subclasses__() if c.__module__.startswith(pkg)]
    names = [c.bl_idname for c in ops]
    check("only one operator in the module", names == ["mesh.sts_edge_draw"], str(names))


# ---------------------------------------------------------------- classify_event

def test_classify_event():
    ce = logic().classify_event
    table = [
        (('LEFTMOUSE', 'PRESS'), 'ADD'),
        (('LEFTMOUSE', 'RELEASE'), 'END_DRAG'),
        (('BACK_SPACE', 'PRESS'), 'UNDO'),
        (('C', 'PRESS'), 'CLOSE'),
        (('RET', 'PRESS'), 'FINISH'),
        (('NUMPAD_ENTER', 'PRESS'), 'FINISH'),
        (('ESC', 'PRESS'), 'CANCEL'),        # Esc discards (Blender convention)
        (('RIGHTMOUSE', 'PRESS'), 'FINISH'),
        (('RIGHTMOUSE', 'RELEASE'), 'NONE'),
        (('MIDDLEMOUSE', 'PRESS'), 'PASS'),
        (('WHEELUPMOUSE', 'PRESS'), 'PASS'),
        (('WHEELDOWNMOUSE', 'PRESS'), 'PASS'),
        (('TRACKPADPAN', 'NOTHING'), 'PASS'),
        (('TRACKPADZOOM', 'NOTHING'), 'PASS'),
        (('MOUSEMOVE', 'NOTHING'), 'PASS'),
        (('NUMPAD_1', 'PRESS'), 'PASS'),
        (('NUMPAD_5', 'PRESS'), 'PASS'),
        (('X', 'PRESS'), 'NONE'),          # other keys are swallowed while drawing
        (('TAB', 'PRESS'), 'NONE'),
    ]
    for (etype, value), want in table:
        got = ce(etype, value)
        check(f"classify_event({etype}, {value}) == {want}", got == want, str(got))


# ---------------------------------------------------------------- surface_point

def test_surface_point_hit_and_offset():
    add_plane(0.0, "Ground")
    sp = logic().surface_point
    dg = depsgraph()
    scene = bpy.context.scene
    co, hit = sp(scene, dg, Vector((0.2, 0.3, 5.0)), Vector((0.0, 0.0, -1.0)), Vector((9, 9, 9)))
    check("hit the plane", hit and near(co, (0.2, 0.3, 0.0)), f"{hit} {co}")
    co, hit = sp(scene, dg, Vector((0.2, 0.3, 5.0)), Vector((0.0, 0.0, -1.0)), Vector((9, 9, 9)),
                 offset=0.1)
    check("offset along the surface normal", hit and near(co, (0.2, 0.3, 0.1)), f"{co}")


def test_surface_point_miss_uses_fallback():
    add_plane(0.0, "Ground")
    co, hit = logic().surface_point(bpy.context.scene, depsgraph(), Vector((10.0, 10.0, 5.0)),
                                    Vector((0.0, 0.0, -1.0)), Vector((1.0, 2.0, 3.0)))
    check("miss returns the fallback", (not hit) and near(co, (1.0, 2.0, 3.0)), f"{hit} {co}")


def test_surface_point_exclude():
    add_plane(0.0, "Ground")
    top = add_plane(1.0, "Top")
    co, hit = logic().surface_point(bpy.context.scene, depsgraph(), Vector((0.0, 0.0, 5.0)),
                                    Vector((0.0, 0.0, -1.0)), Vector((9, 9, 9)), exclude=top)
    check("excluded object is looked through", hit and near(co, (0.0, 0.0, 0.0)), f"{hit} {co}")


def test_plane_point():
    pp = logic().plane_point
    p = pp(Vector((1.0, 2.0, 5.0)), Vector((0.0, 0.0, -1.0)), 'XY')
    check("XY plane hit", p is not None and near(p, (1.0, 2.0, 0.0)), str(p))
    p = pp(Vector((1.0, 5.0, 3.0)), Vector((0.0, -1.0, 0.0)), 'XZ')
    check("XZ plane hit", p is not None and near(p, (1.0, 0.0, 3.0)), str(p))
    p = pp(Vector((4.0, 1.0, 3.0)), Vector((-1.0, 0.0, 0.0)), 'YZ')
    check("YZ plane hit", p is not None and near(p, (0.0, 1.0, 3.0)), str(p))
    check("ray parallel to the plane -> None",
          pp(Vector((0.0, 0.0, 5.0)), Vector((1.0, 0.0, 0.0)), 'XY') is None)
    check("plane behind the ray -> None",
          pp(Vector((0.0, 0.0, 5.0)), Vector((0.0, 0.0, 1.0)), 'XY') is None)


def test_drag_far_enough():
    f = logic().drag_far_enough
    check("closer than interval -> False", f(Vector((0, 0, 0)), Vector((0.05, 0, 0)), 0.1) is False)
    check("at least interval -> True", f(Vector((0, 0, 0)), Vector((0.1, 0, 0)), 0.1) is True)
    check("no last point -> True", f(None, Vector((0, 0, 0)), 0.1) is True)


# ---------------------------------------------------------------- EdgeBuilder

def _new_builder(target=None):
    return logic().EdgeBuilder(bpy.context, target)


def test_builder_new_object():
    n_before = len(bpy.data.objects)
    b = _new_builder()
    check("no object before the first point", len(bpy.data.objects) == n_before)
    for co in [(0, 0, 0), (1, 0, 0), (1, 1, 0)]:
        b.add_point(Vector(co))
    obj = b.object
    check("object created on first point", obj is not None and obj.type == 'MESH')
    check("3 points -> 3 verts, 2 edges",
          len(obj.data.vertices) == 3 and len(obj.data.edges) == 2,
          f"{len(obj.data.vertices)} {len(obj.data.edges)}")
    check("vertices at the given world positions",
          near(obj.matrix_world @ obj.data.vertices[2].co, (1, 1, 0)))
    check("count == 3", b.count == 3, str(b.count))

    check("undo_last returns True", b.undo_last() is True)
    check("undo removes vertex and its edge",
          len(obj.data.vertices) == 2 and len(obj.data.edges) == 1)

    check("close_loop needs 3 points", b.close_loop() is False)
    b.add_point(Vector((1, 1, 0)))
    b.add_point(Vector((0, 1, 0)))
    check("close_loop with 4 points", b.close_loop() is True)
    check("closed loop has 4 edges", len(obj.data.edges) == 4, str(len(obj.data.edges)))
    check("close_loop twice does not duplicate", b.close_loop() is False and len(obj.data.edges) == 4)

    result = b.finish()
    check("finish returns the object", result is obj)
    check("finish: object active", bpy.context.view_layer.objects.active is obj)
    check("finish: in mesh edit mode", bpy.context.mode == 'EDIT_MESH', bpy.context.mode)
    bm = bmesh.from_edit_mesh(obj.data)
    check("finish: all new verts selected", all(v.select for v in bm.verts))
    bpy.ops.object.mode_set(mode='OBJECT')


def test_builder_close_with_fill():
    b = _new_builder()
    for co in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]:
        b.add_point(Vector(co))
    check("close_loop(fill=True)", b.close_loop(fill=True) is True)
    obj = b.object
    check("fill makes one face", len(obj.data.polygons) == 1, str(len(obj.data.polygons)))
    check("filled loop has 4 edges", len(obj.data.edges) == 4, str(len(obj.data.edges)))
    b.finish()
    bpy.ops.object.mode_set(mode='OBJECT')


def test_builder_cancel_new_object():
    n_before = len(bpy.data.objects)
    b = _new_builder()
    b.add_point(Vector((0, 0, 0)))
    b.add_point(Vector((1, 0, 0)))
    check("cancel returns None", b.cancel() is None)
    check("cancel removes the new object", len(bpy.data.objects) == n_before)
    check("cancel stays in Object Mode", bpy.context.mode == 'OBJECT', bpy.context.mode)


def test_builder_cancel_target():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = bpy.context.object
    b = _new_builder(target=cube)
    b.add_point(Vector((3, 0, 0)))
    b.add_point(Vector((3, 1, 0)))
    b.cancel()
    check("cancel removes only the added vertices", len(cube.data.vertices) == 8
          and len(cube.data.edges) == 12, f"{len(cube.data.vertices)} {len(cube.data.edges)}")
    check("cancel keeps the target object", cube.name in bpy.data.objects)


def test_builder_empty_finish():
    n_before = len(bpy.data.objects)
    b = _new_builder()
    check("finish without points returns None", b.finish() is None)
    check("finish without points creates nothing", len(bpy.data.objects) == n_before)
    check("undo with nothing returns False", _new_builder().undo_last() is False)


def test_builder_active_target():
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(1.0, 0.0, 0.0))
    cube = bpy.context.object
    cube.scale = (2.0, 2.0, 2.0)
    bpy.context.view_layer.update()
    n_objects = len(bpy.data.objects)

    b = _new_builder(target=cube)
    b.add_point(Vector((3.0, 0.0, 0.0)))   # world (3,0,0) -> local (1,0,0)
    check("no extra object for ACTIVE target", len(bpy.data.objects) == n_objects)
    check("builder.object is the target", b.object is cube)
    check("one vertex added to 8", len(cube.data.vertices) == 9, str(len(cube.data.vertices)))
    check("new vertex in local coordinates", near(cube.data.vertices[8].co, (1.0, 0.0, 0.0)),
          str(cube.data.vertices[8].co))
    check("first new vertex not connected to old geometry", len(cube.data.edges) == 12)

    check("undo removes the new vertex", b.undo_last() is True and len(cube.data.vertices) == 8)
    check("undo never removes existing geometry", b.undo_last() is False and len(cube.data.vertices) == 8)

    b.add_point(Vector((3.0, 0.0, 0.0)))
    b.add_point(Vector((3.0, 2.0, 0.0)))
    check("second point connects to first new one", len(cube.data.edges) == 13)
    b.finish()
    check("finish on target: edit mode", bpy.context.mode == 'EDIT_MESH')
    bm = bmesh.from_edit_mesh(cube.data)
    bm.verts.ensure_lookup_table()
    sel = [v.index for v in bm.verts if v.select]
    check("only the new vertices selected", sel == [8, 9], str(sel))
    bpy.ops.object.mode_set(mode='OBJECT')


run([
    test_registered,
    test_no_wrapper_operators,
    test_classify_event,
    test_surface_point_hit_and_offset,
    test_surface_point_miss_uses_fallback,
    test_surface_point_exclude,
    test_plane_point,
    test_drag_far_enough,
    test_builder_new_object,
    test_builder_close_with_fill,
    test_builder_cancel_new_object,
    test_builder_cancel_target,
    test_builder_empty_finish,
    test_builder_active_target,
])
