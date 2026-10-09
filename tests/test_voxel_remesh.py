"""Functional tests for modules/voxel_remesh. Run through tests/run_tests.sh."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

VS = 0.05  # coarse voxels keep the tests fast


def face_sets(obj):
    a = obj.data.attributes.get(".sculpt_face_set")
    return {d.value for d in a.data} if a else set()


def scene_three():
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    cube = bpy.context.object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(1.0, 0, 0))
    sphere = bpy.context.object
    bpy.ops.curve.primitive_bezier_curve_add(location=(0, 1.0, 0))
    curve = bpy.context.object
    curve.data.bevel_depth = 0.1
    bpy.ops.object.empty_add(location=(0, 0, 2))
    empty = bpy.context.object
    for o in (cube, sphere, curve, empty):
        o.select_set(True)
    bpy.context.view_layer.objects.active = cube
    return cube, sphere, curve, empty


def ops_mod():
    return submodule("modules.voxel_remesh.ops")


def test_registered():
    check("module listed in MODULES", "voxel_remesh" in sys.modules[package()].MODULES)
    for n in ("OBJECT_OT_sts_voxel_join_remesh", "OBJECT_OT_sts_voxel_apply_remesh",
              "VIEW3D_PT_sts_voxel_remesh"):
        check(f"{n} registered", hasattr(bpy.types, n))
    p = getattr(bpy.types, "VIEW3D_PT_sts_voxel_remesh", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)


def test_no_underscore_properties():
    """V2_28 had _is_warning / _estimated_count: Blender refuses them at registration."""
    props = bpy.ops.object.sts_voxel_join_remesh.get_rna_type().properties
    bad = [k for k in props.keys() if k.startswith("_")]
    check("no '_' operator properties", not bad, str(bad))


def test_defaults():
    props = bpy.ops.object.sts_voxel_join_remesh.get_rna_type().properties
    check("default keeps originals", props["keep_originals"].default is True)
    check("default ends in Object Mode", props["final_mode"].default == 'OBJECT')
    check("default remesh applies now", props["remesh_mode"].default == 'APPLY')


def test_join_remesh_keeps_originals():
    cube, sphere, curve, empty = scene_three()
    names = {o.name for o in (cube, sphere, curve)}
    r = bpy.ops.object.sts_voxel_join_remesh(voxel_size=VS)
    res = bpy.context.active_object
    check("finished", r == {'FINISHED'}, str(r))
    check("result is a new mesh", res is not None and res.type == 'MESH' and res.name not in names)
    check("Object Mode", bpy.context.mode == 'OBJECT', bpy.context.mode)
    check("result is the only selected object", list(bpy.context.selected_objects) == [res],
          str([o.name for o in bpy.context.selected_objects]))
    check("originals still exist", all(n in bpy.data.objects for n in names))
    check("originals hidden", all(bpy.data.objects[n].hide_get() for n in names))
    check("originals untouched (cube still 6 faces)", len(cube.data.polygons) == 6)
    check("empty left alone", empty.name in bpy.data.objects and not empty.hide_get())
    # Join renumbers face sets so they stay distinct (e.g. 1, 4, 6): count them.
    check("one face set per source", len(face_sets(res)) == 3, str(face_sets(res)))
    check("remeshed (many faces)", len(res.data.polygons) > 500, str(len(res.data.polygons)))
    check("no leftover _part objects",
          not [o.name for o in bpy.data.objects if o.name.endswith("_part")])


def test_delete_originals():
    cube, sphere, curve, _empty = scene_three()
    names = [o.name for o in (cube, sphere, curve)]
    bpy.ops.object.sts_voxel_join_remesh(voxel_size=VS, keep_originals=False)
    check("originals deleted", not [n for n in names if n in bpy.data.objects])


def test_modifier_results():
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cube = bpy.context.object
    arr = cube.modifiers.new("Array", 'ARRAY')
    arr.count = 3
    bpy.ops.object.sts_voxel_join_remesh(voxel_size=VS, apply_modifiers=True)
    wide = bpy.context.active_object.dimensions.x
    check("array modifier result used (~3 wide)", wide > 2.5, f"{wide:.2f}")
    check("original keeps its modifier", len(cube.modifiers) == 1)

    bpy.ops.object.select_all(action='DESELECT')
    cube.hide_set(False)
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
    bpy.ops.object.sts_voxel_join_remesh(voxel_size=VS, apply_modifiers=False)
    narrow = bpy.context.active_object.dimensions.x
    check("without modifiers (~1 wide)", narrow < 1.5, f"{narrow:.2f}")


def test_modifier_mode_then_apply():
    scene_three()
    bpy.ops.object.sts_voxel_join_remesh(voxel_size=VS, remesh_mode='MODIFIER')
    res = bpy.context.active_object
    mod = ops_mod().find_voxel_modifier(res)
    check("voxel remesh modifier added", mod is not None and abs(mod.voxel_size - VS) < 1e-6)
    before = len(res.data.polygons)
    sets_before = face_sets(res)
    mod.voxel_size = VS * 1.5   # user tunes the preview
    r = bpy.ops.object.sts_voxel_apply_remesh()
    check("apply remesh finished", r == {'FINISHED'}, str(r))
    check("modifier removed", ops_mod().find_voxel_modifier(res) is None)
    check("mesh really remeshed", len(res.data.polygons) != before)
    check("used the tuned voxel size", abs(res.data.remesh_voxel_size - VS * 1.5) < 1e-6)
    check("face sets survive apply", len(sets_before) == 3 and face_sets(res) == sets_before,
          f"{sets_before} -> {face_sets(res)}")


def test_apply_without_modifier():
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.object
    obj.data.remesh_voxel_size = VS
    r = bpy.ops.object.sts_voxel_apply_remesh()
    check("apply with mesh values", r == {'FINISHED'} and len(obj.data.polygons) > 6)


def test_sculpt_dyntopo():
    scene_three()
    bpy.ops.object.sts_voxel_join_remesh(voxel_size=VS, final_mode='SCULPT', use_dyntopo=True)
    res = bpy.context.active_object
    check("Sculpt Mode", bpy.context.mode == 'SCULPT', bpy.context.mode)
    check("dyntopo on", res.use_dynamic_topology_sculpting)
    want = ops_mod().auto_dyntopo_resolution(VS)
    got = bpy.context.scene.tool_settings.sculpt.constant_detail_resolution
    check("resolution from voxel size", abs(got - want) < 1e-3, f"{got} vs {want}")
    check("face sets survive dyntopo", len(face_sets(res)) == 3, str(face_sets(res)))
    bpy.ops.object.mode_set(mode='OBJECT')


def test_sculpt_dyntopo_manual_resolution_and_modifier_mode():
    scene_three()
    bpy.ops.object.sts_voxel_join_remesh(voxel_size=VS, final_mode='SCULPT', use_dyntopo=True,
                                         remesh_mode='MODIFIER', dyntopo_auto_resolution=False,
                                         dyntopo_resolution=33.0)
    res = bpy.context.active_object
    got = bpy.context.scene.tool_settings.sculpt.constant_detail_resolution
    check("manual resolution kept", abs(got - 33.0) < 1e-3, str(got))
    check("dyntopo needs a real mesh: modifier applied", ops_mod().find_voxel_modifier(res) is None)
    bpy.ops.object.mode_set(mode='OBJECT')


def test_nothing_convertible():
    bpy.ops.object.empty_add()
    check("poll fails with only an empty", not bpy.ops.object.sts_voxel_join_remesh.poll())


def test_estimate_divisions():
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    a = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(4.0, 0, 0))
    b = bpy.context.object
    e = ops_mod().estimate_divisions
    check("one 2m cube at 0.01 -> 200", abs(e([a], 0.01) - 200) < 1e-6, str(e([a], 0.01)))
    check("whole selection counts (6m -> 600)", abs(e([a, b], 0.01) - 600) < 1e-6, str(e([a, b], 0.01)))


run([
    test_registered,
    test_no_underscore_properties,
    test_defaults,
    test_join_remesh_keeps_originals,
    test_delete_originals,
    test_modifier_results,
    test_modifier_mode_then_apply,
    test_apply_without_modifier,
    test_sculpt_dyntopo,
    test_sculpt_dyntopo_manual_resolution_and_modifier_mode,
    test_nothing_convertible,
    test_estimate_divisions,
])
