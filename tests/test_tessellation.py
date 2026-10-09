"""Functional tests for modules/tessellation. Run through tests/run_tests.sh."""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def cells():
    return submodule("modules.tessellation.cells")


def mesh_from(verts, faces, name="M"):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    select_only(o)
    return o


def select_only(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def square(size=1.0, cuts=0):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=cuts + 1, y_subdivisions=cuts + 1, size=size)
    return bpy.context.object


def total_area(me):
    return sum(p.area for p in me.polygons)


def edge_face_counts(me):
    counts = {}
    for p in me.polygons:
        for k in p.edge_keys:
            counts[k] = counts.get(k, 0) + 1
    return counts


def boundary_edges(me):
    return sum(1 for c in edge_face_counts(me).values() if c == 1)


def tile(**kw):
    return bpy.ops.mesh.sts_tile_faces(**kw)


# ---------------------------------------------------------------- registration

def test_registered():
    check("module listed in MODULES", "tessellation" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.tessellation").META["tabs"] == ("Model",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_tessellation", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    P = bpy.ops.mesh.sts_tile_faces.get_rna_type().properties
    check("tile: six patterns",
          {i.identifier for i in P["pattern"].enum_items}
          == {'SQUARE', 'BRICK', 'TRIANGLE', 'HEXAGON', 'OCTAGON', 'VORONOI'})
    check("tile: size is a length", P["tile_size"].unit == 'LENGTH')
    check("tile: rotation / region angle are angles",
          P["rotation"].subtype == 'ANGLE' and P["region_angle"].subtype == 'ANGLE')
    check("tile: offset is a length", P["offset"].unit == 'LENGTH')
    check("no settings left on the Scene", not any(k.startswith("cell_tess") or "tessellation" in k
                                                   for k in bpy.types.Scene.bl_rna.properties.keys()))


# ---------------------------------------------------------------- tile faces

def test_exact_squares():
    o = square(1.0)
    r = tile(pattern='SQUARE', tile_size=0.25, sliver=0.0)
    me = o.data
    check("tile finished", r == {'FINISHED'}, str(r))
    check("1 m plane / 0.25 m squares = 16 faces", len(me.polygons) == 16, str(len(me.polygons)))
    check("every square is exactly 0.25 x 0.25",
          all(abs(p.area - 0.0625) < 1e-6 and len(p.vertices) == 4 for p in me.polygons))
    check("connected: only the 16 outline edges are open", boundary_edges(me) == 16, str(boundary_edges(me)))


def test_world_size_with_object_scale():
    o = square(1.0)
    o.scale = (2.0, 2.0, 2.0)
    tile(pattern='SQUARE', tile_size=0.5, sliver=0.0)
    check("tile size is in world units (scaled object: 2 m / 0.5 m = 16)", len(o.data.polygons) == 16,
          str(len(o.data.polygons)))


def test_continuous_across_faces():
    a = square(1.0)
    tile(pattern='SQUARE', tile_size=0.3, sliver=0.0)
    one_face = (len(a.data.polygons), boundary_edges(a.data))
    bpy.data.objects.remove(a)
    b = square(1.0, cuts=4)        # same outline made of 25 faces
    tile(pattern='SQUARE', tile_size=0.3, sliver=0.0)
    many = (len(b.data.polygons), boundary_edges(b.data))
    check("pattern runs across face edges (same result as one big face)", one_face == many,
          f"{one_face} vs {many}")
    check("no T-junction or seam inside", many[1] == one_face[1])


def test_area_kept_for_every_pattern():
    for pat in ('SQUARE', 'BRICK', 'TRIANGLE', 'HEXAGON', 'OCTAGON', 'VORONOI'):
        bpy.ops.wm.read_homefile(use_empty=True)
        o = square(1.0, cuts=2)
        r = tile(pattern=pat, tile_size=0.17, rotation=0.3, sliver=0.0)
        me = o.data
        check(f"{pat}: finished", r == {'FINISHED'}, str(r))
        check(f"{pat}: area kept", abs(total_area(me) - 1.0) < 1e-4, str(total_area(me)))
        check(f"{pat}: one connected sheet (open edges only on the outline)",
              all(c <= 2 for c in edge_face_counts(me).values()))
        check(f"{pat}: normals still up", all(p.normal.z > 0.99 for p in me.polygons))


def test_hexagons_are_hexagons():
    o = square(2.0)
    tile(pattern='HEXAGON', tile_size=0.2, sliver=0.0)
    full = 3 * math.sqrt(3) / 2 * 0.2 ** 2
    whole = [p for p in o.data.polygons if abs(p.area - full) < 1e-6]
    check("inner tiles are whole regular hexagons", len(whole) > 15 and all(len(p.vertices) == 6 for p in whole),
          str(len(whole)))


def test_concave_face():
    # L shape: one concave n-gon (old clipper assumed convex faces)
    o = mesh_from([(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)], [(0, 1, 2, 3, 4, 5)])
    tile(pattern='SQUARE', tile_size=0.25, sliver=0.0)
    me = o.data
    check("concave face: area kept (3 m2)", abs(total_area(me) - 3.0) < 1e-5, str(total_area(me)))
    check("concave face: nothing outside the L",
          all(not (v.co.x > 1.0 + 1e-6 and v.co.y > 1.0 + 1e-6) for v in me.vertices))
    check("concave face: 48 squares", len(me.polygons) == 48, str(len(me.polygons)))


def test_bent_quad_stays_on_surface():
    o = mesh_from([(0, 0, 0), (1, 0, 0), (1, 1, 0.4), (0, 1, 0)], [(0, 1, 2, 3)])
    tri_a = [Vector(c) for c in ((0, 0, 0), (1, 0, 0), (1, 1, 0.4))]
    tri_b = [Vector(c) for c in ((0, 0, 0), (1, 1, 0.4), (0, 1, 0))]
    from mathutils.geometry import distance_point_to_plane, normal
    planes = [(t[0], normal(t)) for t in (tri_a, tri_b)]
    tile(pattern='TRIANGLE', tile_size=0.15, sliver=0.0)
    worst = 0.0
    for v in o.data.vertices:
        d = min(abs(distance_point_to_plane(v.co, p, n)) for p, n in planes)
        worst = max(worst, d)
    check("bent quad: every new vertex lies on the original surface", worst < 1e-5, str(worst))


def test_edit_mode_selected_only_and_watertight():
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(o.data)
    for f in bm.faces:
        f.select_set(f.normal.z > 0.9)
    bmesh.update_edit_mesh(o.data)
    r = tile(pattern='SQUARE', tile_size=0.3, sliver=0.0)
    check("edit: finished", r == {'FINISHED'}, str(r))
    bm = bmesh.from_edit_mesh(o.data)
    top = [f for f in bm.faces if f.normal.z > 0.9]
    sides = [f for f in bm.faces if abs(f.normal.z) < 0.1]
    check("edit: only the selected top face was tiled", len(top) == 16 and len(sides) == 4,
          f"{len(top)} / {len(sides)}")
    check("edit: the new tiles are selected", all(f.select for f in top) and not any(f.select for f in sides))
    check("edit: still closed (sides were split where the tiles meet them)",
          all(len(e.link_faces) == 2 for e in bm.edges))
    bpy.ops.object.mode_set(mode='OBJECT')
    check("edit: volume surface area kept", abs(total_area(o.data) - 6.0) < 1e-5)


def test_edit_mode_nothing_selected():
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    r = tile(pattern='SQUARE', tile_size=0.3)
    check("edit: nothing selected -> CANCELLED", r == {'CANCELLED'}, str(r))


def test_box_corners_restart_pattern():
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.object
    tile(pattern='SQUARE', tile_size=0.25, sliver=0.0)
    me = o.data
    check("cube: 6 sides x 16 squares", len(me.polygons) == 96, str(len(me.polygons)))
    check("cube: closed", all(c == 2 for c in edge_face_counts(me).values()))


def test_uv_carried_over():
    o = square(1.0)          # the grid's UVs are (x + 0.5, y + 0.5)
    tile(pattern='HEXAGON', tile_size=0.13, sliver=0.0)
    me = o.data
    uv = me.uv_layers.active.data
    worst = 0.0
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            worst = max(worst, (Vector((co.x + 0.5, co.y + 0.5)) - uv[li].uv).length)
    check("UVs follow the surface", worst < 1e-4, str(worst))


def test_materials_kept():
    o = square(1.0, cuts=1)
    for name in ("A", "B"):
        o.data.materials.append(bpy.data.materials.new(name))
    for p in o.data.polygons:
        p.material_index = 1 if p.center.x > 0 else 0
    tile(pattern='SQUARE', tile_size=0.25, sliver=0.0)
    me = o.data
    check("material slots kept per side",
          all(p.material_index == (1 if p.center.x > 0 else 0) for p in me.polygons))


def test_small_pieces_merge():
    o = square(1.0)
    tile(pattern='SQUARE', tile_size=0.3, offset=(0.05, 0.05), sliver=0.0)
    n_all = len(o.data.polygons)
    smallest = min(p.area for p in o.data.polygons)
    bpy.ops.wm.read_homefile(use_empty=True)
    o = square(1.0)
    tile(pattern='SQUARE', tile_size=0.3, offset=(0.05, 0.05), sliver=0.3)
    me = o.data
    check("without merging there are slivers", smallest < 0.3 * 0.09, str(smallest))
    check("merged: fewer faces", len(me.polygons) < n_all, f"{len(me.polygons)} < {n_all}")
    check("merged: no piece under the limit", min(p.area for p in me.polygons) >= 0.3 * 0.09 - 1e-9)
    check("merged: area kept", abs(total_area(me) - 1.0) < 1e-5)


def test_rotation_and_offset():
    o = square(1.0)
    tile(pattern='SQUARE', tile_size=0.25, rotation=math.radians(45.0), sliver=0.0)
    me = o.data
    check("rotated: area kept", abs(total_area(me) - 1.0) < 1e-5)
    full = [p for p in me.polygons if abs(p.area - 0.0625) < 1e-6]
    check("rotated: whole tiles run at 45 degrees",
          full and all(abs(abs((me.vertices[p.vertices[1]].co - me.vertices[p.vertices[0]].co).normalized().x)
                           - math.sqrt(0.5)) < 1e-4 for p in full))
    bpy.ops.wm.read_homefile(use_empty=True)
    o = square(1.0)
    tile(pattern='SQUARE', tile_size=0.25, offset=(0.125, 0.0), sliver=0.0)
    check("offset by half a tile: 5 columns x 4 rows", len(o.data.polygons) == 20, str(len(o.data.polygons)))


def test_refuses():
    o = square(1.0)
    o.shape_key_add(name="Basis")
    r = tile(pattern='SQUARE', tile_size=0.25)
    check("shape keys -> CANCELLED", r == {'CANCELLED'}, str(r))
    bpy.ops.wm.read_homefile(use_empty=True)
    square(100.0)
    r = tile(pattern='SQUARE', tile_size=0.01)
    check("too many tiles -> CANCELLED", r == {'CANCELLED'}, str(r))


# ---------------------------------------------------------------- live cells

def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return o.evaluated_get(dg).data


def test_live_cells():
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, location=(-3, 0, 0))
    a = bpy.context.object
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, location=(3, 0, 0))
    b = bpy.context.object
    a.select_set(True)
    r = bpy.ops.object.sts_cells_add()
    check("cells: finished", r == {'FINISHED'}, str(r))
    ma, mb = cells().get(a), cells().get(b)
    check("cells: modifier on both selected", ma is not None and mb is not None)
    check("cells: one shared node group", ma.node_group is mb.node_group)
    bpy.ops.object.sts_cells_add()
    check("cells: pressing again adds no duplicate",
          sum(1 for m in a.modifiers if m.type == 'NODES') == 1)
    n0 = len(evaluated(a).polygons)
    check("cells: geometry changed", n0 > len(a.data.polygons), str(n0))
    cells().set_input(ma, "Subdivisions", 2)
    n1 = len(evaluated(a).polygons)
    check("cells: more subdivisions, more cells", n1 > n0 * 2, f"{n0} -> {n1}")
    cells().set_input(ma, "Jitter", 0.0)
    cells().set_input(ma, "Gap", 0.0)
    cells().set_input(ma, "Cell Thickness", 0.0)
    me = evaluated(a)
    rr = [v.co.length for v in me.vertices]
    check("cells: flat cells stay on the sphere", max(rr) < 1.0 + 1e-4 and min(rr) > 0.9, f"{min(rr)}..{max(rr)}")
    cells().set_input(ma, "Lattice", True)
    me = evaluated(a)
    check("cells: lattice makes struts", len(me.polygons) > 0)
    cells().set_input(mb, "Keep Base", True)
    cells().set_input(mb, "Cell Thickness", 0.05)
    check("cells: keep base adds the original surface",
          len(evaluated(b).polygons) > n0)
    r = bpy.ops.object.sts_cells_remove()
    check("cells: removed", r == {'FINISHED'} and cells().get(a) is None and cells().get(b) is None)
    r = bpy.ops.object.sts_cells_remove()
    check("cells: nothing to remove -> CANCELLED", r == {'CANCELLED'}, str(r))


def test_live_cells_open_mesh():
    o = square(2.0, cuts=5)
    bpy.ops.object.sts_cells_add()
    mod = cells().get(o)
    cells().set_input(mod, "Cell Thickness", 0.0)
    cells().set_input(mod, "Gap", 0.0)
    cells().set_input(mod, "Jitter", 0.0)
    me = evaluated(o)
    xs = [v.co.x for v in me.vertices]
    check("cells on an open plane reach its border", abs(max(xs) - 1.0) < 1e-4 and abs(min(xs) + 1.0) < 1e-4,
          f"{min(xs)}..{max(xs)}")


# ---------------------------------------------------------------- skin lattice

def test_skin_lattice():
    o = square(1.0, cuts=2)
    r = bpy.ops.mesh.sts_skin_lattice(radius=0.03)
    check("skin: finished", r == {'FINISHED'}, str(r))
    sv = o.data.skin_vertices[0].data
    check("skin: radius written", all(abs(d.radius[0] - 0.03) < 1e-6 for d in sv))
    check("skin: one root for the one piece", sum(1 for d in sv if d.use_root) == 1)
    check("skin: modifier added", sum(1 for m in o.modifiers if m.type == 'SKIN') == 1)
    bpy.ops.mesh.sts_skin_lattice(radius=0.05)
    check("skin: again -> still one modifier, one root",
          sum(1 for m in o.modifiers if m.type == 'SKIN') == 1
          and sum(1 for d in o.data.skin_vertices[0].data if d.use_root) == 1)


run([
    test_registered,
    test_exact_squares,
    test_world_size_with_object_scale,
    test_continuous_across_faces,
    test_area_kept_for_every_pattern,
    test_hexagons_are_hexagons,
    test_concave_face,
    test_bent_quad_stays_on_surface,
    test_edit_mode_selected_only_and_watertight,
    test_edit_mode_nothing_selected,
    test_box_corners_restart_pattern,
    test_uv_carried_over,
    test_materials_kept,
    test_small_pieces_merge,
    test_rotation_and_offset,
    test_refuses,
    test_live_cells,
    test_live_cells_open_mesh,
    test_skin_lattice,
])
