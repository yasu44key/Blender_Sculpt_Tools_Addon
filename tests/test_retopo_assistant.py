"""Spec for modules/retopo_assistant (the working part of the old Retopo Assistant v0.2,
plus the old "Reduce with Sharp Preserve"). Run through tests/run_tests.sh.

Model tab. A live Decimate modifier "STS Decimate" whose own values the panel shows (no
Scene copy of them), and ridge protection through the vertex group "Ridge":

  object.sts_retopo_add_decimate     add "STS Decimate" (COLLAPSE, ratio 0.5) to the active mesh
                                     (no second one when pressed again)
  object.sts_retopo_ridge_from_mask  sculpt mask -> vertex group "Ridge" (weights = mask),
                                     and the modifier uses it (added if missing)
  object.sts_retopo_ridge_from_angle angle (ANGLE, 30 deg): vertices on edges sharper than the
                                     angle (or on the mesh border) get weight 1, others 0
                                     -> "Ridge", and the modifier uses it
  object.sts_retopo_apply            apply "STS Decimate"
  object.sts_retopo_remove           remove "STS Decimate" (the Ridge group stays)
All work from Object or Sculpt Mode (the mode is kept). Nothing to do -> CANCELLED.

Decimate's vertex group means "decimate these FIRST" (weight 1 goes first): protecting the
Ridge group therefore needs invert_vertex_group on (factor 1). The old tool left invert off
by default, so its "protection" removed the ridges first.
"""

import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

MOD = "STS Decimate"


def dense_cube(cuts=8):
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


def evaluated_count(o):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return len(o.evaluated_get(dg).data.vertices)


def weight(vg, i):
    try:
        return vg.weight(i)
    except RuntimeError:
        return 0.0


def on_edge(v, tol=1e-4):
    return sum(1 for c in v.co if abs(abs(c) - 1.0) < tol) >= 2


def test_registered():
    check("module listed in MODULES", "retopo_assistant" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.retopo_assistant").META["tabs"] == ("Model",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_retopo_assistant", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    P = bpy.ops.object.sts_retopo_ridge_from_angle.get_rna_type().properties
    check("ridge angle: ANGLE, 30 deg", P["angle"].subtype == 'ANGLE' and abs(P["angle"].default - 0.5235988) < 1e-5)
    check("no Scene copy of the settings", "ra_settings" not in bpy.types.Scene.bl_rna.properties.keys())


def test_add_apply_remove():
    o = dense_cube()
    n0 = len(o.data.vertices)
    r = bpy.ops.object.sts_retopo_add_decimate()
    m = o.modifiers.get(MOD)
    check("add: finished, COLLAPSE 0.5", r == {'FINISHED'} and m is not None and m.decimate_type == 'COLLAPSE'
          and abs(m.ratio - 0.5) < 1e-6)
    bpy.ops.object.sts_retopo_add_decimate()
    check("add twice: one modifier", sum(1 for x in o.modifiers if x.type == 'DECIMATE') == 1)
    check("preview: fewer vertices", evaluated_count(o) < n0)
    r = bpy.ops.object.sts_retopo_apply()
    check("apply: finished, mesh reduced, modifier gone", r == {'FINISHED'} and len(o.data.vertices) < n0
          and o.modifiers.get(MOD) is None)
    check("apply again -> CANCELLED", bpy.ops.object.sts_retopo_apply() == {'CANCELLED'})
    bpy.ops.object.sts_retopo_add_decimate()
    check("remove: finished, modifier gone", bpy.ops.object.sts_retopo_remove() == {'FINISHED'} and o.modifiers.get(MOD) is None)


def test_ridge_from_angle():
    o = dense_cube()
    r = bpy.ops.object.sts_retopo_ridge_from_angle()
    vg = o.vertex_groups.get("Ridge")
    m = o.modifiers.get(MOD)
    check("angle: finished, group made, modifier added and using it",
          r == {'FINISHED'} and vg is not None and m is not None and m.vertex_group == "Ridge")
    check("angle: the group protects (inverted, factor 1)", m is not None and m.invert_vertex_group
          and abs(m.vertex_group_factor - 1.0) < 1e-6)
    if vg is None:
        return
    edge = [v.index for v in o.data.vertices if on_edge(v)]
    flat = [v.index for v in o.data.vertices if not on_edge(v)]
    check("angle: vertices on the cube's edges weight 1, flat ones 0",
          all(weight(vg, i) == 1.0 for i in edge) and all(weight(vg, i) == 0.0 for i in flat))


def test_ridge_on_a_thin_fin():
    """A thin wedge: its knife edge folds almost 180 deg (an abs(dot) test would call it flat)."""
    import bmesh
    bm = bmesh.new()
    rows = []
    for k in range(6):
        z = k / 5.0
        rows.append([bm.verts.new(p) for p in ((0, 0, z), (1, 0.02, z), (1, -0.02, z))])
    for k in range(5):
        a, b = rows[k], rows[k + 1]
        for i in range(3):
            j = (i + 1) % 3
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rows[0][::-1])
    bm.faces.new(rows[5])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Fin")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("Fin", me)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.sts_retopo_ridge_from_angle()
    vg = o.vertex_groups.get("Ridge")
    mid_fin = [v.index for v in me.vertices if v.co.x < 1e-6 and 0.1 < v.co.z < 0.9]
    check("angle: the knife edge of a thin fin is a ridge", vg is not None and mid_fin
          and all(weight(vg, i) == 1.0 for i in mid_fin))


def test_ridge_protects():
    def kept_on_edges(protect):
        bpy.ops.wm.read_homefile(use_empty=True)
        o = dense_cube(10)
        if protect:
            bpy.ops.object.sts_retopo_ridge_from_angle()
        else:
            bpy.ops.object.sts_retopo_add_decimate()
        m = o.modifiers[MOD]
        m.ratio = 0.15
        bpy.ops.object.sts_retopo_apply()
        return sum(1 for v in o.data.vertices if on_edge(v, 1e-3))
    plain, kept = kept_on_edges(False), kept_on_edges(True)
    check("protected ridges keep more of the cube's edges", kept > plain, f"{plain} -> {kept}")


def test_ridge_from_mask_and_sculpt_mode():
    o = dense_cube(4)
    m = o.data.attributes.new(".sculpt_mask", 'FLOAT', 'POINT')
    vals = [0.7 if v.co.z > 0.99 else 0.0 for v in o.data.vertices]
    m.data.foreach_set("value", vals)
    bpy.ops.object.mode_set(mode='SCULPT')
    r = bpy.ops.object.sts_retopo_ridge_from_mask()
    check("mask: finished in Sculpt Mode, still Sculpt Mode", r == {'FINISHED'} and bpy.context.mode == 'SCULPT', str(r))
    bpy.ops.object.mode_set(mode='OBJECT')
    vg = o.vertex_groups.get("Ridge")
    check("mask: Ridge = the mask", vg is not None and all(abs(weight(vg, i) - w) < 1e-6 for i, w in enumerate(vals)))
    check("mask: the modifier uses it", o.modifiers.get(MOD) is not None and o.modifiers[MOD].vertex_group == "Ridge")
    bpy.ops.mesh.primitive_cube_add(location=(5, 0, 0))
    check("no mask -> CANCELLED", bpy.ops.object.sts_retopo_ridge_from_mask() == {'CANCELLED'})


run([
    test_registered,
    test_add_apply_remove,
    test_ridge_from_angle,
    test_ridge_on_a_thin_fin,
    test_ridge_protects,
    test_ridge_from_mask_and_sculpt_mode,
])
