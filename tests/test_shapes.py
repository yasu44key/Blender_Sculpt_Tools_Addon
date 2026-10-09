"""Functional tests for modules/shapes. Run through tests/run_tests.sh.

Five "add a shape" operators (Generate tab and Add > Mesh), replacing
SpecialObject (spindle, egg family, gear, star) and the Platonic Solids generator:
  mesh.sts_add_spindle / mesh.sts_add_egg / mesh.sts_add_gear / mesh.sts_add_star / mesh.sts_add_platonic
Torus and Pyramid are left to Blender's own Torus and Cone.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

OPS = ["mesh.sts_add_egg", "mesh.sts_add_gear", "mesh.sts_add_platonic",
       "mesh.sts_add_spindle", "mesh.sts_add_star"]


def bm_of(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    return bm


def closed(obj):
    bm = bm_of(obj)
    ok = all(len(e.link_faces) == 2 for e in bm.edges)
    bm.free()
    return ok


def volume(obj):
    bm = bm_of(obj)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


def max_face_sides(obj):
    return max(len(p.vertices) for p in obj.data.polygons)


def all_faces_convex(obj):
    """Every face is convex: the cross products of consecutive edges all point the same way."""
    me = obj.data
    for p in me.polygons:
        vs = [me.vertices[i].co for i in p.vertices]
        n = len(vs)
        if n == 3:
            continue
        for i in range(n):
            a, b, c = vs[i], vs[(i + 1) % n], vs[(i + 2) % n]
            if (b - a).cross(c - b).dot(p.normal) < -1e-6:
                return False
    return True


def bbox(obj):
    cs = [v.co for v in obj.data.vertices]
    return (Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))),
            Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))))


def add(op, **kw):
    r = getattr(bpy.ops.mesh, op.split(".")[1])(**kw)
    return r, bpy.context.object


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "shapes" in sys.modules[package()].MODULES)
    check("META tabs is ('Generate',)", submodule("modules.shapes").META["tabs"] == ("Generate",))
    pkg = package() + ".modules.shapes"
    ops = sorted(c.bl_idname for c in bpy.types.Operator.__subclasses__() if c.__module__.startswith(pkg))
    check("exactly the five shape operators (no torus / pyramid)", ops == OPS, str(ops))
    p = getattr(bpy.types, "VIEW3D_PT_sts_shapes", None)
    check("panel in the Generate tab", p is not None and p.bl_category == submodule("core.tabs").GENERATE)
    funcs = getattr(bpy.types.VIEW3D_MT_mesh_add.draw, "_draw_funcs", [])
    check("entries in Add > Mesh", any(getattr(f, "__module__", "").startswith(pkg) for f in funcs))
    check("no Scene settings (values live on the operators, F9)",
          not [k for k in bpy.types.Scene.bl_rna.properties.keys() if "shape" in k or "special" in k])


def test_props_are_lengths():
    for op, names in [("spindle", ["radius", "height"]), ("egg", ["radius", "cyl_height"]),
                      ("gear", ["inner_radius", "outer_radius", "depth", "hole_radius"]),
                      ("star", ["inner_radius", "outer_radius", "depth"]), ("platonic", ["size"])]:
        P = getattr(bpy.ops.mesh, "sts_add_" + op).get_rna_type().properties
        for n in names:
            check(f"{op}.{n} is a length", n in P and P[n].unit == 'LENGTH', str(P[n].unit) if n in P else "missing")


# ---------------------------------------------------------------- common behaviour

def test_added_at_cursor_and_selected():
    bpy.ops.mesh.primitive_cube_add()
    other = bpy.context.object
    bpy.context.scene.cursor.location = (3, 4, 5)
    for op in OPS:
        r, obj = add(op)
        check(f"{op}: finished", r == {'FINISHED'}, str(r))
        check(f"{op}: at the 3D cursor", (obj.location - Vector((3, 4, 5))).length < 1e-6)
        check(f"{op}: only the new object selected", list(bpy.context.selected_objects) == [obj])
        check(f"{op}: closed solid", closed(obj))
        check(f"{op}: normals outward (positive volume)", volume(obj) > 0, f"{volume(obj):.4f}")
    check("other objects untouched", other.name in bpy.data.objects)


def test_from_edit_mode():
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.object.mode_set(mode='EDIT')
    r, obj = add("mesh.sts_add_spindle")
    check("works from Edit Mode (new object, Object Mode)", r == {'FINISHED'} and bpy.context.mode == 'OBJECT'
          and obj.name.startswith("Spindle"), f"{r} {bpy.context.mode} {obj.name}")


# ---------------------------------------------------------------- shapes

def test_spindle():
    _r, o = add("mesh.sts_add_spindle", radius=1.0, height=2.0, segments=16)
    check("spindle: segments + 2 verts", len(o.data.vertices) == 18, str(len(o.data.vertices)))
    check("spindle: 2 x segments triangles", len(o.data.polygons) == 32 and max_face_sides(o) == 3)
    lo, hi = bbox(o)
    check("spindle: height 2, radius 1", abs(hi.z - lo.z - 2) < 1e-5 and abs(hi.x - 1) < 1e-5)


def test_egg_presets():
    _r, o = add("mesh.sts_add_egg", preset='SPHERE', radius=1.0)
    d = [v.co.length for v in o.data.vertices]
    check("SPHERE: every vertex at radius 1", max(abs(x - 1) for x in d) < 1e-4, f"{min(d)} {max(d)}")
    check("SPHERE: named Sphere", o.name.startswith("Sphere"), o.name)
    _r, o = add("mesh.sts_add_egg", preset='CAPSULE', radius=0.5, cyl_height=1.0)
    lo, hi = bbox(o)
    check("CAPSULE: height = cylinder + 2R", abs((hi.z - lo.z) - 2.0) < 1e-4, str(hi.z - lo.z))
    check("CAPSULE: centred", abs(hi.z + lo.z) < 1e-4)
    _r, o = add("mesh.sts_add_egg", preset='EGG')
    widest = max(o.data.vertices, key=lambda v: Vector((v.co.x, v.co.y)).length)
    check("EGG: the widest ring sits below the middle (fuller bottom)", widest.co.z < -1e-3, str(widest.co.z))
    check("EGG: named Egg", o.name.startswith("Egg"), o.name)


def test_egg_name_follows_numbers():
    _r, o = add("mesh.sts_add_egg", preset='SPHERE', radius=1.0, rho1=0.5)
    check("numbers changed away from the preset -> generic name 'Egg'", o.name.startswith("Egg"), o.name)


def test_gear():
    _r, o = add("mesh.sts_add_gear", teeth=12, inner_radius=0.6, outer_radius=1.0, depth=0.3, hole_radius=0.0)
    check("gear: no concave n-gon (all faces convex)", all_faces_convex(o))
    check("gear: no huge single cap face", max_face_sides(o) <= 4, str(max_face_sides(o)))
    lo, hi = bbox(o)
    check("gear: thickness = depth", abs(hi.z - lo.z - 0.3) < 1e-5)
    _r, h = add("mesh.sts_add_gear", teeth=12, inner_radius=0.6, outer_radius=1.0, depth=0.3, hole_radius=0.2)
    check("gear with hole: still closed", closed(h))
    inner = min(Vector((v.co.x, v.co.y)).length for v in h.data.vertices)
    check("gear with hole: hole radius 0.2", abs(inner - 0.2) < 1e-4, str(inner))
    check("gear with hole: all faces convex", all_faces_convex(h))


def test_star():
    _r, o = add("mesh.sts_add_star", points=5, inner_radius=0.4, outer_radius=1.0, depth=0.3)
    check("star: all faces convex (no concave cap)", all_faces_convex(o))
    tips = max(Vector((v.co.x, v.co.y)).length for v in o.data.vertices)
    check("star: tips at the outer radius", abs(tips - 1.0) < 1e-5)


def test_platonic():
    expect = {'TETRA': (4, 4), 'CUBE': (8, 6), 'OCTA': (6, 8), 'DODECA': (20, 12), 'ICOSA': (12, 20),
              'TRUNC_ICOSA': (60, 32)}
    P = bpy.ops.mesh.sts_add_platonic.get_rna_type().properties
    check("solid choices", {i.identifier for i in P["solid"].enum_items} == set(expect))
    for solid, (nv, nf) in expect.items():
        _r, o = add("mesh.sts_add_platonic", solid=solid, size=1.5)
        check(f"{solid}: {nv} verts / {nf} faces", (len(o.data.vertices), len(o.data.polygons)) == (nv, nf),
              f"{len(o.data.vertices)} / {len(o.data.polygons)}")
        d = [v.co.length for v in o.data.vertices]
        check(f"{solid}: every vertex on the circumsphere (size = circumradius)",
              max(abs(x - 1.5) for x in d) < 1e-4, f"{min(d):.5f}..{max(d):.5f}")
        check(f"{solid}: closed and outward", closed(o) and volume(o) > 0)
    _r, o = add("mesh.sts_add_platonic", solid='TRUNC_ICOSA', size=1.0)
    sides = sorted(len(p.vertices) for p in o.data.polygons)
    check("soccer ball: 12 pentagons + 20 hexagons", sides == [5] * 12 + [6] * 20, str(sides[:3]) + "...")


run([
    test_registered,
    test_props_are_lengths,
    test_added_at_cursor_and_selected,
    test_from_edit_mode,
    test_spindle,
    test_egg_presets,
    test_egg_name_follows_numbers,
    test_gear,
    test_star,
    test_platonic,
])
