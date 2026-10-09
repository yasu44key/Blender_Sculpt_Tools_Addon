"""Thickness measurement helpers, GUI-free so the tests can run them.

Replaces: MinThicknessGuard (docs/old/min_thickness_guard.py)

Fixed from the old version:
- normals come from bmesh normal_update() (Mesh.calc_normals() is gone since 4.1)
- thickness is measured INWARD ONLY (-normal): the old both-directions min
  counted the gap to an unrelated outside surface as "thickness"
- measurement is in world space, so object scale does not distort it
"""

import bmesh
from mathutils.bvhtree import BVHTree

THICK_ATTR = "sts_thickness"
MASK_ATTR = ".sculpt_mask"
THIN_GROUP = "Thin"

RAY_START_EPS = 1e-6      # ray starts just inside the surface to avoid a self-hit
BAKE_MAX = 1000.0         # internal max_distance when an operator bakes without asking


def _tree_and_normals(obj):
    """World-space BVH of the mesh plus world-space unit normals per vertex."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    mw = obj.matrix_world
    nmat = mw.to_3x3().transposed().inverted()  # normals need the inverse transpose
    world = [mw @ v.co for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    normals = [(nmat @ v.normal).normalized() for v in bm.verts]
    bm.free()
    return BVHTree.FromPolygons(world, faces), world, normals


def bake(obj, max_distance):
    """Write the point attribute sts_thickness: distance from just inside each
    vertex along -normal to the first hit (no hit / farther -> max_distance)."""
    me = obj.data
    tree, world, normals = _tree_and_normals(obj)
    attr = me.attributes.get(THICK_ATTR)
    if attr is None or attr.domain != 'POINT' or attr.data_type != 'FLOAT':
        if attr is not None:
            me.attributes.remove(attr)
        attr = me.attributes.new(THICK_ATTR, 'FLOAT', 'POINT')
    values = []
    for i in range(len(me.vertices)):
        n = normals[i]
        hit = tree.ray_cast(world[i] - n * RAY_START_EPS, -n, max_distance)
        values.append(hit[3] if hit[0] is not None else max_distance)
    attr.data.foreach_set("value", values)
    return values


def thickness_values(obj):
    """The baked values, or None when the mesh has no usable sts_thickness."""
    attr = obj.data.attributes.get(THICK_ATTR)
    if (attr is None or attr.domain != 'POINT' or attr.data_type != 'FLOAT'
            or len(attr.data) != len(obj.data.vertices)):
        return None
    return [d.value for d in attr.data]


def ensure_thickness(obj):
    """Baked values, baking first when the attribute is missing."""
    values = thickness_values(obj)
    if values is None:
        values = bake(obj, BAKE_MAX)
    return values


def thin_indices(values, min_thickness):
    return [i for i, t in enumerate(values) if t < min_thickness]


def write_thin_group(obj, thin):
    """Vertex group Thin: 1.0 on the thin vertices, 0.0 (absent) on the rest."""
    vg = obj.vertex_groups.get(THIN_GROUP) or obj.vertex_groups.new(name=THIN_GROUP)
    vg.remove(list(range(len(obj.data.vertices))))
    if thin:
        vg.add(thin, 1.0, 'REPLACE')
    return vg


def fix(obj, min_thickness):
    """Re-bake, then push every thin vertex outward along its normal by HALF
    the deficit. Both walls of a thin plate move, so the plate ends at
    min_thickness instead of the old double shift."""
    values = bake(obj, BAKE_MAX)
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    mw = obj.matrix_world
    nmat = mw.to_3x3().transposed().inverted()
    mw_inv = mw.inverted()
    moved = 0
    for v in bm.verts:
        t = values[v.index]
        if t >= min_thickness:
            continue
        n = (nmat @ v.normal).normalized()
        if n.length < 1e-9:
            continue
        v.co = mw_inv @ (mw @ v.co + n * (min_thickness - t) * 0.5)
        moved += 1
    if moved:
        bm.to_mesh(me)
        me.update()
    bm.free()
    return moved


def to_mask(obj, values, thin_distance, thick_distance, invert):
    """Sculpt mask (.sculpt_mask): 0 at or below thin_distance, 1 at or above
    thick_distance, linear in between; invert flips it."""
    me = obj.data
    attr = me.attributes.get(MASK_ATTR)
    if attr is None or attr.domain != 'POINT' or attr.data_type != 'FLOAT':
        if attr is not None:
            me.attributes.remove(attr)
        attr = me.attributes.new(MASK_ATTR, 'FLOAT', 'POINT')
    span = thick_distance - thin_distance
    mvals = []
    for t in values:
        if span <= 0.0:
            w = 0.0 if t <= thin_distance else 1.0
        elif t <= thin_distance:
            w = 0.0
        elif t >= thick_distance:
            w = 1.0
        else:
            w = (t - thin_distance) / span
        mvals.append(1.0 - w if invert else w)
    attr.data.foreach_set("value", mvals)
