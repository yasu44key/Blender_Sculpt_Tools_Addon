"""Functional tests for modules/smooth_normals. Run through tests/run_tests.sh."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def N():
    return submodule("modules.smooth_normals.normals")


def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return o.evaluated_get(dg).data


def cube_with_top_group():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    vg = o.vertex_groups.new(name="Mask")
    vg.add([v.index for v in o.data.vertices if v.co.z > 0], 1.0, 'REPLACE')
    return o


def flat(vec):
    return max(abs(c) for c in vec) > 0.999


def corner_split(o):
    """(smoothed corners on top vertices, flat corners on bottom vertices, totals)."""
    me = evaluated(o)
    top = bottom = n_top = n_bottom = 0
    for i, loop in enumerate(me.loops):
        v = me.corner_normals[i].vector
        if o.data.vertices[loop.vertex_index].co.z > 0:
            n_top += 1
            top += not flat(v)
        else:
            n_bottom += 1
            bottom += flat(v)
    return top, n_top, bottom, n_bottom


def test_registered():
    check("module listed in MODULES", "smooth_normals" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.smooth_normals").META["tabs"] == ("Model",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_smooth_normals", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)


def test_weighted_by_group():
    o = cube_with_top_group()
    r = bpy.ops.object.sts_smooth_normals_add()
    check("add finished", r == {'FINISHED'}, str(r))
    mod = N().get(o)
    check("active vertex group filled in", N().get_input(mod, "Vertex Group") == "Mask")
    top, n_top, bottom, n_bottom = corner_split(o)
    check("painted corners are smoothed", top == n_top, f"{top}/{n_top}")
    check("unpainted corners keep their flat normals", bottom == n_bottom, f"{bottom}/{n_bottom}")
    check("shape unchanged", [tuple(v.co) for v in evaluated(o).vertices] == [tuple(v.co) for v in o.data.vertices])


def test_whole_mesh_without_group():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    bpy.ops.object.sts_smooth_normals_add()
    top, n_top, bottom, n_bottom = corner_split(o)
    check("no group: the whole mesh is smoothed", top == n_top and bottom == 0, f"{top}/{n_top}, {bottom}")


def test_strength():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    bpy.ops.object.sts_smooth_normals_add()
    mod = N().get(o)
    me = evaluated(o)
    full = me.corner_normals[0].vector.copy()
    N().set_input(mod, "Strength", 0.0)
    me = evaluated(o)
    off = me.corner_normals[0].vector.copy()
    N().set_input(mod, "Strength", 0.5)
    me = evaluated(o)
    half = me.corner_normals[0].vector.copy()
    check("strength 0: flat", flat(off))
    check("strength 1: smoothed", not flat(full))
    check("strength 0.5: in between", off.angle(half) > 0.05 and half.angle(full) > 0.05,
          f"{off.angle(half)} {half.angle(full)}")


def test_sculpt_mask_as_weight():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    m = o.data.attributes.new(N().SCULPT_MASK, 'FLOAT', 'POINT')
    for i, v in enumerate(o.data.vertices):
        m.data[i].value = 1.0 if v.co.z > 0 else 0.0
    r = bpy.ops.object.sts_smooth_normals_from_mask()
    check("from mask: finished, modifier added, group filled in",
          r == {'FINISHED'} and N().get(o) is not None and N().get_input(N().get(o), "Vertex Group") == "Sculpt Mask")
    top, n_top, bottom, n_bottom = corner_split(o)
    check("sculpt mask: masked corners smoothed, the rest flat", top == n_top and bottom == n_bottom,
          f"{top}/{n_top}, {bottom}/{n_bottom}")
    bpy.ops.mesh.primitive_cube_add(location=(4, 0, 0))
    check("no mask -> CANCELLED", bpy.ops.object.sts_smooth_normals_from_mask() == {'CANCELLED'})


def test_apply_keeps_normals():
    o = cube_with_top_group()
    bpy.ops.object.sts_smooth_normals_add()
    want = [tuple(round(c, 4) for c in cn.vector) for cn in evaluated(o).corner_normals]
    bpy.ops.object.modifier_apply(modifier=N().MOD_NAME)
    got = [tuple(round(c, 4) for c in cn.vector) for cn in o.data.corner_normals]
    check("apply keeps the custom normals", o.data.has_custom_normals and got == want)


def test_remove_and_refuse():
    bpy.ops.mesh.primitive_cube_add()
    o = bpy.context.object
    bpy.ops.object.sts_smooth_normals_add()
    bpy.ops.object.sts_smooth_normals_add()
    check("add twice: one modifier", sum(1 for m in o.modifiers if m.type == 'NODES') == 1)
    check("removed", bpy.ops.object.sts_smooth_normals_remove() == {'FINISHED'} and N().get(o) is None)
    check("remove again -> CANCELLED", bpy.ops.object.sts_smooth_normals_remove() == {'CANCELLED'})
    o.select_set(False)
    check("nothing selected -> CANCELLED", bpy.ops.object.sts_smooth_normals_add() == {'CANCELLED'})


run([
    test_registered,
    test_weighted_by_group,
    test_whole_mesh_without_group,
    test_strength,
    test_sculpt_mask_as_weight,
    test_apply_keeps_normals,
    test_remove_and_refuse,
])
