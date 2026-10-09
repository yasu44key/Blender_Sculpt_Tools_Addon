"""Spec for modules/point_smooth — part 1: object.sts_point_smooth. Run through tests/run_tests.sh.

Edit Mode on meshes, curves (Bezier / NURBS / Poly) and NURBS surfaces; every object in
Edit Mode is processed (not only the active one). The selection is split into pieces and
each piece is handled on its own:

  mesh     connected pieces of selected vertices (through edges between selected vertices)
           - open chain  -> straighten: ends stay, the rest evenly spaced on the line between them
           - closed loop -> even spacing along the loop + relax (smooth the shape); the loop keeps
                            its size (mean distance from its centre) and every iteration counts
           - anything else (2D) -> Laplacian relax; fix_boundary keeps the outer vertices
                            (touching unselected ones or on the mesh border); tangent_smooth
                            moves only along the surface (no shrinking toward the inside)
  curve    runs of consecutive selected points of each spline (a run of fewer than 3 is left)
           - open run -> straighten (ends stay); Bezier handles move with their point and point
             along the line; a fully selected cyclic spline -> loop (as above)
  surface  NURBS: one selected row / column -> straighten; 2D -> Laplacian (as mesh)

  The old 'LINE' mode is gone: with the pieces above it would do exactly what AUTO does (its only
  own effect was wrecking 2D mesh selections). strength 0..1, iterations 1..100.
  Too few points everywhere -> CANCELLED.
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def mesh_obj(verts, edges=(), faces=(), name="M", loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], list(edges), list(faces))
    o = bpy.data.objects.new(name, me)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o


def edit(*objs, select_all=True):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    if select_all:
        bpy.ops.mesh.select_all(action='SELECT') if objs[0].type == 'MESH' else bpy.ops.curve.select_all(action='SELECT')


def obj_mode():
    bpy.ops.object.mode_set(mode='OBJECT')


def smooth(**kw):
    return bpy.ops.object.sts_point_smooth(**kw)


def zigzag(n=7, x0=0.0, y=0.0):
    return [Vector((x0 + i, y, 0.4 if i % 2 else 0.0)) for i in range(n)]


def chain_edges(n, closed=False, base=0):
    e = [(base + i, base + i + 1) for i in range(n - 1)]
    if closed:
        e.append((base + n - 1, base))
    return e


def bumpy_circle(n=16, cx=0.0, seed=1):
    rng = random.Random(seed)
    return [Vector((cx + math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), rng.uniform(-0.3, 0.3)))
            for i in range(n)]


def straight_and_even(pts, a, b, tol=1e-4):
    n = len(pts) - 1
    return all((p - a.lerp(b, i / n)).length < tol for i, p in enumerate(pts))


def z_spread(pts):
    zs = [p.z for p in pts]
    m = sum(zs) / len(zs)
    return math.sqrt(sum((z - m) ** 2 for z in zs) / len(zs))


def mean_radius(pts):
    c = sum(pts, Vector()) / len(pts)
    return sum(((p - c).xy).length for p in pts) / len(pts)


def spacing_spread(pts):
    d = [(pts[(i + 1) % len(pts)] - pts[i]).length for i in range(len(pts))]
    m = sum(d) / len(d)
    return max(abs(x - m) for x in d) / m


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "point_smooth" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.point_smooth").META["tabs"] == ("Model",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_point_smooth", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    P = bpy.ops.object.sts_point_smooth.get_rna_type().properties
    check("properties", {"strength", "iterations", "fix_boundary", "tangent_smooth",
                         "auto_handle_length"} <= set(P.keys()) and "mode" not in P.keys())
    check("strength is a factor (1.0)", P["strength"].subtype == 'FACTOR' and P["strength"].default == 1.0)
    check("English names (JA through the translation table)", P["strength"].name == "Strength")
    check("undoable / F9", {'REGISTER', 'UNDO'} <= set(bpy.types.OBJECT_OT_sts_point_smooth.bl_options))
    check("no old scene.pointsmooth", "pointsmooth" not in bpy.types.Scene.bl_rna.properties.keys())


# ---------------------------------------------------------------- mesh

def test_mesh_two_chains():
    a, b = zigzag(), zigzag(y=3.0)
    o = mesh_obj(a + b, chain_edges(7) + chain_edges(7, base=7))
    edit(o)
    r = smooth()
    obj_mode()
    v = [x.co.copy() for x in o.data.vertices]
    check("mesh chain: finished", r == {'FINISHED'}, str(r))
    check("mesh chain: straight and even, ends fixed", straight_and_even(v[:7], a[0], a[-1]))
    check("mesh: the second chain too (old: only one piece)", straight_and_even(v[7:], b[0], b[-1]))


def test_mesh_loops():
    a, b = bumpy_circle(seed=1), bumpy_circle(cx=4.0, seed=2)
    o = mesh_obj(a + b, chain_edges(16, True) + chain_edges(16, True, base=16))
    edit(o)
    smooth(iterations=1)
    obj_mode()
    v1 = [x.co.copy() for x in o.data.vertices]
    bpy.ops.wm.read_homefile(use_empty=True)
    o = mesh_obj(a + b, chain_edges(16, True) + chain_edges(16, True, base=16))
    edit(o)
    smooth(iterations=8)
    obj_mode()
    v8 = [x.co.copy() for x in o.data.vertices]
    check("loop: bumps smoothed", z_spread(v1[:16]) < z_spread(a) * 0.8, f"{z_spread(a)} -> {z_spread(v1[:16])}")
    check("loop: more iterations, smoother (old: no change after the first)",
          z_spread(v8[:16]) < z_spread(v1[:16]) * 0.8, f"{z_spread(v1[:16])} -> {z_spread(v8[:16])}")
    check("loop: keeps its size", abs(mean_radius(v8[:16]) - mean_radius(a)) < 0.05 * mean_radius(a),
          f"{mean_radius(a)} -> {mean_radius(v8[:16])}")
    check("loop: evenly spaced", spacing_spread(v8[:16]) < 0.1, str(spacing_spread(v8[:16])))
    check("loop: the second loop too", z_spread(v8[16:]) < z_spread(b) * 0.5)


def bumpy_grid(n=5, seed=3):
    rng = random.Random(seed)
    verts = []
    for j in range(n):
        for i in range(n):
            inner = 0 < i < n - 1 and 0 < j < n - 1
            verts.append(Vector((i * 0.5, j * 0.5, rng.uniform(-0.3, 0.3) if inner else 0.0)))
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(n - 1) for i in range(n - 1)]
    return verts, faces


def test_mesh_plane():
    verts, faces = bumpy_grid()
    o = mesh_obj(verts, faces=faces)
    edit(o)
    smooth(iterations=5)
    obj_mode()
    v = [x.co.copy() for x in o.data.vertices]
    border = [i for i in range(25) if i % 5 in (0, 4) or i // 5 in (0, 4)]
    inner = [i for i in range(25) if i not in border]
    check("plane: border fixed (fix_boundary)", all((v[i] - verts[i]).length < 1e-6 for i in border))
    check("plane: bumps relaxed", max(abs(v[i].z) for i in inner) < max(abs(verts[i].z) for i in inner) * 0.5)


def test_plane_is_never_lined_up():
    verts, faces = bumpy_grid()
    o = mesh_obj(verts, faces=faces)
    edit(o)
    r = smooth(iterations=5)
    obj_mode()
    v = [x.co.copy() for x in o.data.vertices]
    xs = {round(p.x, 3) for p in v}
    ys = {round(p.y, 3) for p in v}
    check("2D selection: relaxed, never lined up (old LINE mode wrecked it)",
          r == {'FINISHED'} and len(xs) <= 7 and len(ys) <= 7 and
          all(abs(v[i].x - verts[i].x) < 0.2 and abs(v[i].y - verts[i].y) < 0.2 for i in range(25)),
          f"{len(xs)} x {len(ys)}")


def test_mesh_fix_boundary_off_and_strength():
    verts, faces = bumpy_grid()
    o = mesh_obj(verts, faces=faces)
    edit(o)
    smooth(fix_boundary=False, iterations=3)
    obj_mode()
    check("fix_boundary off: the border moves too",
          any((o.data.vertices[i].co - verts[i]).length > 1e-4 for i in (0, 4, 20, 24)))
    bpy.ops.wm.read_homefile(use_empty=True)
    o = mesh_obj(verts, faces=faces)
    edit(o)
    smooth(strength=0.0)
    obj_mode()
    check("strength 0: nothing moves", all((o.data.vertices[i].co - verts[i]).length < 1e-6 for i in range(25)))


def test_tangent_smooth():
    def patch():
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16)
        s = bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(s.data)
        rng = random.Random(5)
        for v in bm.verts:
            v.select_set(v.co.z > 0.3)
            if 0.45 < v.co.z < 0.95:
                v.co *= 1.0 + rng.uniform(-0.03, 0.03)
        bm.select_flush(True)
        bmesh.update_edit_mesh(s.data)
        return s
    s = patch()
    smooth(tangent_smooth=True, iterations=10)
    obj_mode()
    rt = [v.co.length for v in s.data.vertices if 0.45 < v.co.z < 0.95]
    bpy.ops.wm.read_homefile(use_empty=True)
    s = patch()
    smooth(tangent_smooth=False, iterations=10)
    obj_mode()
    rf = [v.co.length for v in s.data.vertices if 0.45 < v.co.z < 0.95]
    dev_t = sum(abs(r - 1.0) for r in rt) / len(rt)
    dev_f = sum(abs(r - 1.0) for r in rf) / len(rf)
    check("tangent_smooth: stays on the sphere (less shrinking than plain relax)", dev_t < dev_f * 0.7,
          f"{dev_t} vs {dev_f}")


def test_multi_object_edit():
    a = mesh_obj(zigzag(), chain_edges(7), name="A")
    b = mesh_obj(zigzag(), chain_edges(7), name="B", loc=(0, 5, 0))
    edit(a, b)
    bpy.ops.mesh.select_all(action='SELECT')
    smooth()
    obj_mode()
    za = max(abs(v.co.z) for v in a.data.vertices)
    zb = max(abs(v.co.z) for v in b.data.vertices)
    check("every object in Edit Mode is processed (old: active only)", za < 1e-6 and zb < 1e-6, f"{za} {zb}")


# ---------------------------------------------------------------- curves

def bezier_obj(pts, cyclic=False, kind='BEZIER', name="C"):
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new(kind)
    if kind == 'BEZIER':
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = 'FREE'
            bp.handle_left = p + Vector((-0.2, 0.1, 0))
            bp.handle_right = p + Vector((0.2, -0.1, 0))
    else:
        sp.points.add(len(pts) - 1)
        for pt, p in zip(sp.points, pts):
            pt.co = (p.x, p.y, p.z, 1.0)
    sp.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    return o


def curve_pts(o):
    sp = o.data.splines[0]
    if sp.type == 'BEZIER':
        return [bp.co.copy() for bp in sp.bezier_points]
    return [Vector(p.co[:3]) for p in sp.points]


def test_bezier_straighten_and_handles():
    pts = zigzag()
    o = bezier_obj(pts)
    edit(o)
    r = smooth()
    obj_mode()
    got = curve_pts(o)
    check("bezier: finished, straight and even, ends fixed", r == {'FINISHED'} and straight_and_even(got, pts[0], pts[-1]))
    mid = o.data.splines[0].bezier_points[3]
    d = (mid.handle_right - mid.co).normalized()
    check("bezier: handles point along the line", abs(abs(d.x) - 1.0) < 1e-4, str(d))


def test_bezier_separate_runs():
    pts = zigzag(9)
    o = bezier_obj(pts)
    edit(o, select_all=False)
    bpy.ops.curve.select_all(action='DESELECT')
    for i, bp in enumerate(o.data.splines[0].bezier_points):
        bp.select_control_point = i in (0, 1, 2, 3, 5, 6, 7, 8)
    smooth()
    obj_mode()
    got = curve_pts(o)
    check("curve: each run of selected points on its own (old: one run across the gap)",
          straight_and_even(got[0:4], pts[0], pts[3]) and straight_and_even(got[5:9], pts[5], pts[8])
          and (got[4] - pts[4]).length < 1e-6)


def test_nurbs_and_poly():
    for kind in ('NURBS', 'POLY'):
        bpy.ops.wm.read_homefile(use_empty=True)
        pts = zigzag()
        o = bezier_obj(pts, kind=kind)
        edit(o)
        r = smooth()
        obj_mode()
        check(f"{kind} curve: straightened", r == {'FINISHED'} and straight_and_even(curve_pts(o), pts[0], pts[-1]))


def test_cyclic_curve_loop():
    pts = bumpy_circle()
    o = bezier_obj(pts, cyclic=True)
    edit(o)
    smooth(iterations=8)
    obj_mode()
    got = curve_pts(o)
    check("cyclic curve: smoothed, keeps its size",
          z_spread(got) < z_spread(pts) * 0.5 and abs(mean_radius(got) - mean_radius(pts)) < 0.05 * mean_radius(pts),
          f"{z_spread(pts)} -> {z_spread(got)}, r {mean_radius(got)}")


# ---------------------------------------------------------------- surfaces

def surface_obj():
    bpy.ops.surface.primitive_nurbs_surface_surface_add(radius=1.0)
    o = bpy.context.object
    bpy.ops.object.mode_set(mode='OBJECT')
    sp = o.data.splines[0]
    nu = sp.point_count_u
    for v in range(sp.point_count_v):
        for u in range(nu):
            p = sp.points[v * nu + u]
            p.co = (u * 1.0, v * 1.0, 0.0, 1.0)
    sp.points[1 * nu + 1].co = (1.0, 1.0, 0.8, 1.0)          # an interior bump
    sp.points[2 * nu + 2].co = (2.0, 2.0, -0.6, 1.0)
    return o, nu, sp.point_count_v


def test_surface_plane_and_row():
    o, nu, nv = surface_obj()
    edit(o)
    smooth(iterations=5)
    obj_mode()
    sp = o.data.splines[0]
    edge = [(u, v) for v in range(nv) for u in range(nu) if u in (0, nu - 1) or v in (0, nv - 1)]
    check("surface 2D: grid border fixed", all(abs(sp.points[v * nu + u].co[2]) < 1e-6 for u, v in edge))
    check("surface 2D: bumps relaxed", abs(sp.points[1 * nu + 1].co[2]) < 0.4 and abs(sp.points[2 * nu + 2].co[2]) < 0.3)
    bpy.ops.wm.read_homefile(use_empty=True)
    o, nu, nv = surface_obj()
    edit(o, select_all=False)
    bpy.ops.curve.select_all(action='DESELECT')
    sp = o.data.splines[0]
    for u in range(nu):
        sp.points[1 * nu + u].select = True
    smooth()
    obj_mode()
    sp = o.data.splines[0]
    check("surface row: straightened", all(abs(sp.points[1 * nu + u].co[2]) < 1e-6 for u in range(nu)))
    check("surface row: other rows untouched", abs(sp.points[2 * nu + 2].co[2] + 0.6) < 1e-6)


# ---------------------------------------------------------------- refusals

def test_refusals():
    o = mesh_obj(zigzag(2), chain_edges(2))
    edit(o)
    check("too few points -> CANCELLED", smooth() == {'CANCELLED'})
    obj_mode()
    check("Object Mode: not available (poll)", not bpy.ops.object.sts_point_smooth.poll())


run([
    test_registered,
    test_mesh_two_chains,
    test_mesh_loops,
    test_mesh_plane,
    test_plane_is_never_lined_up,
    test_mesh_fix_boundary_off_and_strength,
    test_tangent_smooth,
    test_multi_object_edit,
    test_bezier_straighten_and_handles,
    test_bezier_separate_runs,
    test_nurbs_and_poly,
    test_cyclic_curve_loop,
    test_surface_plane_and_row,
    test_refusals,
])
