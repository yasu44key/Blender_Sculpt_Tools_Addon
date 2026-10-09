"""Tile Faces: lay an exact-size tile pattern over mesh faces (bmesh, one shot).

How it differs from the old per-face tessellation:

- Faces are grouped into *regions* (connected faces whose normals stay within
  an angle). A region shares one pattern frame, so tiles run across face
  edges instead of restarting on every face. The frame is anchored to the
  object, so separate patches on one plane line up too.
- Each face is cut through its own triangles (the mesh's loop triangles), so
  concave faces keep their shape, and every piece is mapped back with the
  triangle's barycentric coordinates: pieces lie on the original surface
  even on bent quads, and UVs are carried over.
- Pieces of the same tile are merged back into one face, tiny leftovers at the
  edges can be merged into a neighbour, and T-junctions where the pattern
  meets other faces are split so the mesh stays connected.
"""

import math

import bmesh
from mathutils import Matrix, Vector, geometry

from . import patterns

TILE_LAYER = "sts_tile_id"


# ---------------------------------------------------------------- regions

def _world_normal(face, wco):
    pts = [wco[v] for v in face.verts]
    n = geometry.normal(pts) if len(pts) >= 3 else Vector()
    return n


def _face_area(face, wco):
    pts = [wco[v] for v in face.verts]
    if len(pts) < 3:
        return 0.0
    n = geometry.normal(pts)
    s = Vector()
    for i in range(len(pts)):
        s += pts[i - 1].cross(pts[i])
    return abs(s.dot(n)) * 0.5


def find_regions(faces, wco, max_angle):
    """Connected groups of faces whose normals stay within max_angle of the group average."""
    cos_lim = math.cos(max_angle)
    cos_hard = math.cos(math.radians(80.0))   # projection must not fold
    info = {}
    for f in faces:
        n = _world_normal(f, wco)
        a = _face_area(f, wco)
        if n.length > 0.5 and a > 0.0:
            info[f] = (n, a)
    pool = set(info)
    regions = []
    while pool:
        start = min(pool, key=lambda f: f.index)   # deterministic
        pool.discard(start)
        n0, a0 = info[start]
        acc = n0 * a0
        region = [start]
        stack = [start]
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g not in pool:
                        continue
                    if info[g][0].dot(acc.normalized()) < cos_lim:
                        continue
                    pool.discard(g)
                    acc += info[g][0] * info[g][1]
                    region.append(g)
                    stack.append(g)
        avg = acc.normalized()
        keep = [f for f in region if info[f][0].dot(avg) >= cos_hard]
        if len(keep) < len(region):          # rare: put the folded ones back for their own region
            pool.update(f for f in region if f not in keep)
            if not keep:
                keep = [start]
                pool.discard(start)
                avg = info[start][0]
        regions.append((keep, avg))
    return regions


def region_frame(normal, mw, angle, offset):
    """World -> pattern-space 2D function. Anchored to the object's origin and X axis."""
    rot = mw.to_3x3()
    ref = (rot @ Vector((1.0, 0.0, 0.0))).normalized()
    if abs(ref.dot(normal)) > 0.99:
        ref = (rot @ Vector((0.0, 1.0, 0.0))).normalized()
    u = (ref - normal * ref.dot(normal)).normalized()
    v = normal.cross(u)
    o = mw.translation
    ca, sa = math.cos(-angle), math.sin(-angle)
    ox, oy = offset

    def to2(p):
        d = p - o
        x, y = d.dot(u), d.dot(v)
        return (x * ca - y * sa - ox, x * sa + y * ca - oy)
    return to2


# ---------------------------------------------------------------- pieces

def _barycentric(p, a, b, c):
    d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    w1 = ((p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])) / d
    w2 = ((b[0] - a[0]) * (p[1] - a[1]) - (p[0] - a[0]) * (b[1] - a[1])) / d
    return 1.0 - w1 - w2, w1, w2


class Piece:
    __slots__ = ("key", "face", "loops", "pts", "weights")

    def __init__(self, key, face, loops, pts, weights):
        self.key = key          # (region index, tile id)
        self.face = face        # original face (attributes are copied from it)
        self.loops = loops      # the loop triangle the piece was cut from
        self.pts = pts          # local-space corners
        self.weights = weights  # barycentric weights per corner


# ---------------------------------------------------------------- build

def _quant(co, q):
    return (round(co.x / q), round(co.y / q), round(co.z / q))


def tile_faces(bm, faces, mw, pattern, size, opts, angle=0.0, offset=(0.0, 0.0),
               region_angle=math.radians(30.0), sliver=0.0):
    """Replace `faces` of `bm` with the tile pattern. Returns the new faces."""
    faces = [f for f in faces if f.is_valid]
    if not faces:
        return []

    # Adding a layer reallocates the elements: every BMFace / BMVert reference
    # taken before it is dead. Add it first, then look the faces up again.
    bm.faces.index_update()
    order = [f.index for f in faces]
    tile_layer = bm.faces.layers.int.get(TILE_LAYER) or bm.faces.layers.int.new(TILE_LAYER)
    bm.faces.ensure_lookup_table()
    faces = [bm.faces[i] for i in order]
    bm.verts.ensure_lookup_table()
    wco = {}
    for f in faces:
        for v in f.verts:
            if v not in wco:
                wco[v] = mw @ v.co

    scale = sum(mw.to_scale()) / 3.0 or 1.0
    eps_w = max(size * 1e-5, 1e-7)           # pattern / world space
    eps_l = eps_w / scale                    # local space

    loop_tris = {f: [] for f in faces}
    fset = set(faces)
    for lt in bm.calc_loop_triangles():
        f = lt[0].face
        if f in fset:
            loop_tris[f].append(lt)

    regions = find_regions(faces, wco, region_angle)
    all_pieces = []
    full_area = {}
    for ri, (rfaces, normal) in enumerate(regions):
        to2 = region_frame(normal, mw, angle, offset)
        pcs, full = _cut_region(ri, rfaces, loop_tris, to2, wco, pattern, size, opts, eps_w)
        all_pieces.extend(pcs)
        full_area.update(full)

    if not all_pieces:
        bm.faces.layers.int.remove(tile_layer)
        return []

    old_verts = {v for f in faces for v in f.verts}
    uv_layers = list(bm.loops.layers.uv.values())

    # piece data must be read before the original faces go away
    piece_uvs = []
    for pc in all_pieces:
        per_layer = []
        for lay in uv_layers:
            u0, u1, u2 = (pc.loops[k][lay].uv.copy() for k in range(3))
            per_layer.append([u0 * w[0] + u1 * w[1] + u2 * w[2] for w in pc.weights])
        piece_uvs.append(per_layer)

    key_index = {}
    for pc in all_pieces:
        key_index.setdefault(pc.key, len(key_index) + 1)

    # create the new faces (copying attributes from the face each piece came from)
    vmap = {}
    new_faces = []
    face_key = {}
    for pc, uvs in zip(all_pieces, piece_uvs):
        verts = []
        for co in pc.pts:
            k = _quant(co, eps_l)
            v = vmap.get(k)
            if v is None:
                v = bm.verts.new(co)
                vmap[k] = v
            if not verts or verts[-1] is not v:
                verts.append(v)
        if len(verts) > 1 and verts[0] is verts[-1]:
            verts.pop()
        if len(verts) < 3 or len(set(verts)) != len(verts):
            continue
        try:
            nf = bm.faces.new(verts, pc.face)
        except ValueError:
            continue
        nf[tile_layer] = key_index[pc.key]
        for li, lay in enumerate(uv_layers):
            for loop, uv in zip(nf.loops, uvs[li]):
                loop[lay].uv = uv
        new_faces.append(nf)
        face_key[nf] = pc.key

    bmesh.ops.delete(bm, geom=faces, context='FACES')
    _weld(bm, list(vmap.values()), [v for v in old_verts if v.is_valid], eps_l)

    new_faces = [f for f in new_faces if f.is_valid]
    _merge_same_tile(bm, new_faces, tile_layer)
    loose = [v for v in vmap.values() if v.is_valid and not v.link_edges]
    loose += [v for v in old_verts if v.is_valid and not v.link_edges]
    if loose:
        bmesh.ops.delete(bm, geom=list(set(loose)), context='VERTS')
    new_faces = _faces_with_layer(bm, tile_layer)

    if sliver > 0.0:
        full_by_index = {key_index[k]: a for k, a in full_area.items()}
        _absorb_slivers(bm, new_faces, tile_layer, full_by_index, mw, sliver)
        new_faces = _faces_with_layer(bm, tile_layer)

    _fix_t_junctions(bm, new_faces, eps_l)
    new_faces = _faces_with_layer(bm, tile_layer)
    _dissolve_straight_verts(bm, new_faces)
    new_faces = _faces_with_layer(bm, tile_layer)

    bm.faces.index_update()
    order = [f.index for f in new_faces]
    bm.faces.layers.int.remove(tile_layer)     # invalidates references again
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    return [bm.faces[i] for i in order]


def _cut_region(ri, faces, loop_tris, to2, wco, pattern, size, opts, eps):
    """Cut every tile of the pattern by the region's triangles (in pattern space).

    Returns (pieces, full_area): full_area maps tile key -> area of the uncut tile.
    """
    tris = []
    for f in faces:
        for lt in loop_tris[f]:
            a, b, c = (to2(wco[lt[k].vert]) for k in range(3))
            if patterns.area((a, b, c)) <= eps * eps:   # degenerate (or folded: not expected)
                continue
            tris.append((f, lt, (a, b, c)))
    if not tris:
        return [], {}
    cell = size
    grid = {}
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for idx, (_f, _lt, tri) in enumerate(tris):
        bx0, by0, bx1, by1 = patterns.bounds(tri)
        x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
        for gi in range(math.floor(bx0 / cell), math.floor(bx1 / cell) + 1):
            for gj in range(math.floor(by0 / cell), math.floor(by1 / cell) + 1):
                grid.setdefault((gi, gj), []).append(idx)

    pieces = []
    full = {}
    for tid, poly in patterns.tiles(pattern, (x0, y0, x1, y1), size, opts):
        tx0, ty0, tx1, ty1 = patterns.bounds(poly)
        if tx1 < x0 or tx0 > x1 or ty1 < y0 or ty0 > y1:
            continue
        cand = set()
        for gi in range(math.floor(tx0 / cell), math.floor(tx1 / cell) + 1):
            for gj in range(math.floor(ty0 / cell), math.floor(ty1 / cell) + 1):
                cand.update(grid.get((gi, gj), ()))
        key = (ri, tid)
        for idx in sorted(cand):
            f, lt, tri = tris[idx]
            cut = patterns.clip_convex(poly, tri)
            if not cut:
                continue
            cut = patterns.dedupe(cut, eps)
            if len(cut) < 3 or patterns.area(cut) <= eps * eps:
                continue
            a, b, c = tri
            la, lb, lc = (lt[k].vert.co for k in range(3))
            pts, ws = [], []
            for p in cut:
                w = _barycentric(p, a, b, c)
                ws.append(w)
                pts.append(la * w[0] + lb * w[1] + lc * w[2])
            pieces.append(Piece(key, f, lt, pts, ws))
            full[key] = patterns.area(poly)
    return pieces, full


def _faces_with_layer(bm, layer):
    return [f for f in bm.faces if f[layer] != 0]


def _weld(bm, new_verts, old_verts, eps):
    """Merge new vertices into each other and into the old ones left on the border.

    Only these vertices take part, so near-duplicates elsewhere in the user's
    mesh are left alone; old vertices are kept where they are.
    """
    new_verts = [v for v in new_verts if v.is_valid]
    found = bmesh.ops.find_doubles(bm, verts=new_verts + old_verts, keep_verts=old_verts, dist=eps)
    tmap = {k: v for k, v in found["targetmap"].items() if k is not v}
    if tmap:
        bmesh.ops.weld_verts(bm, targetmap=tmap)


def _merge_same_tile(bm, faces, layer):
    edges = set()
    for f in faces:
        if not f.is_valid:
            continue
        t = f[layer]
        for e in f.edges:
            lf = e.link_faces
            if len(lf) == 2 and lf[0][layer] == t and lf[1][layer] == t:
                edges.add(e)
    if edges:
        bmesh.ops.dissolve_edges(bm, edges=list(edges), use_verts=False, use_face_split=False)


def _absorb_slivers(bm, faces, layer, full_by_index, mw, ratio):
    """Merge tiles cut down below `ratio` of a whole tile into their longest-shared neighbour."""
    def world_area(f):
        pts = [mw @ v.co for v in f.verts]
        n = geometry.normal(pts)
        s = Vector()
        for i in range(len(pts)):
            s += pts[i - 1].cross(pts[i])
        return abs(s.dot(n)) * 0.5

    small = []
    for f in faces:
        full = full_by_index.get(f[layer], 0.0)
        if full > 0.0:
            a = world_area(f)
            if a < full * ratio:
                small.append((a, f[layer]))
    small.sort()
    for _a, tid in small:
        f = next((g for g in bm.faces if g[layer] == tid), None)
        if f is None:
            continue
        best = None
        for e in f.edges:
            lf = e.link_faces
            if len(lf) != 2:
                continue
            other = lf[0] if lf[1] == f else lf[1]
            if other[layer] == 0 or other[layer] == tid:
                continue
            ln = e.calc_length()
            if best is None or ln > best[0]:
                best = (ln, e, other[layer])
        if best is None:
            continue
        res = bmesh.ops.dissolve_edges(bm, edges=[best[1]], use_verts=False, use_face_split=False)
        for g in res.get("region", []):
            g[layer] = best[2]


def _fix_t_junctions(bm, faces, eps):
    """Split boundary edges at vertices that lie on them, then weld.

    Boundary = edges with a single face. Where the pattern meets faces that were
    not tiled (or another region), each side has its own vertices on the shared
    line; splitting both sides at the other's vertices makes them meet.
    """
    edges = set()
    for f in faces:
        for e in f.edges:
            if len(e.link_faces) == 1:
                edges.add(e)
    # also the open edges of untouched faces right next to the pattern
    touch = set()
    for f in faces:
        for v in f.verts:
            touch.add(v)
    for v in list(touch):
        for e in v.link_edges:
            if len(e.link_faces) == 1:
                edges.add(e)
    for e in list(edges):
        for v in e.verts:
            for e2 in v.link_edges:
                if len(e2.link_faces) == 1:
                    edges.add(e2)
    if not edges:
        return
    verts = set()
    for e in edges:
        verts.update(e.verts)

    cell = max(max((e.calc_length() for e in edges), default=1.0), eps * 10)
    grid = {}
    for v in verts:
        k = (math.floor(v.co.x / cell), math.floor(v.co.y / cell), math.floor(v.co.z / cell))
        grid.setdefault(k, []).append(v)

    splits = {}
    for e in edges:
        a, b = e.verts[0].co, e.verts[1].co
        d = b - a
        ln2 = d.length_squared
        if ln2 <= eps * eps:
            continue
        lo = Vector((min(a.x, b.x), min(a.y, b.y), min(a.z, b.z)))
        hi = Vector((max(a.x, b.x), max(a.y, b.y), max(a.z, b.z)))
        found = []
        for i in range(math.floor((lo.x - eps) / cell), math.floor((hi.x + eps) / cell) + 1):
            for j in range(math.floor((lo.y - eps) / cell), math.floor((hi.y + eps) / cell) + 1):
                for k in range(math.floor((lo.z - eps) / cell), math.floor((hi.z + eps) / cell) + 1):
                    for v in grid.get((i, j, k), ()):
                        if v in e.verts:
                            continue
                        t = (v.co - a).dot(d) / ln2
                        if t <= 1e-6 or t >= 1.0 - 1e-6:
                            continue
                        if (a + d * t - v.co).length <= eps * 4:
                            found.append((t, v))
        if found:
            splits[e] = sorted(found, key=lambda x: x[0])

    tmap = {}
    for e, found in splits.items():
        if not e.is_valid:
            continue
        v0, v1 = e.verts
        edge = e
        done = 0.0
        for t, v in found:
            if v in tmap or v in tmap.values():
                continue
            # edge_split's factor runs from v0 along what is left of the edge (v0 -> v1)
            _ne, nv = bmesh.utils.edge_split(edge, v0, (t - done) / (1.0 - done))
            nv.co = v.co.copy()
            tmap[v] = nv
            edge = next((x for x in nv.link_edges if v1 in x.verts), None)
            if edge is None:
                break
            v0 = nv
            done = t
    if tmap:
        bmesh.ops.weld_verts(bm, targetmap={k: v for k, v in tmap.items() if k.is_valid and v.is_valid})


def _dissolve_straight_verts(bm, faces, tol=1e-4):
    """Remove two-edge vertices in a straight line (left over from cutting by triangles)."""
    cands = set()
    for f in faces:
        for v in f.verts:
            cands.add(v)
    gone = []
    for v in cands:
        if len(v.link_edges) != 2:
            continue
        a = v.link_edges[0].other_vert(v).co - v.co
        b = v.link_edges[1].other_vert(v).co - v.co
        if a.length_squared == 0.0 or b.length_squared == 0.0:
            continue
        if a.normalized().dot(b.normalized()) < -1.0 + tol:
            gone.append(v)
    if gone:
        bmesh.ops.dissolve_verts(bm, verts=gone)
