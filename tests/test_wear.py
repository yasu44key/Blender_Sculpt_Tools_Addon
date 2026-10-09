"""Spec for modules/wear (edge chips + surface erosion, one shot, F9). Run through tests/run_tests.sh.

  object.sts_wear  — Object Mode, every selected mesh (shared mesh data once):
    subdivide the whole mesh, then chip faces near sharp edges and erode other
    faces (more on faces pointing down in world space). Each hit face is inset
    and pushed in. Sizes are relative to each face (sqrt of its area), so the
    result scales with the object; the same seed gives the same result (the
    random generator restarts from the seed for each mesh).
    Refuses (CANCELLED, mesh untouched): faces x (subdivisions + 1)^2 over
    500,000; shape keys; nothing enabled; edge damage alone on a mesh with no
    edge sharper than sharp_angle; nothing selected.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def select_only(*objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def cube(size=2.0, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    return bpy.context.object


def volume(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


def closed(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ok = all(len(e.link_faces) == 2 for e in bm.edges)
    bm.free()
    return ok


def coords(o):
    return [tuple(round(c, 6) for c in v.co) for v in o.data.vertices]


def wear(**kw):
    return bpy.ops.object.sts_wear(**kw)


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "wear" in sys.modules[package()].MODULES)
    check("META tabs is ('Sculpt',)", submodule("modules.wear").META["tabs"] == ("Sculpt",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_wear", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)
    P = bpy.ops.object.sts_wear.get_rna_type().properties
    want = {"subdivisions", "seed", "randomness", "edge_damage", "sharp_angle", "edge_width", "chip_rate",
            "chip_depth", "erosion", "erosion_rate", "erosion_depth", "gravity_bias", "crumble", "crumble_strength"}
    check("operator properties", want <= set(P.keys()), str(sorted(want - set(P.keys()))))
    check("sharp_angle is an angle (default 30°)",
          P["sharp_angle"].subtype == 'ANGLE' and abs(P["sharp_angle"].default - math.radians(30)) < 1e-6)
    check("rates / depths are factors",
          all(P[k].subtype == 'FACTOR' for k in ("chip_rate", "erosion_rate", "gravity_bias", "randomness")))
    check("undoable / F9", {'REGISTER', 'UNDO'} <= set(bpy.types.OBJECT_OT_sts_wear.bl_options))
    check("no settings left on the Scene",
          not any(k.endswith("_props") and ("aging" in k or "erosion" in k or "edge_damage" in k)
                  for k in bpy.types.Scene.bl_rna.properties.keys()))


# ---------------------------------------------------------------- basic result

def test_cube_default():
    c = cube()
    v0 = volume(c)
    n0 = len(c.data.polygons)
    r = wear()
    check("finished", r == {'FINISHED'}, str(r))
    check("more faces", len(c.data.polygons) > n0)
    check("still closed (every edge has two faces)", closed(c))
    v1 = volume(c)
    check("material removed, normals outward (signed volume smaller but positive)", 0.7 * v0 < v1 < v0,
          f"{v0} -> {v1}")
    check("no new objects (no preview copies)", len(bpy.data.objects) == 1, str(len(bpy.data.objects)))
    check("object stays visible, selected, active",
          c.visible_get() and c.select_get() and bpy.context.view_layer.objects.active is c)


def test_only_the_inset_face_sinks():
    # The old versions pushed the rim faces that inset_individual returns, which moved the
    # shared grid points too. Every point of the subdivided grid must stay where it was.
    c = cube()
    wear(subdivisions=3, chip_rate=1.0, erosion_rate=0.5)
    have = {tuple(round(x, 5) for x in v.co) for v in c.data.vertices}
    steps = (-1.0, -0.5, 0.0, 0.5, 1.0)
    grid = {(x, y, z) for x in steps for y in steps for z in steps if 1.0 in (abs(x), abs(y), abs(z))}
    missing = [p for p in grid if tuple(round(q, 5) for q in p) not in have]
    check("grid points of the subdivided surface stay in place", not missing, f"{len(missing)} of {len(grid)} moved")


def test_same_seed_same_result():
    a = cube(loc=(-3, 0, 0))
    b = cube(loc=(3, 0, 0))
    select_only(a)
    wear(seed=7)
    select_only(b)
    wear(seed=7)
    check("same seed, same result", coords(a) == coords(b))
    c = cube(loc=(0, 3, 0))
    select_only(c)
    wear(seed=8)
    check("other seed, other result", coords(a) != coords(c))


def test_scale_invariant():
    small = cube(size=0.1, loc=(-3, 0, 0))
    big = cube(size=10.0, loc=(3, 0, 0))
    vs, vb = volume(small), volume(big)
    select_only(small)
    wear(seed=3)
    select_only(big)
    wear(seed=3)
    ls_, lb = 1 - volume(small) / vs, 1 - volume(big) / vb
    check("relative damage does not depend on the object size", lb > 0 and abs(ls_ - lb) < 1e-4 * max(lb, 1e-9),
          f"{ls_} vs {lb}")


def test_modifiers_untouched():
    c = cube()
    c.modifiers.new("Bevel", 'BEVEL')
    wear()
    check("modifiers unchanged (old Apply duplicated them)", [m.name for m in c.modifiers] == ["Bevel"],
          str([m.name for m in c.modifiers]))


# ---------------------------------------------------------------- edge damage

def test_edge_damage_stays_near_edges():
    c = cube()
    r = wear(edge_damage=True, erosion=False, crumble=False, subdivisions=5, edge_width=1, chip_rate=1.0)
    check("edge only: finished", r == {'FINISHED'}, str(r))
    me = c.data
    inner = [v for v in me.vertices if v.co.z > 0.5 and max(abs(v.co.x), abs(v.co.y)) < 0.3]
    check("edge only: middle of the top face untouched",
          inner and all(abs(v.co.z - 1.0) < 1e-6 for v in inner), str(len(inner)))
    near = [v for v in me.vertices if max(abs(v.co.x), abs(v.co.y), abs(v.co.z)) < 1.0 - 1e-4]
    check("edge only: chips cut in near the edges", len(near) > 20, str(len(near)))
    check("edge only: still closed", closed(c))


def test_no_sharp_edges():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
    s = bpy.context.object
    before = coords(s)
    r = wear(edge_damage=True, erosion=False, crumble=False)
    check("smooth mesh, edge damage only -> CANCELLED", r == {'CANCELLED'}, str(r))
    check("smooth mesh: unchanged", coords(s) == before)
    r = wear(edge_damage=True, erosion=False, crumble=False, sharp_angle=math.radians(5))
    check("lower angle finds the edges", r == {'FINISHED'}, str(r))


# ---------------------------------------------------------------- erosion

def _depressed_counts(o):
    """Vertices pushed in under the world top / bottom face (cube of size 2), away from the cube edges."""
    top = bottom = 0
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        if max(abs(w.x - o.matrix_world.translation.x), abs(w.y)) > 0.95:
            continue
        if 0.5 < w.z < 1.0 - 1e-4:
            top += 1
        elif -1.0 + 1e-4 < w.z < -0.5:
            bottom += 1
    return top, bottom


def _erode_gravity():
    return wear(edge_damage=False, erosion=True, crumble=False, subdivisions=8, erosion_rate=0.02,
                gravity_bias=1.0)


def test_gravity_world_down():
    c = cube()
    _erode_gravity()
    top, bottom = _depressed_counts(c)
    check("gravity: faces looking down erode more", bottom > top * 2 and bottom > 20, f"top {top} bottom {bottom}")
    d = cube(loc=(4, 0, 0))
    d.rotation_euler = (math.pi, 0, 0)
    bpy.context.view_layer.update()
    _erode_gravity()
    top, bottom = _depressed_counts(d)
    check("gravity is world down (upside-down object)", bottom > top * 2 and bottom > 20,
          f"top {top} bottom {bottom}")


def test_nothing_enabled():
    c = cube()
    before = coords(c)
    r = wear(edge_damage=False, erosion=False, crumble=False)
    check("nothing enabled -> CANCELLED", r == {'CANCELLED'} and coords(c) == before, str(r))


# ---------------------------------------------------------------- crumble (open borders)

def test_crumble_open_borders():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=8, y_subdivisions=8, size=2.0)
    g = bpy.context.object
    r = wear(edge_damage=False, erosion=False, crumble=True, crumble_strength=0.5, subdivisions=0)
    check("crumble: finished", r == {'FINISHED'}, str(r))
    # compare with a fresh grid (same vertex order: subdivisions=0 keeps the topology)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=8, y_subdivisions=8, size=2.0, location=(5, 0, 0))
    ref = bpy.context.object
    moved_border = sum(1 for a, b in zip(g.data.vertices, ref.data.vertices)
                       if max(abs(b.co.x), abs(b.co.y)) > 0.999 and (a.co - b.co).length > 1e-6)
    moved_inner = sum(1 for a, b in zip(g.data.vertices, ref.data.vertices)
                      if max(abs(b.co.x), abs(b.co.y)) < 0.999 and (a.co - b.co).length > 1e-6)
    check("crumble: open border vertices move", moved_border > 5, str(moved_border))
    check("crumble: inner vertices stay", moved_inner == 0, str(moved_inner))


# ---------------------------------------------------------------- targets / refusals

def test_several_objects_shared_data_once():
    a = cube(loc=(-3, 0, 0))
    b = bpy.data.objects.new("Linked", a.data)
    bpy.context.scene.collection.objects.link(b)
    b.location = (3, 0, 0)
    c = cube(loc=(0, 4, 0))
    select_only(a, b, c)
    r = wear(seed=1)
    check("several: finished", r == {'FINISHED'}, str(r))
    check("several: every selected mesh changed", len(a.data.polygons) > 6 and len(c.data.polygons) > 6)
    ref = cube(loc=(0, -4, 0))
    select_only(ref)
    wear(seed=1)
    check("shared mesh data worn once, seed restarts per mesh (same as a single run)", coords(a) == coords(ref))


def test_refusals():
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6)
    big = bpy.context.object
    before = len(big.data.polygons)
    r = wear(subdivisions=6)
    check("too heavy -> CANCELLED before doing anything", r == {'CANCELLED'} and len(big.data.polygons) == before,
          str(r))
    bpy.ops.wm.read_homefile(use_empty=True)
    c = cube()
    c.shape_key_add(name="Basis")
    r = wear()
    check("shape keys -> CANCELLED", r == {'CANCELLED'}, str(r))
    bpy.ops.wm.read_homefile(use_empty=True)
    c = cube()
    bpy.ops.object.mode_set(mode='EDIT')
    check("Edit Mode: not available (poll)", not bpy.ops.object.sts_wear.poll())
    bpy.ops.object.mode_set(mode='OBJECT')
    c.select_set(False)
    check("nothing selected -> CANCELLED", wear() == {'CANCELLED'})


run([
    test_registered,
    test_cube_default,
    test_only_the_inset_face_sinks,
    test_same_seed_same_result,
    test_scale_invariant,
    test_modifiers_untouched,
    test_edge_damage_stays_near_edges,
    test_no_sharp_edges,
    test_gravity_world_down,
    test_nothing_enabled,
    test_crumble_open_borders,
    test_several_objects_shared_data_once,
    test_refusals,
])
