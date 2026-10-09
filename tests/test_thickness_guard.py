"""Spec for modules/thickness_guard — part 1 (no mouse). Run through tests/run_tests.sh.

Wall thickness for 3D printing. Object or Sculpt Mode on the active mesh (Edit Mode for
selecting); the mode is restored afterwards.

  object.sts_thickness_bake     max_distance (length)
      For every vertex a ray goes INTO the mesh (along -normal, from just inside the
      surface); the distance to the first hit is its thickness, stored in the point float
      attribute "sts_thickness" (no hit / farther than max_distance -> max_distance).
  object.sts_thickness_select   min_thickness (length)
      Edit Mode: select exactly the vertices thinner than min_thickness.
      Object / Sculpt Mode: write the vertex group "Thin" (1.0 thin, 0.0 otherwise).
      Bakes first when there is no "sts_thickness".
  object.sts_thickness_fix      min_thickness (length)
      Re-bakes, then pushes every vertex thinner than min_thickness outward along its
      normal by half the missing thickness (both walls of a thin plate move, so the plate
      ends at min_thickness). Thick parts are not touched.
  object.sts_thickness_to_mask  thin_distance, thick_distance (lengths), invert
      Sculpt mask (.sculpt_mask) from the thickness: 0 at or below thin_distance, 1 at or
      above thick_distance, linear between (invert flips it). Bakes first when needed.

The old Min Thickness Guard defined register() twice (the mask tools never registered) and
called Mesh.calc_normals() (gone since 4.1).
"""

import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

PLATE = 0.05


def plate_and_block():
    """One mesh: a thin plate (2 x 2 x 0.05, subdivided) at x < 0 and a 1 m block at x > 2."""
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(2.0, 2.0, PLATE), verts=r["verts"])
    bmesh.ops.translate(bm, vec=(-1.5, 0, 0), verts=r["verts"])
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if e.verts[0] in set(r["verts"])], cuts=4,
                              use_grid_fill=True)
    plate = set(bm.verts)
    r2 = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.translate(bm, vec=(3.0, 0, 0), verts=r2["verts"])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("PB")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("PB", me)
    bpy.context.scene.collection.objects.link(o)
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    return o


def thickness(o):
    a = o.data.attributes.get("sts_thickness")
    return [d.value for d in a.data] if a else None


def plate_inner(o):
    """Plate vertices on the top / bottom faces away from the plate's edges (normals +-z)."""
    return [i for i, v in enumerate(o.data.vertices) if v.co.x < 0 and abs(v.co.x + 1.5) < 0.79 and abs(v.co.y) < 0.79]


def block(o):
    return [i for i, v in enumerate(o.data.vertices) if v.co.x > 2.0]


def test_registered():
    check("module listed in MODULES", "thickness_guard" in sys.modules[package()].MODULES)
    check("META tabs is ('Sculpt',)", submodule("modules.thickness_guard").META["tabs"] == ("Sculpt",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_thickness_guard", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)
    for op, props in (("sts_thickness_bake", ("max_distance",)), ("sts_thickness_select", ("min_thickness",)),
                      ("sts_thickness_fix", ("min_thickness",)),
                      ("sts_thickness_to_mask", ("thin_distance", "thick_distance"))):
        P = getattr(bpy.ops.object, op).get_rna_type().properties
        check(f"{op}: lengths", all(k in P and P[k].unit == 'LENGTH' for k in props))
        check(f"{op}: undoable", {'REGISTER', 'UNDO'} <= set(getattr(bpy.types, "OBJECT_OT_" + op).bl_options))


def test_bake():
    o = plate_and_block()
    r = bpy.ops.object.sts_thickness_bake(max_distance=5.0)
    t = thickness(o)
    check("bake: finished, attribute on the points", r == {'FINISHED'} and t is not None and len(t) == len(o.data.vertices))
    if t is None:
        return
    inner = plate_inner(o)
    check("bake: the plate measures its thickness", inner and all(abs(t[i] - PLATE) < 1e-4 for i in inner),
          str(sorted({round(t[i], 4) for i in inner})[:5]))
    check("bake: the block is thick (>= 0.9)", all(t[i] > 0.9 for i in block(o)))
    bpy.ops.object.sts_thickness_bake(max_distance=0.5)
    t = thickness(o)
    check("bake: farther than max_distance -> max_distance", all(abs(t[i] - 0.5) < 1e-6 for i in block(o)))


def test_select_and_group():
    o = plate_and_block()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    r = bpy.ops.object.sts_thickness_select(min_thickness=0.2)
    check("select (Edit Mode): finished, still Edit Mode", r == {'FINISHED'} and bpy.context.mode == 'EDIT_MESH', str(r))
    bpy.ops.object.mode_set(mode='OBJECT')
    sel = [v.select for v in o.data.vertices]
    check("select: the plate's top / bottom vertices, no block vertex",
          all(sel[i] for i in plate_inner(o)) and not any(sel[i] for i in block(o)))
    bpy.ops.wm.read_homefile(use_empty=True)
    o = plate_and_block()
    r = bpy.ops.object.sts_thickness_select(min_thickness=0.2)
    g = o.vertex_groups.get("Thin")
    check("select (Object Mode): vertex group Thin", r == {'FINISHED'} and g is not None)
    if g:
        def w(i):
            try:
                return g.weight(i)
            except RuntimeError:
                return 0.0
        check("Thin group: 1 on the plate, 0 on the block",
              all(w(i) == 1.0 for i in plate_inner(o)) and all(w(i) == 0.0 for i in block(o)))


def test_fix():
    o = plate_and_block()
    before_block = [o.data.vertices[i].co.copy() for i in block(o)]
    mode_before = bpy.context.mode
    r = bpy.ops.object.sts_thickness_fix(min_thickness=0.2)
    check("fix: finished, mode kept", r == {'FINISHED'} and bpy.context.mode == mode_before, str(r))
    bpy.ops.object.sts_thickness_bake(max_distance=5.0)
    t = thickness(o)
    inner = plate_inner(o)
    check("fix: the plate is now min_thickness thick (not double)", all(abs(t[i] - 0.2) < 0.01 for i in inner),
          str(sorted({round(t[i], 3) for i in inner})[:4]))
    check("fix: the block is untouched",
          all((o.data.vertices[i].co - c).length < 1e-9 for i, c in zip(block(o), before_block)))


def test_to_mask_and_sculpt_mode():
    o = plate_and_block()
    bpy.ops.object.mode_set(mode='SCULPT')
    r = bpy.ops.object.sts_thickness_to_mask(thin_distance=0.1, thick_distance=0.5)
    check("mask: finished in Sculpt Mode, still Sculpt Mode", r == {'FINISHED'} and bpy.context.mode == 'SCULPT', str(r))
    bpy.ops.object.mode_set(mode='OBJECT')
    m = o.data.attributes.get(".sculpt_mask")
    vals = [d.value for d in m.data] if m else []
    check("mask: 0 on the plate, 1 on the block",
          vals and all(vals[i] == 0.0 for i in plate_inner(o)) and all(abs(vals[i] - 1.0) < 1e-6 for i in block(o)))
    bpy.ops.object.sts_thickness_to_mask(thin_distance=0.1, thick_distance=0.5, invert=True)
    vals = [d.value for d in o.data.attributes[".sculpt_mask"].data]
    check("mask invert: 1 on the plate, 0 on the block",
          all(abs(vals[i] - 1.0) < 1e-6 for i in plate_inner(o)) and all(vals[i] == 0.0 for i in block(o)))
    bpy.ops.object.sts_thickness_bake(max_distance=5.0)
    bpy.ops.object.sts_thickness_to_mask(thin_distance=0.0, thick_distance=2.0)
    vals = [d.value for d in o.data.attributes[".sculpt_mask"].data]
    t = thickness(o)
    i = block(o)[0]
    check("mask: linear in between", abs(vals[i] - min(1.0, t[i] / 2.0)) < 1e-4, f"{vals[i]} {t[i]}")


def test_refusals():
    bpy.ops.object.empty_add()
    check("not a mesh -> not available (poll)", not bpy.ops.object.sts_thickness_bake.poll())
    bpy.ops.mesh.primitive_plane_add()
    r = bpy.ops.object.sts_thickness_fix(min_thickness=0.2)
    check("open plane (nothing hit) -> nothing thin, FINISHED without change",
          r in ({'FINISHED'}, {'CANCELLED'}) and all(abs(v.co.z) < 1e-9 for v in bpy.context.object.data.vertices))


run([
    test_registered,
    test_bake,
    test_select_and_group,
    test_fix,
    test_to_mask_and_sculpt_mode,
    test_refusals,
])
