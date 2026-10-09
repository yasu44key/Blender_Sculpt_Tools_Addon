"""Functional tests for modules/align_tools. Run through tests/run_tests.sh.

Four operators replace the ten of AlignScripts:
  object.sts_align_to_axis      (Edit Mode)  selected faces' average normal / one edge -> a world axis
  object.sts_origin_to_bottom   origin to the bottom of each selected object (+ offset ratio)
  object.sts_drop_to_surface    move along a direction until the object touches a surface / the ground plane
  object.sts_match_cursor       location / rotation from the 3D cursor, scale kept
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

OPS = ["object.sts_align_to_axis", "object.sts_drop_to_surface",
       "object.sts_match_cursor", "object.sts_origin_to_bottom"]


def near(a, b, eps=1e-4):
    return (Vector(a) - Vector(b)).length < eps


def world_verts(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def cube(size=2.0, location=(0, 0, 0), name=None):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    o = bpy.context.object
    if name:
        o.name = name
    return o


def select_only(*objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def select_faces(obj, test):
    """Edit Mode on obj with exactly the faces whose local normal passes test() selected."""
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for f in bm.faces:
        f.select = False
    for e in bm.edges:
        e.select = False
    for v in bm.verts:
        v.select = False
    for f in bm.faces:
        if test(f):
            f.select = True
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data)


def world_avg_normal_of_selection(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    m3 = obj.matrix_world.to_3x3().inverted().transposed()
    n = sum(((m3 @ f.normal).normalized() for f in bm.faces if f.select), Vector())
    return n.normalized()


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "align_tools" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.align_tools").META["tabs"] == ("Model",))
    pkg = package() + ".modules.align_tools"
    ops = sorted(c.bl_idname for c in bpy.types.Operator.__subclasses__() if c.__module__.startswith(pkg))
    check("exactly the four operators", ops == OPS, str(ops))
    for name in ops:
        cls = next(c for c in bpy.types.Operator.__subclasses__() if c.bl_idname == name)
        check(f"{name} is undoable", 'UNDO' in getattr(cls, "bl_options", set()))
    p = getattr(bpy.types, "VIEW3D_PT_sts_align_tools", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    old = [n for n in ("OBJECT_OT_align_edge_to_axis", "OBJECT_OT_snap_to_ground",
                       "OBJECT_OT_origin_to_bottom", "OBJECT_OT_snap_to_surface_stable") if hasattr(bpy.types, n)]
    check("old AlignScripts operators not registered", not old, str(old))


def test_props():
    P = bpy.ops.object.sts_align_to_axis.get_rna_type().properties
    axes = {'POS_X', 'NEG_X', 'POS_Y', 'NEG_Y', 'POS_Z', 'NEG_Z'}
    check("align: source FACES / EDGE", {i.identifier for i in P["source"].enum_items} == {'FACES', 'EDGE'})
    check("align: axis six directions, default NEG_Z",
          {i.identifier for i in P["axis"].enum_items} == axes and P["axis"].default == 'NEG_Z')
    check("align: pivot ORIGIN / SELECTION", {i.identifier for i in P["pivot"].enum_items} == {'ORIGIN', 'SELECTION'})
    check("align: apply_rotation default True", P["apply_rotation"].default is True)
    P = bpy.ops.object.sts_drop_to_surface.get_rna_type().properties
    check("drop: direction six, default NEG_Z",
          {i.identifier for i in P["direction"].enum_items} == axes and P["direction"].default == 'NEG_Z')
    check("drop: target SURFACE / GROUND", {i.identifier for i in P["target"].enum_items} == {'SURFACE', 'GROUND'})
    check("drop: offset is a length", P["offset"].unit == 'LENGTH')
    check("drop: align_rotation default False", P["align_rotation"].default is False)
    P = bpy.ops.object.sts_origin_to_bottom.get_rna_type().properties
    check("origin: offset_ratio 0..1 default 0", P["offset_ratio"].hard_min == 0 and P["offset_ratio"].hard_max == 1
          and P["offset_ratio"].default == 0)
    P = bpy.ops.object.sts_match_cursor.get_rna_type().properties
    check("match: use_location / use_rotation default True",
          P["use_location"].default is True and P["use_rotation"].default is True)


# ---------------------------------------------------------------- align to axis

def test_align_faces_on_rotated_object():
    o = cube()
    o.rotation_euler = Euler((math.radians(30), math.radians(10), 0))   # rotation NOT applied
    bpy.context.view_layer.update()
    select_faces(o, lambda f: f.normal.z > 0.9)            # local top face
    r = bpy.ops.object.sts_align_to_axis(source='FACES', axis='NEG_Z', pivot='ORIGIN', apply_rotation=True)
    check("align faces finished", r == {'FINISHED'}, str(r))
    check("stays in Edit Mode", bpy.context.mode == 'EDIT_MESH', bpy.context.mode)
    n = world_avg_normal_of_selection(o)
    check("face now points to -Z in world space (existing rotation respected)", near(n, (0, 0, -1), 1e-3), str(n))
    check("apply_rotation: object rotation is zero", near(o.rotation_euler, (0, 0, 0), 1e-4), str(o.rotation_euler))
    bpy.ops.object.mode_set(mode='OBJECT')


def test_align_multi_faces_keep_rotation_and_pivot():
    o = cube(location=(3, 0, 0))
    select_faces(o, lambda f: f.normal.x > 0.9 or f.normal.z > 0.9)   # two faces, avg normal (1,0,1)/sqrt2
    bm = bmesh.from_edit_mesh(o.data)
    center_before = o.matrix_world @ (sum((f.calc_center_median() for f in bm.faces if f.select), Vector()) / 2)
    bpy.ops.object.sts_align_to_axis(source='FACES', axis='POS_Y', pivot='SELECTION', apply_rotation=False)
    n = world_avg_normal_of_selection(o)
    check("average normal of 2 faces -> +Y", near(n, (0, 1, 0), 1e-3), str(n))
    check("apply_rotation off: rotation kept on the object", not near(o.rotation_euler, (0, 0, 0)))
    bm = bmesh.from_edit_mesh(o.data)
    center_after = o.matrix_world @ (sum((f.calc_center_median() for f in bm.faces if f.select), Vector()) / 2)
    check("pivot SELECTION: faces' center does not move", near(center_before, center_after, 1e-3),
          f"{center_before} -> {center_after}")
    bpy.ops.object.mode_set(mode='OBJECT')


def test_align_edge():
    o = cube()
    o.rotation_euler = Euler((0, 0, math.radians(25)))
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(o.data)
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False
    for v in bm.verts:
        v.select = False
    e = next(e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).normalized().x) > 0.9)
    e.select = True
    bmesh.update_edit_mesh(o.data)
    r = bpy.ops.object.sts_align_to_axis(source='EDGE', axis='POS_Y')
    check("align edge finished", r == {'FINISHED'}, str(r))
    bm = bmesh.from_edit_mesh(o.data)
    e = next(e for e in bm.edges if e.select)
    d = (o.matrix_world @ e.verts[1].co - o.matrix_world @ e.verts[0].co).normalized()
    check("edge parallel to world Y", abs(abs(d.y) - 1.0) < 1e-3, str(d))
    bpy.ops.object.mode_set(mode='OBJECT')


def test_align_errors():
    o = cube()
    select_faces(o, lambda f: False)
    check("no faces selected -> CANCELLED", bpy.ops.object.sts_align_to_axis(source='FACES') == {'CANCELLED'})
    check("EDGE without exactly one edge -> CANCELLED",
          bpy.ops.object.sts_align_to_axis(source='EDGE') == {'CANCELLED'})
    bpy.ops.object.mode_set(mode='OBJECT')
    check("poll: needs Edit Mode", not bpy.ops.object.sts_align_to_axis.poll())


# ---------------------------------------------------------------- origin to bottom

def test_origin_to_bottom_rotated_and_multi():
    a = cube(location=(0, 0, 3))
    a.rotation_euler = Euler((math.radians(45), 0, 0))           # rotated: dimensions.z lies
    b = cube(size=1.0, location=(5, 0, 1))
    bpy.context.view_layer.update()
    before_a, before_b = world_verts(a), world_verts(b)
    cursor_before = bpy.context.scene.cursor.location.copy()
    select_only(a, b)
    r = bpy.ops.object.sts_origin_to_bottom(offset_ratio=0.0)
    bpy.context.view_layer.update()
    check("origin to bottom finished", r == {'FINISHED'}, str(r))
    for o, before in ((a, before_a), (b, before_b)):
        wv = world_verts(o)
        check(f"{o.name}: mesh does not move in the world", all(near(p, q, 1e-4) for p, q in zip(before, wv)))
        low = min(p.z for p in wv)
        check(f"{o.name}: origin z = lowest world z", abs(o.matrix_world.translation.z - low) < 1e-4,
              f"{o.matrix_world.translation.z} vs {low}")
        cx = (min(p.x for p in wv) + max(p.x for p in wv)) / 2
        check(f"{o.name}: origin x at the world bounds center", abs(o.matrix_world.translation.x - cx) < 1e-4)
    check("each object gets its own bottom (not the active's)",
          abs(a.matrix_world.translation.x - b.matrix_world.translation.x) > 1.0)
    check("3D cursor not moved", near(bpy.context.scene.cursor.location, cursor_before))


def test_origin_offset_ratio():
    o = cube(size=2.0, location=(0, 0, 1))      # z from 0 to 2
    select_only(o)
    bpy.ops.object.sts_origin_to_bottom(offset_ratio=0.5)
    bpy.context.view_layer.update()
    check("ratio 0.5 -> middle height", abs(o.matrix_world.translation.z - 1.0) < 1e-4, str(o.matrix_world.translation))


def test_origin_skips_non_mesh():
    bpy.ops.object.empty_add()
    e = bpy.context.object
    o = cube(location=(0, 0, 4))
    select_only(o, e)
    r = bpy.ops.object.sts_origin_to_bottom()
    check("non-mesh in the selection does not stop it", r == {'FINISHED'})


# ---------------------------------------------------------------- drop to surface

def test_drop_onto_bumps():
    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0, 0, 0))
    floor = bpy.context.object
    bump = cube(size=0.5, location=(0.8, 0.8, 0.25), name="Bump")   # top at z = 0.5, under one corner
    o = cube(size=2.0, location=(0, 0, 5))                             # x, y from -1 to 1
    select_only(o)
    r = bpy.ops.object.sts_drop_to_surface(direction='NEG_Z', target='SURFACE', offset=0.0)
    bpy.context.view_layer.update()
    low = min(p.z for p in world_verts(o))
    check("drop finished", r == {'FINISHED'}, str(r))
    check("rests on the bump (lowest point z = 0.5), not through it", abs(low - 0.5) < 1e-3, str(low))
    check("floor and bump untouched", floor.location.z == 0 and abs(bump.location.z - 0.25) < 1e-6)


def test_drop_onto_bump_under_the_middle():
    """A small bump under the middle of a flat bottom: rays from the object's corners miss it,
    so the contact must also be checked from the surfaces below (no sinking through)."""
    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0, 0, 0))
    cube(size=0.2, location=(0, 0, 0.1), name="MiddleBump")              # top at z = 0.2
    o = cube(size=2.0, location=(0, 0, 5))
    select_only(o)
    bpy.ops.object.sts_drop_to_surface(direction='NEG_Z', target='SURFACE')
    bpy.context.view_layer.update()
    low = min(p.z for p in world_verts(o))
    check("rests on a bump under the middle (z = 0.2), not sunk to the floor", abs(low - 0.2) < 1e-3, str(low))


def test_drop_ground_and_offset():
    o = cube(size=2.0, location=(0, 0, 5))
    select_only(o)
    bpy.ops.object.sts_drop_to_surface(direction='NEG_Z', target='GROUND', offset=0.25)
    bpy.context.view_layer.update()
    low = min(p.z for p in world_verts(o))
    check("GROUND: lowest point at z = offset (0.25)", abs(low - 0.25) < 1e-4, str(low))


def test_drop_side_direction():
    wall = cube(size=1.0, location=(6, 0, 0), name="Wall")       # x from 5.5 to 6.5
    o = cube(size=2.0, location=(0, 0, 0))
    select_only(o)
    bpy.ops.object.sts_drop_to_surface(direction='POS_X', target='SURFACE')
    bpy.context.view_layer.update()
    high = max(p.x for p in world_verts(o))
    check("+X: touches the wall (max x = 5.5)", abs(high - 5.5) < 1e-3, str(high))
    check("wall untouched", abs(wall.location.x - 6.0) < 1e-6)


def test_drop_nothing_below():
    o = cube(location=(0, 0, 5))
    select_only(o)
    r = bpy.ops.object.sts_drop_to_surface(direction='NEG_Z', target='SURFACE')
    check("nothing below: object stays", abs(o.location.z - 5) < 1e-6)
    check("nothing below: not an error", r in ({'FINISHED'}, {'CANCELLED'}))


def test_drop_align_rotation():
    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0, 0, 0))
    slope = bpy.context.object
    slope.rotation_euler = Euler((math.radians(30), 0, 0))
    o = cube(size=1.0, location=(0, 0, 5))
    select_only(o)
    bpy.ops.object.sts_drop_to_surface(direction='NEG_Z', target='SURFACE', align_rotation=True)
    bpy.context.view_layer.update()
    up = (o.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    normal = (slope.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    check("align_rotation: object up = surface normal", near(up, normal, 1e-3), f"{up} vs {normal}")


def test_drop_skips_non_mesh():
    bpy.ops.object.empty_add(location=(0, 0, 3))
    e = bpy.context.object
    o = cube(location=(0, 0, 5))
    select_only(o, e)
    r = bpy.ops.object.sts_drop_to_surface(direction='NEG_Z', target='GROUND')
    check("non-mesh in the selection does not stop it", r == {'FINISHED'})


# ---------------------------------------------------------------- match cursor

def test_match_cursor_keeps_scale():
    o = cube(location=(1, 1, 1))
    o.scale = (2, 3, 4)
    cur = bpy.context.scene.cursor
    cur.location = (5, 6, 7)
    cur.rotation_euler = Euler((0, 0, math.radians(90)))
    select_only(o)
    r = bpy.ops.object.sts_match_cursor()
    bpy.context.view_layer.update()
    check("match finished", r == {'FINISHED'}, str(r))
    check("location from cursor", near(o.matrix_world.translation, (5, 6, 7)))
    x = (o.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    check("rotation from cursor", near(x, (0, 1, 0), 1e-4), str(x))
    check("scale kept", near(o.matrix_world.to_scale(), (2, 3, 4), 1e-4), str(o.matrix_world.to_scale()))
    cur.location = (0, 0, 0)
    bpy.ops.object.sts_match_cursor(use_rotation=False)
    check("use_rotation off: rotation untouched", near((o.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized(),
                                                      (0, 1, 0), 1e-4))


run([
    test_registered,
    test_props,
    test_align_faces_on_rotated_object,
    test_align_multi_faces_keep_rotation_and_pivot,
    test_align_edge,
    test_align_errors,
    test_origin_to_bottom_rotated_and_multi,
    test_origin_offset_ratio,
    test_origin_skips_non_mesh,
    test_drop_onto_bumps,
    test_drop_onto_bump_under_the_middle,
    test_drop_ground_and_offset,
    test_drop_side_direction,
    test_drop_nothing_below,
    test_drop_align_rotation,
    test_drop_skips_non_mesh,
    test_match_cursor_keeps_scale,
])
