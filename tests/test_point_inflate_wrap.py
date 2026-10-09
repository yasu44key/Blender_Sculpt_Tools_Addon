"""Spec for modules/point_smooth — part 2: inflate and wrap. Run through tests/run_tests.sh.

Edit Mode, every object in Edit Mode, mesh / curve / NURBS surface like part 1.

  object.sts_point_inflate   amount (length, signed: negative = inward), fix_boundary
      mesh / surface: every selected point moves along its normal by amount x w, where
        w = sin(pi/2 * d / dmax), d = steps (edges / grid steps) from the boundary of the
        selection (points touching unselected ones, or on the mesh / grid border) and dmax the
        largest d — the boundary stays (w = 0), the middle moves the full amount.
        fix_boundary off -> w = 1 everywhere.
      curve: each run of selected points (3+) moves along the normal of the run's plane
        (from the cross products of its segments) by amount x sin(pi x t), t = 0..1 along the
        run (ends stay); fix_boundary off -> the full amount everywhere. A straight run has
        no plane -> skipped.
  object.sts_point_wrap      strength, offset (length), iterations, fix_boundary
      mesh / surface: every selected point moves toward the closest point on the target
        mesh's EVALUATED surface (modifiers included) + offset along that surface's normal;
        fix_boundary keeps the boundary points as above. The target is
        scene.sts_point_smooth.wrap_target (a mesh, not the edited object itself).
  Nothing to do / no target / target is the object -> CANCELLED.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def mesh_grid(n=5, size=1.0, z=0.0, name="G"):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=n - 1, y_subdivisions=n - 1, size=size, location=(0, 0, z))
    o = bpy.context.object
    o.name = name
    return o


def edit_all(*objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    if objs[0].type == 'MESH':
        bpy.ops.mesh.select_all(action='SELECT')
    else:
        bpy.ops.curve.select_all(action='SELECT')


def obj_mode():
    bpy.ops.object.mode_set(mode='OBJECT')


def test_registered():
    for op in ("sts_point_inflate", "sts_point_wrap"):
        check(f"operator object.{op}", hasattr(bpy.types, "OBJECT_OT_" + op))
    P = bpy.ops.object.sts_point_inflate.get_rna_type().properties
    check("inflate: amount is a length, fix_boundary", P["amount"].unit == 'LENGTH' and "fix_boundary" in P)
    P = bpy.ops.object.sts_point_wrap.get_rna_type().properties
    check("wrap: strength (factor), offset (length), iterations, fix_boundary",
          P["strength"].subtype == 'FACTOR' and P["offset"].unit == 'LENGTH' and "iterations" in P and "fix_boundary" in P)
    s = bpy.types.Scene.bl_rna.properties.get("sts_point_smooth")
    check("wrap target in scene.sts_point_smooth.wrap_target",
          s is not None and bpy.context.scene.sts_point_smooth.bl_rna.properties["wrap_target"].fixed_type.identifier == 'Object')


def test_inflate_mesh():
    o = mesh_grid(5)
    edit_all(o)
    r = bpy.ops.object.sts_point_inflate(amount=0.4)
    obj_mode()
    check("inflate: finished", r == {'FINISHED'}, str(r))
    zs = {(round(v.co.x, 3), round(v.co.y, 3)): v.co.z for v in o.data.vertices}
    border = [z for (x, y), z in zs.items() if max(abs(x), abs(y)) > 0.49]
    check("inflate: the border stays", all(abs(z) < 1e-6 for z in border))
    check("inflate: the middle moves the full amount", abs(zs[(0.0, 0.0)] - 0.4) < 1e-5, str(zs[(0.0, 0.0)]))
    check("inflate: one step in, sin(pi/4) of it", abs(zs[(0.25, 0.0)] - 0.4 * math.sin(math.pi / 4)) < 1e-5,
          str(zs[(0.25, 0.0)]))
    bpy.ops.wm.read_homefile(use_empty=True)
    o = mesh_grid(5)
    edit_all(o)
    bpy.ops.object.sts_point_inflate(amount=-0.3, fix_boundary=False)
    obj_mode()
    check("inflate: fix_boundary off and negative -> every vertex 0.3 down",
          all(abs(v.co.z + 0.3) < 1e-5 for v in o.data.vertices))


def test_inflate_curve():
    cd = bpy.data.curves.new("C", 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new('BEZIER')
    sp.bezier_points.add(6)
    for i, bp in enumerate(sp.bezier_points):
        a = math.pi * i / 6
        bp.co = (math.cos(a), math.sin(a), 0.0)
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    o = bpy.data.objects.new("C", cd)
    bpy.context.scene.collection.objects.link(o)
    edit_all(o)
    r = bpy.ops.object.sts_point_inflate(amount=0.5)
    obj_mode()
    pts = [bp.co.copy() for bp in o.data.splines[0].bezier_points]
    check("inflate curve: finished", r == {'FINISHED'}, str(r))
    check("inflate curve: ends stay", abs(pts[0].z) < 1e-6 and abs(pts[-1].z) < 1e-6)
    check("inflate curve: the middle point moves 0.5 off the arc's plane", abs(abs(pts[3].z) - 0.5) < 1e-5, str(pts[3]))
    check("inflate curve: in the plane it does not move", abs(pts[3].x) < 1e-6 and abs(pts[3].y - 1.0) < 1e-6)


def test_inflate_surface_and_straight_curve():
    bpy.ops.surface.primitive_nurbs_surface_surface_add(radius=1.0)
    s = bpy.context.object
    bpy.ops.object.mode_set(mode='OBJECT')
    sp = s.data.splines[0]
    nu, nv = sp.point_count_u, sp.point_count_v
    for v in range(nv):
        for u in range(nu):
            sp.points[v * nu + u].co = (u * 1.0, v * 1.0, 0.0, 1.0)
    edit_all(s)
    r = bpy.ops.object.sts_point_inflate(amount=0.2)
    obj_mode()
    sp = s.data.splines[0]
    border = [sp.points[v * nu + u].co[2] for v in range(nv) for u in range(nu) if u in (0, nu - 1) or v in (0, nv - 1)]
    inner = [sp.points[v * nu + u].co[2] for v in range(1, nv - 1) for u in range(1, nu - 1)]
    check("inflate surface: border stays, inside moves 0.2 (same side)", r == {'FINISHED'}
          and all(abs(z) < 1e-6 for z in border) and all(abs(abs(z) - 0.2) < 1e-5 for z in inner)
          and len({z > 0 for z in inner}) == 1, f"{inner}")
    bpy.ops.wm.read_homefile(use_empty=True)
    cd = bpy.data.curves.new("L", 'CURVE')
    sp = cd.splines.new('POLY')
    sp.points.add(4)
    for i, p in enumerate(sp.points):
        p.co = (i * 1.0, 0, 0, 1)
    o = bpy.data.objects.new("L", cd)
    bpy.context.scene.collection.objects.link(o)
    edit_all(o)
    check("inflate: a straight run has no plane -> CANCELLED", bpy.ops.object.sts_point_inflate(amount=0.2) == {'CANCELLED'})


def sphere_target(r=1.0, subsurf=False):
    if subsurf:
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        t = bpy.context.object
        m = t.modifiers.new("S", 'SUBSURF')
        m.levels = 3
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=64, ring_count=32)
        t = bpy.context.object
    t.name = "Target"
    return t


def test_wrap_mesh():
    t = sphere_target()
    o = mesh_grid(7, size=1.2, z=2.0)
    bpy.context.scene.sts_point_smooth.wrap_target = t
    edit_all(o)
    r = bpy.ops.object.sts_point_wrap(fix_boundary=False, offset=0.1)
    obj_mode()
    check("wrap: finished", r == {'FINISHED'}, str(r))
    dists = [(o.matrix_world @ v.co).length for v in o.data.vertices]
    check("wrap: every vertex on the sphere + offset", all(abs(d - 1.1) < 0.01 for d in dists), f"{min(dists)}..{max(dists)}")
    bpy.ops.wm.read_homefile(use_empty=True)
    t = sphere_target()
    o = mesh_grid(7, size=1.2, z=2.0)
    bpy.context.scene.sts_point_smooth.wrap_target = t
    edit_all(o)
    bpy.ops.object.sts_point_wrap(fix_boundary=True, strength=0.5)
    obj_mode()
    zs = {(round(v.co.x, 3), round(v.co.y, 3)): (o.matrix_world @ v.co).z for v in o.data.vertices}
    check("wrap: fix_boundary keeps the border, strength 0.5 goes half way",
          abs(zs[(0.6, 0.6)] - 2.0) < 1e-6 and abs(zs[(0.0, 0.0)] - 1.5) < 0.01, f"{zs[(0.0, 0.0)]}")


def test_wrap_evaluated_and_surface():
    t = sphere_target(subsurf=True)
    o = mesh_grid(5, size=1.0, z=2.0)
    bpy.context.scene.sts_point_smooth.wrap_target = t
    edit_all(o)
    bpy.ops.object.sts_point_wrap(fix_boundary=False)
    obj_mode()
    dg = bpy.context.evaluated_depsgraph_get()
    te = t.evaluated_get(dg)
    worst = max((te.closest_point_on_mesh(v.co + o.location)[1] - (v.co + o.location)).length for v in o.data.vertices)
    check("wrap: onto the evaluated (subdivided) surface", worst < 1e-4, str(worst))
    bpy.ops.wm.read_homefile(use_empty=True)
    t = sphere_target()
    bpy.ops.surface.primitive_nurbs_surface_surface_add(radius=0.5, location=(0, 0, 2))
    s = bpy.context.object
    bpy.context.scene.sts_point_smooth.wrap_target = t
    edit_all(s)
    r = bpy.ops.object.sts_point_wrap(fix_boundary=False)
    obj_mode()
    d = [(s.matrix_world @ Vector(p.co[:3])).length for p in s.data.splines[0].points]
    check("wrap surface: control points on the sphere", r == {'FINISHED'} and all(abs(x - 1.0) < 0.01 for x in d),
          f"{min(d)}..{max(d)}")


def test_wrap_refusals():
    o = mesh_grid(3)
    bpy.context.scene.sts_point_smooth.wrap_target = None
    edit_all(o)
    check("wrap: no target -> CANCELLED", bpy.ops.object.sts_point_wrap() == {'CANCELLED'})
    obj_mode()
    bpy.context.scene.sts_point_smooth.wrap_target = o
    edit_all(o)
    check("wrap: target is the object itself -> CANCELLED", bpy.ops.object.sts_point_wrap() == {'CANCELLED'})
    obj_mode()


run([
    test_registered,
    test_inflate_mesh,
    test_inflate_curve,
    test_inflate_surface_and_straight_curve,
    test_wrap_mesh,
    test_wrap_evaluated_and_surface,
    test_wrap_refusals,
])
