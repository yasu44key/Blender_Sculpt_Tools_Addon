"""Spec for modules/mesh_generators. Run through tests/run_tests.sh.

Add > Mesh and the Generate tab. Every operator: Object Mode first if needed, a new mesh
object at the 3D cursor, only it selected and active, F9-adjustable ({'REGISTER', 'UNDO'}),
lengths with unit='LENGTH', random things driven by a `seed` (same seed, same mesh).

  mesh.sts_add_lattice      cell 'CUBE' | 'OCTET', size, count_x/_y/_z, style 'WIRE' | 'CELLS', gap
      WIRE : the lattice edges only, every vertex and edge once (no doubles)
             CUBE : the cube grid edges;  OCTET : FCC points (cube corners + face centres) joined to
             their nearest neighbours (distance size / sqrt 2) — the tetrahedral-octahedral honeycomb
      CELLS: closed solids, one per cell, each shrunk toward its own centre by `gap` (0..0.9)
             CUBE : one box per cube cell
             OCTET: in every cube cell 8 corner tetrahedra + 1 centre octahedron, plus one octahedron
                    on every INTERIOR cube edge (all 4 cells around it exist). Regular shapes,
                    edge size / sqrt 2. (The old "tetrahedral space filling" did not fill space.)
  mesh.sts_add_hex_grid     rows, cols, size (hexagon edge), gap (0 = one connected sheet,
                            > 0 = separate tiles shrunk by gap)
  mesh.sts_add_random_grid  rows, cols, size, jitter_x/_y/_z (fraction of size), midpoints, seed
                            every vertex is jittered, also the midpoints (the old one moved border
                            vertices instead)
  mesh.sts_add_leaf_venation  outline 'ELLIPSE' | 'OVAL' | 'LANCE' | 'CURVE' (the active curve's
                            first closed spline, in the XY plane of the curve), length (preset size),
                            attractors, step, kill_distance, influence (radius), seed,
                            include_outline, use_skin (taper the thickness from base to tips)
      Space colonization: attractor points scattered inside the outline pull the veins, which
      grow from the base (the lowest point of the outline on Y, i.e. the leaf stalk) one `step`
      at a time; an attractor closer than `kill_distance` to a vein is removed.
      The veins are a tree of edges (one connected piece, no loops) inside the outline.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

OPS = ("sts_add_lattice", "sts_add_hex_grid", "sts_add_random_grid", "sts_add_leaf_venation")


def add(op, **kw):
    r = getattr(bpy.ops.mesh, op)(**kw)
    return r, bpy.context.active_object


def bm_of(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    return bm


def doubles(o, dist=1e-5):
    bm = bm_of(o)
    n = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    d = n - len(bm.verts)
    bm.free()
    return d


def pieces(o):
    bm = bm_of(o)
    seen, count = set(), 0
    for v in bm.verts:
        if v in seen:
            continue
        count += 1
        stack = [v]
        seen.add(v)
        while stack:
            x = stack.pop()
            for e in x.link_edges:
                y = e.other_vert(x)
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
    bm.free()
    return count


def volume(o):
    bm = bm_of(o)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


def coords(o):
    return [tuple(round(c, 6) for c in v.co) for v in o.data.vertices]


def test_registered():
    check("module listed in MODULES", "mesh_generators" in sys.modules[package()].MODULES)
    check("META tabs is ('Generate',)", submodule("modules.mesh_generators").META["tabs"] == ("Generate",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_mesh_generators", None)
    check("panel in the Generate tab", p is not None and p.bl_category == submodule("core.tabs").GENERATE)
    funcs = getattr(bpy.types.VIEW3D_MT_mesh_add.draw, "_draw_funcs", [])
    check("in Add > Mesh", any(getattr(f, "__module__", "").startswith(package() + ".modules.mesh_generators")
                               for f in funcs))
    for op in OPS:
        P = getattr(bpy.ops.mesh, op).get_rna_type().properties
        check(f"{op}: size / length is a length", ("size" in P and P["size"].unit == 'LENGTH') or
              ("length" in P and P["length"].unit == 'LENGTH'))
    P = bpy.ops.mesh.sts_add_leaf_venation.get_rna_type().properties
    check("leaf: outlines", {i.identifier for i in P["outline"].enum_items} == {'ELLIPSE', 'OVAL', 'LANCE', 'CURVE'})


def test_common_behaviour():
    for op in OPS:
        bpy.ops.wm.read_homefile(use_empty=True)
        if op == "sts_add_leaf_venation":
            kw = dict(outline='ELLIPSE')
        else:
            kw = {}
        bpy.context.scene.cursor.location = (2.0, -1.0, 0.5)
        bpy.ops.mesh.primitive_cube_add(location=(9, 9, 9))
        bpy.ops.object.mode_set(mode='EDIT')
        r, o = add(op, **kw)
        check(f"{op}: finished from Edit Mode, back in Object Mode", r == {'FINISHED'} and bpy.context.mode == 'OBJECT',
              str(r))
        check(f"{op}: at the 3D cursor", (o.location - Vector((2.0, -1.0, 0.5))).length < 1e-6, str(tuple(o.location)))
        check(f"{op}: only it selected, active, a mesh",
              o.type == 'MESH' and bpy.context.selected_objects == [o] and len(o.data.vertices) > 0)


# ---------------------------------------------------------------- lattice

def test_lattice_wire():
    r, o = add("sts_add_lattice", cell='CUBE', style='WIRE', size=1.0, count_x=3, count_y=2, count_z=2)
    check("cube wire: 4x3x3 points", len(o.data.vertices) == 36, str(len(o.data.vertices)))
    want_e = 3 * 3 * 3 + 4 * 2 * 3 + 4 * 3 * 2     # x-, y- and z-edges
    check("cube wire: every edge once, no faces", len(o.data.edges) == want_e and not o.data.polygons,
          f"{len(o.data.edges)} vs {want_e}")
    check("cube wire: no doubles", doubles(o) == 0)
    r, o = add("sts_add_lattice", cell='OCTET', style='WIRE', size=1.0, count_x=1, count_y=1, count_z=1)
    check("octet wire: one cube = 8 corners + 6 face centres", len(o.data.vertices) == 14, str(len(o.data.vertices)))
    lens = {round((o.data.vertices[e.vertices[0]].co - o.data.vertices[e.vertices[1]].co).length, 5)
            for e in o.data.edges}
    check("octet wire: every strut size/sqrt2 (nearest neighbours)", lens == {round(1 / math.sqrt(2), 5)}, str(lens))
    check("octet wire: 36 struts in one cube (24 corner-centre + 12 centre-centre)", len(o.data.edges) == 36,
          str(len(o.data.edges)))


def test_lattice_cells():
    r, o = add("sts_add_lattice", cell='CUBE', style='CELLS', size=1.0, count_x=2, count_y=2, count_z=1, gap=0.0)
    check("cube cells: 4 closed boxes, volume 4", abs(volume(o) - 4.0) < 1e-5 and len(o.data.polygons) == 24,
          f"{volume(o)} {len(o.data.polygons)}")
    r, o = add("sts_add_lattice", cell='CUBE', style='CELLS', size=1.0, count_x=2, count_y=2, count_z=1, gap=0.5)
    check("cube cells with gap: each box shrunk (volume 4 * 0.5^3)", abs(volume(o) - 0.5) < 1e-5, str(volume(o)))
    n = (2, 2, 2)
    r, o = add("sts_add_lattice", cell='OCTET', style='CELLS', size=1.0, count_x=n[0], count_y=n[1], count_z=n[2], gap=0.0)
    cubes = n[0] * n[1] * n[2]
    inner_edges = n[0] * (n[1] - 1) * (n[2] - 1) + n[1] * (n[0] - 1) * (n[2] - 1) + n[2] * (n[0] - 1) * (n[1] - 1)
    tetra, octa = 8 * cubes, cubes + inner_edges
    want_faces = 4 * tetra + 8 * octa
    check("octet cells: 8 tetrahedra + 1 octahedron per cube, + 1 octahedron per interior edge",
          len(o.data.polygons) == want_faces, f"{len(o.data.polygons)} vs {want_faces}")
    e = 1 / math.sqrt(2)
    want_v = tetra * e ** 3 / (6 * math.sqrt(2)) + octa * math.sqrt(2) / 3 * e ** 3
    check("octet cells: regular shapes, normals outward (volume adds up)", abs(volume(o) - want_v) < 1e-4,
          f"{volume(o)} vs {want_v}")
    tri = all(len(p.vertices) == 3 for p in o.data.polygons)
    edges_ok = all(abs((o.data.vertices[a].co - o.data.vertices[b].co).length - e) < 1e-5
                   for p in o.data.polygons for a, b in zip(p.vertices, list(p.vertices[1:]) + [p.vertices[0]]))
    check("octet cells: every face a triangle with edges size/sqrt2", tri and edges_ok)


# ---------------------------------------------------------------- hex / random grid

def test_hex_grid():
    r, o = add("sts_add_hex_grid", rows=3, cols=4, size=0.5, gap=0.0)
    check("hex: 12 hexagons", len(o.data.polygons) == 12 and all(len(p.vertices) == 6 for p in o.data.polygons))
    check("hex gap 0: one connected sheet (shared vertices)", doubles(o) == 0 and pieces(o) == 1, f"{pieces(o)}")
    area = 3 * math.sqrt(3) / 2 * 0.25
    check("hex: regular hexagons of edge 0.5", all(abs(p.area - area) < 1e-5 for p in o.data.polygons))
    r, o = add("sts_add_hex_grid", rows=3, cols=4, size=0.5, gap=0.2)
    check("hex gap: separate tiles, shrunk", pieces(o) == 12 and all(abs(p.area - area * 0.64) < 1e-5 for p in o.data.polygons))


def test_random_grid():
    r, a = add("sts_add_random_grid", rows=4, cols=5, size=1.0, jitter_x=0.2, jitter_y=0.2, jitter_z=0.0, seed=3,
               midpoints=False)
    check("random grid: (4+1) x (5+1) vertices, 20 quads", len(a.data.vertices) == 30 and len(a.data.polygons) == 20)
    check("random grid: jitter_z 0 keeps it flat", all(abs(v.co.z) < 1e-9 for v in a.data.vertices))
    r, b = add("sts_add_random_grid", rows=4, cols=5, size=1.0, jitter_x=0.2, jitter_y=0.2, jitter_z=0.0, seed=3,
               midpoints=False)
    r, c = add("sts_add_random_grid", rows=4, cols=5, size=1.0, jitter_x=0.2, jitter_y=0.2, jitter_z=0.0, seed=4,
               midpoints=False)
    check("random grid: same seed same mesh, other seed other mesh", coords(a) == coords(b) and coords(a) != coords(c))
    r, d = add("sts_add_random_grid", rows=2, cols=2, size=1.0, jitter_x=0.0, jitter_y=0.0, jitter_z=0.3, seed=1,
               midpoints=True)
    me = d.data
    check("midpoints: each quad split in four (5x5 vertices)", len(me.vertices) == 25 and len(me.polygons) == 16,
          f"{len(me.vertices)} {len(me.polygons)}")
    mids = [v for v in me.vertices if (round(v.co.x * 2) % 2 == 1 or round(v.co.y * 2) % 2 == 1)]
    check("midpoints are jittered too (old: the border moved instead)", sum(1 for v in mids if abs(v.co.z) > 1e-6) >= len(mids) // 2,
          f"{sum(1 for v in mids if abs(v.co.z) > 1e-6)}/{len(mids)}")


# ---------------------------------------------------------------- leaf venation

def inside_ellipse(p, a, b, cy):
    return (p.x / a) ** 2 + ((p.y - cy) / b) ** 2 <= 1.0 + 1e-6


def test_leaf_venation():
    r, o = add("sts_add_leaf_venation", outline='ELLIPSE', length=2.0, attractors=300, step=0.05, kill_distance=0.05,
               influence=0.5, seed=1, include_outline=False, use_skin=False)
    me = o.data
    check("leaf: finished, edges only", r == {'FINISHED'} and len(me.edges) > 20 and not me.polygons, str(len(me.edges)))
    check("leaf: one tree (connected, no loops)", pieces(o) == 1 and len(me.edges) == len(me.vertices) - 1,
          f"{pieces(o)} {len(me.edges)} {len(me.vertices)}")
    ys = [v.co.y for v in me.vertices]
    check("leaf: grows from the base (lowest point) toward the tip", min(ys) < -0.95 and max(ys) > 0.5,
          f"{min(ys)}..{max(ys)}")
    a, b = 0.5, 1.0     # ELLIPSE preset: length = 2 * b, width = length / 2
    check("leaf: every vein inside the outline",
          all(inside_ellipse(v.co, a * 1.02, b * 1.02, 0.0) for v in me.vertices))
    deg = [0] * len(me.vertices)
    for e in me.edges:
        for i in e.vertices:
            deg[i] += 1
    check("leaf: branching veins, not a fan of rays from one point (each point grows one step per round)",
          max(deg) <= 6 and sum(1 for d in deg if d >= 3) >= 5, f"max degree {max(deg)}, forks {sum(1 for d in deg if d >= 3)}")
    n1 = len(me.vertices)
    r, o2 = add("sts_add_leaf_venation", outline='ELLIPSE', length=2.0, attractors=300, step=0.05, kill_distance=0.05,
                influence=0.5, seed=1, include_outline=False, use_skin=False)
    r, o3 = add("sts_add_leaf_venation", outline='ELLIPSE', length=2.0, attractors=300, step=0.05, kill_distance=0.05,
                influence=0.5, seed=2, include_outline=False, use_skin=False)
    check("leaf: same seed same veins, other seed other veins", coords(o) == coords(o2) and coords(o) != coords(o3))
    r, o4 = add("sts_add_leaf_venation", outline='ELLIPSE', length=2.0, attractors=1200, step=0.05, kill_distance=0.05,
                influence=0.5, seed=1, include_outline=False, use_skin=False)
    check("leaf: more attractors, more veins", len(o4.data.vertices) > n1, f"{n1} -> {len(o4.data.vertices)}")


def test_leaf_outline_and_skin():
    r, o = add("sts_add_leaf_venation", outline='OVAL', length=2.0, attractors=200, seed=2, include_outline=True,
               use_skin=True)
    bm = bm_of(o)
    ring = [v for v in bm.verts if len(v.link_edges) == 2 and all(len(e.other_vert(v).link_edges) >= 2 for e in v.link_edges)]
    loose_ends = [v for v in bm.verts if len(v.link_edges) == 1]
    check("leaf outline: a closed ring is added (more 2-edge vertices than the veins alone)",
          len(ring) > 20 and len(loose_ends) > 0, f"{len(ring)} {len(loose_ends)}")
    bm.free()
    sk = [m for m in o.modifiers if m.type == 'SKIN']
    check("leaf skin: a Skin modifier and radii", len(sk) == 1 and o.data.skin_vertices)
    if o.data.skin_vertices:
        radii = [d.radius[0] for d in o.data.skin_vertices[0].data]
        base = min(range(len(o.data.vertices)), key=lambda i: o.data.vertices[i].co.y)
        check("leaf skin: thickest at the base", abs(radii[base] - max(radii)) < 1e-9, f"{radii[base]} vs {max(radii)}")
    # from a curve
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.curve.primitive_bezier_circle_add(radius=1.0)
    r, o = add("sts_add_leaf_venation", outline='CURVE', attractors=200, seed=1, include_outline=False, use_skin=False)
    check("leaf from a curve: veins inside the circle",
          r == {'FINISHED'} and all(v.co.xy.length <= 1.02 for v in o.data.vertices), str(r))
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    r = bpy.ops.mesh.sts_add_leaf_venation(outline='CURVE')
    check("leaf from a curve without a curve -> CANCELLED", r == {'CANCELLED'}, str(r))


run([
    test_registered,
    test_common_behaviour,
    test_lattice_wire,
    test_lattice_cells,
    test_hex_grid,
    test_random_grid,
    test_leaf_venation,
    test_leaf_outline_and_skin,
])
