"""Face-set / mask helpers, GUI-free so the tests can run them.

Replaces: CFS2.py, FaceToMaskTest43.py (the mask-writing part)

The old versions built the mask by hiding the face set, flood-filling the
whole mask, showing everything and inverting — which destroyed the user's
existing mask and hidden state. These helpers write .sculpt_mask directly
and never touch .hide_poly.
"""

from mathutils import Vector

FACE_SET = ".sculpt_face_set"
MASK = ".sculpt_mask"


def face_set_ids(mesh):
    """Sorted face-set numbers used by the mesh ([] when there is no attribute)."""
    attr = mesh.attributes.get(FACE_SET)
    if attr is None:
        return []
    return sorted({d.value for d in attr.data})


def face_set_under_ray(obj, origin, direction):
    """Face-set number of the face hit by a world-space ray; None on a miss."""
    attr = obj.data.attributes.get(FACE_SET)
    if attr is None:
        return None
    inv = obj.matrix_world.inverted()  # ray_cast works in local space
    hit, _loc, _normal, face_index = obj.ray_cast(inv @ origin, inv.to_3x3() @ direction)
    if not hit or face_index < 0:
        return None
    return attr.data[face_index].value


def apply_mask(mesh, ids, mode='REPLACE', invert=False):
    """Write .sculpt_mask for the given face sets; return the target vertex count.

    Target = vertices of faces whose face set is in `ids` (boundary vertices
    included); with invert=True, every vertex except those.
    REPLACE: target 1.0, everything else 0.0. ADD: target 1.0, rest kept.
    SUBTRACT: target 0.0, rest kept.
    """
    attr = mesh.attributes.get(FACE_SET)
    in_set = set()
    if attr is not None:
        wanted = set(ids)
        values = [0] * len(attr.data)
        attr.data.foreach_get("value", values)
        for poly in mesh.polygons:
            if values[poly.index] in wanted:
                in_set.update(poly.vertices)

    count = len(in_set)
    if invert:
        count = len(mesh.vertices) - count

    mask = mesh.attributes.get(MASK)
    if mask is None:
        mask = mesh.attributes.new(MASK, 'FLOAT', 'POINT')
    mvals = [0.0] * len(mesh.vertices)
    mask.data.foreach_get("value", mvals)
    for i in range(len(mvals)):
        if (i in in_set) ^ invert:
            mvals[i] = 0.0 if mode == 'SUBTRACT' else 1.0
        elif mode == 'REPLACE':
            mvals[i] = 0.0
    mask.data.foreach_set("value", mvals)
    return count


def smooth_face_set(mesh, ids, iterations=10, strength=0.5, keep_border=True):
    """Relax the vertices of the given face sets toward their neighbours' average.

    Replaces: ★archive/SmoothNomal/smooth_faceset_modal.py (it did not even load).
    With keep_border the vertices shared with other face sets (and the mesh
    border) stay, so the face set's outline does not shrink or slide.
    Returns the number of vertices that moved.
    """
    attr = mesh.attributes.get(FACE_SET)
    if attr is None:
        return 0
    wanted = set(ids)
    fs = [0] * len(attr.data)
    attr.data.foreach_get("value", fs)
    inside, outside = set(), set()
    for poly in mesh.polygons:
        (inside if fs[poly.index] in wanted else outside).update(poly.vertices)
    edge_count = {}
    for poly in mesh.polygons:
        for k in poly.edge_keys:
            edge_count[k] = edge_count.get(k, 0) + 1
    border = set()
    for (a, b), n in edge_count.items():
        if n == 1:
            border.update((a, b))
    fixed = (inside & outside) | (inside & border) if keep_border else set()
    moving = [i for i in inside if i not in fixed]
    if not moving:
        return 0
    nbrs = {i: [] for i in moving}
    for a, b in (tuple(e.vertices) for e in mesh.edges):
        if a in nbrs:
            nbrs[a].append(b)
        if b in nbrs:
            nbrs[b].append(a)
    co = [0.0] * (len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    pts = [Vector(co[i * 3:i * 3 + 3]) for i in range(len(mesh.vertices))]
    for _ in range(iterations):
        new = {}
        for i in moving:
            if not nbrs[i]:
                continue
            avg = sum((pts[j] for j in nbrs[i]), Vector()) / len(nbrs[i])
            new[i] = pts[i].lerp(avg, strength)
        for i, p in new.items():
            pts[i] = p
    mesh.vertices.foreach_set("co", [c for p in pts for c in p])
    mesh.update()
    return len(moving)
