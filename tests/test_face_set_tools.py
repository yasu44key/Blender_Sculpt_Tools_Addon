"""Functional tests for modules/face_set_tools. Run through tests/run_tests.sh.

logic.py (GUI-free):
  face_set_ids(mesh) -> sorted list of int
  face_set_under_ray(obj, origin, direction) -> int or None   (world space)
  apply_mask(mesh, ids, mode='REPLACE', invert=False) -> number of target vertices
Operator: sculpt.sts_face_set_to_mask (face_set, mode, invert)

Note: built-in sculpt operators (e.g. sculpt.face_sets_create) crash Blender
in background mode, so the tests only read / write mesh attributes.
"""

import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def logic():
    return submodule("modules.face_set_tools.logic")


def grid(location=(0.0, 0.0, 0.0), face_sets=True):
    """4x4-face grid, size 2 (x and y from -1 to 1). Face set 1 = x<0, 2 = x>0."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=2.0, location=location)
    obj = bpy.context.object
    if face_sets:
        attr = obj.data.attributes.new(".sculpt_face_set", 'INT', 'FACE')
        attr.data.foreach_set("value", [2 if p.center.x > 0 else 1 for p in obj.data.polygons])
    return obj


def mask(obj):
    a = obj.data.attributes.get(".sculpt_mask")
    return [d.value for d in a.data] if a else None


def xs(obj):
    return [v.co.x for v in obj.data.vertices]


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "face_set_tools" in sys.modules[package()].MODULES)
    check("META tabs is ('Sculpt',)", submodule("modules.face_set_tools").META["tabs"] == ("Sculpt",))
    op = getattr(bpy.types, "SCULPT_OT_sts_face_set_to_mask", None)
    check("operator registered", op is not None)
    check("operator idname", op is not None and op.bl_idname == "sculpt.sts_face_set_to_mask")
    p = getattr(bpy.types, "VIEW3D_PT_sts_face_set_tools", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)
    pkg = package() + ".modules.face_set_tools"
    ops = [c.bl_idname for c in bpy.types.Operator.__subclasses__() if c.__module__.startswith(pkg)]
    check("operators: to mask + smooth (the old deformer = built-in Mesh Filter)",
          sorted(ops) == ["sculpt.sts_face_set_smooth", "sculpt.sts_face_set_to_mask"], str(ops))
    s = getattr(bpy.context.scene, "sts_face_set_tools", None)
    check("settings on Scene.sts_face_set_tools", s is not None)
    if s is not None:
        modes = {i.identifier for i in s.bl_rna.properties["mode"].enum_items}
        check("settings mode REPLACE/ADD/SUBTRACT", modes == {'REPLACE', 'ADD', 'SUBTRACT'}, str(modes))
        check("settings invert bool", s.bl_rna.properties["invert"].type == 'BOOLEAN')


# ---------------------------------------------------------------- logic

def test_face_set_ids():
    obj = grid()
    check("face_set_ids", logic().face_set_ids(obj.data) == [1, 2], str(logic().face_set_ids(obj.data)))
    plain = grid(location=(5, 0, 0), face_sets=False)
    check("no face sets -> []", logic().face_set_ids(plain.data) == [])


def test_apply_mask_replace():
    obj = grid()
    n = logic().apply_mask(obj.data, {2}, 'REPLACE')
    m, x = mask(obj), xs(obj)
    check("mask attribute created", m is not None)
    check("right side verts masked (x >= 0)", all(v == 1.0 for v, xx in zip(m, x) if xx > -1e-6))
    check("left-only verts unmasked (x < 0)", all(v == 0.0 for v, xx in zip(m, x) if xx < -1e-6))
    check("returns target count (3 columns x 5 = 15)", n == 15, str(n))


def test_apply_mask_invert():
    obj = grid()
    n = logic().apply_mask(obj.data, {2}, 'REPLACE', invert=True)
    m, x = mask(obj), xs(obj)
    check("invert: left-only verts masked", all(v == 1.0 for v, xx in zip(m, x) if xx < -1e-6))
    check("invert: face set 2 verts unmasked", all(v == 0.0 for v, xx in zip(m, x) if xx > -1e-6))
    check("invert count (2 columns x 5 = 10)", n == 10, str(n))


def test_apply_mask_add_subtract():
    obj = grid()
    me = obj.data
    a = me.attributes.new(".sculpt_mask", 'FLOAT', 'POINT')
    a.data.foreach_set("value", [0.5 if v.co.y > 0.9 else 0.0 for v in me.vertices])  # top row = 0.5
    logic().apply_mask(me, {2}, 'ADD')
    m, x = mask(obj), xs(obj)
    top_left = [v for v, vert in zip(m, me.vertices) if vert.co.y > 0.9 and vert.co.x < -1e-6]
    check("ADD keeps existing mask outside the set", top_left and all(abs(v - 0.5) < 1e-6 for v in top_left),
          str(top_left))
    check("ADD sets the face set to 1", all(v == 1.0 for v, xx in zip(m, x) if xx > -1e-6))
    logic().apply_mask(me, {1}, 'SUBTRACT')
    m = mask(obj)
    check("SUBTRACT clears face set 1 (incl. shared column)",
          all(v == 0.0 for v, xx in zip(m, x) if xx < 1e-6), str([v for v, xx in zip(m, x) if xx < 1e-6]))
    check("SUBTRACT leaves the rest", all(v == 1.0 for v, xx in zip(m, x) if xx > 1e-6))


def test_apply_mask_keeps_hidden_state():
    obj = grid()
    me = obj.data
    me.polygons[0].hide = True
    me.polygons[5].hide = True
    before = [p.hide for p in me.polygons]
    logic().apply_mask(me, {1}, 'REPLACE')
    check("hidden faces untouched", [p.hide for p in me.polygons] == before)


def test_face_set_under_ray():
    obj = grid(location=(10.0, 0.0, 0.0))
    obj.scale = (2.0, 2.0, 2.0)            # grid spans x 8..12 in world space
    bpy.context.view_layer.update()
    f = logic().face_set_under_ray
    down = Vector((0, 0, -1))
    check("ray on the right half -> 2", f(obj, Vector((11.0, 0.3, 5.0)), down) == 2,
          str(f(obj, Vector((11.0, 0.3, 5.0)), down)))
    check("ray on the left half -> 1", f(obj, Vector((9.0, 0.3, 5.0)), down) == 1)
    check("miss -> None", f(obj, Vector((20.0, 0.0, 5.0)), down) is None)
    plain = grid(location=(30, 0, 0), face_sets=False)
    check("mesh without face sets -> None", f(plain, Vector((30.5, 0, 5)), down) is None)


# ---------------------------------------------------------------- operator

def test_operator():
    obj = grid()
    check("poll fails outside Sculpt Mode", not bpy.ops.sculpt.sts_face_set_to_mask.poll())
    bpy.ops.object.mode_set(mode='SCULPT')
    check("poll ok in Sculpt Mode", bpy.ops.sculpt.sts_face_set_to_mask.poll())
    r = bpy.ops.sculpt.sts_face_set_to_mask(face_set=2, mode='REPLACE')
    check("exec with face_set=2", r == {'FINISHED'}, str(r))
    check("still in Sculpt Mode", bpy.context.mode == 'SCULPT', bpy.context.mode)
    bpy.ops.object.mode_set(mode='OBJECT')
    m, x = mask(obj), xs(obj)
    check("operator wrote the mask", m is not None and all(v == 1.0 for v, xx in zip(m, x) if xx > -1e-6)
          and all(v == 0.0 for v, xx in zip(m, x) if xx < -1e-6))

    bpy.ops.object.mode_set(mode='SCULPT')
    r = bpy.ops.sculpt.sts_face_set_to_mask(face_set=9)
    check("unknown face set -> CANCELLED", r == {'CANCELLED'}, str(r))
    r = bpy.ops.sculpt.sts_face_set_to_mask(face_set=0)
    check("face_set=0 in exec -> CANCELLED", r == {'CANCELLED'}, str(r))
    bpy.ops.object.mode_set(mode='OBJECT')


def test_smooth_face_set():
    import random
    obj = grid()
    rng = random.Random(2)
    for v in obj.data.vertices:
        if v.co.x > 0.01 and abs(v.co.y) < 0.99 and v.co.x < 0.99:
            v.co.z = rng.uniform(-0.3, 0.3)
    before = [v.co.copy() for v in obj.data.vertices]
    bumpy = max(abs(v.co.z) for v in obj.data.vertices)
    bpy.ops.object.mode_set(mode='SCULPT')
    r = bpy.ops.sculpt.sts_face_set_smooth(face_set=2, iterations=20, strength=0.5)
    check("smooth face set: finished, still Sculpt Mode", r == {'FINISHED'} and bpy.context.mode == 'SCULPT', str(r))
    bpy.ops.object.mode_set(mode='OBJECT')
    after = [v.co.copy() for v in obj.data.vertices]
    left = [i for i, p in enumerate(before) if p.x < 0.01]
    outline = [i for i, p in enumerate(before) if p.x > 0.01 and (abs(p.y) > 0.99 or p.x > 0.99)]
    check("smooth face set: the other face set and the shared seam stay",
          all((after[i] - before[i]).length < 1e-6 for i in left))
    check("smooth face set: its outline (mesh border) stays", all((after[i] - before[i]).length < 1e-6 for i in outline))
    check("smooth face set: the bumps inside are relaxed", max(abs(p.z) for p in after) < bumpy * 0.6,
          f"{bumpy} -> {max(abs(p.z) for p in after)}")
    bpy.ops.object.mode_set(mode='SCULPT')
    check("smooth: unknown face set -> CANCELLED", bpy.ops.sculpt.sts_face_set_smooth(face_set=9) == {'CANCELLED'})
    bpy.ops.object.mode_set(mode='OBJECT')


def test_operator_no_face_sets():
    grid(face_sets=False)
    bpy.ops.object.mode_set(mode='SCULPT')
    r = bpy.ops.sculpt.sts_face_set_to_mask(face_set=1)
    check("mesh without face sets -> CANCELLED", r == {'CANCELLED'}, str(r))
    bpy.ops.object.mode_set(mode='OBJECT')


run([
    test_registered,
    test_face_set_ids,
    test_apply_mask_replace,
    test_apply_mask_invert,
    test_apply_mask_add_subtract,
    test_apply_mask_keeps_hidden_state,
    test_face_set_under_ray,
    test_operator,
    test_operator_no_face_sets,
    test_smooth_face_set,
])
