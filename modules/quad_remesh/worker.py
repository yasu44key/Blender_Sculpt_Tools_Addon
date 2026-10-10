"""Quad Remesh worker — runs in a separate background Blender, never inside the user's session.

    blender -b --factory-startup --python worker.py -- <job_dir>

<job_dir>/job.json holds the settings, verts.npy / tris.npy the source surface (local
coordinates). The worker builds a light proxy (voxel remesh + decimate, or decimate only
for open surfaces), cuts it for symmetry, then drives QuadWild Bi-MDF through the DLLs of
an installed QRemeshify (GPL, not shipped with this MIT suite) and writes result.obj.

Progress goes to stdout as   STS_PROGRESS <0..1> <message>
the end as                   STS_RESULT <faces> <quads>      or   STS_ERROR <message>
QuadWild calls exit(0) on some bad inputs: a run that ends without STS_RESULT failed.

This file is run as a script: no imports from the add-on package.
"""

import ctypes
import json
import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector


def progress(frac, msg):
    print(f"STS_PROGRESS {frac:.3f} {msg}", flush=True)


# --- QuadWild DLL interface (struct layouts of lib_quadwild / lib_quadpatches) ---------------

class Parameters(ctypes.Structure):
    _fields_ = [
        ("remesh", ctypes.c_bool),
        ("sharpAngle", ctypes.c_float),
        ("alpha", ctypes.c_float),
        ("scaleFact", ctypes.c_float),
        ("hasFeature", ctypes.c_bool),
        ("hasField", ctypes.c_bool),
    ]


class QRParameters(ctypes.Structure):
    _fields_ = [
        ("useFlowSolver", ctypes.c_bool),
        ("flow_config_filename", ctypes.c_char_p),
        ("satsuma_config_filename", ctypes.c_char_p),
        ("initialRemeshing", ctypes.c_bool),
        ("initialRemeshingEdgeFactor", ctypes.c_double),
        ("reproject", ctypes.c_bool),
        ("splitConcaves", ctypes.c_bool),
        ("finalSmoothing", ctypes.c_bool),
        ("ilpMethod", ctypes.c_int),
        ("alpha", ctypes.c_double),
        ("isometry", ctypes.c_bool),
        ("regularityQuadrilaterals", ctypes.c_bool),
        ("regularityNonQuadrilaterals", ctypes.c_bool),
        ("regularityNonQuadrilateralsWeight", ctypes.c_double),
        ("alignSingularities", ctypes.c_bool),
        ("alignSingularitiesWeight", ctypes.c_double),
        ("repeatLosingConstraintsIterations", ctypes.c_bool),
        ("repeatLosingConstraintsQuads", ctypes.c_bool),
        ("repeatLosingConstraintsNonQuads", ctypes.c_bool),
        ("repeatLosingConstraintsAlign", ctypes.c_bool),
        ("feasibilityFix", ctypes.c_bool),
        ("hardParityConstraint", ctypes.c_bool),
        ("timeLimit", ctypes.c_double),
        ("gapLimit", ctypes.c_double),
        ("minimumGap", ctypes.c_double),
        ("callbackTimeLimit", ctypes.POINTER(ctypes.c_float)),
        ("callbackGapLimit", ctypes.POINTER(ctypes.c_float)),
        ("chartSmoothingIterations", ctypes.c_int),
        ("quadrangulationFixedSmoothingIterations", ctypes.c_int),
        ("quadrangulationNonFixedSmoothingIterations", ctypes.c_int),
        ("doubletRemoval", ctypes.c_bool),
        ("resultSmoothingIterations", ctypes.c_int),
        ("resultSmoothingNRing", ctypes.c_double),
        ("resultSmoothingLaplacianIterations", ctypes.c_int),
        ("resultSmoothingLaplacianNRing", ctypes.c_double),
    ]


FILL = 1.4

CALLBACK_TIME = [3.0, 5.0, 10.0, 20.0, 30.0, 60.0, 90.0, 120.0]
CALLBACK_GAP = [0.005, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.3]


def load_engine(lib_dir):
    names = {"win32": ("lib_quadwild.dll", "lib_quadpatches.dll"),
             "darwin": ("liblib_quadwild.dylib", "liblib_quadpatches.dylib")}
    qw_name, qp_name = names.get(sys.platform, ("liblib_quadwild.so", "liblib_quadpatches.so"))
    qw = ctypes.cdll.LoadLibrary(os.path.join(lib_dir, qw_name))
    qp = ctypes.cdll.LoadLibrary(os.path.join(lib_dir, qp_name))
    qw.remeshAndField2.argtypes = [ctypes.POINTER(Parameters), ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    qw.remeshAndField2.restype = None
    qw.trace2.argtypes = [ctypes.c_char_p]
    qw.trace2.restype = ctypes.c_bool
    qp.quadPatches.argtypes = [ctypes.c_char_p, ctypes.POINTER(QRParameters), ctypes.c_float, ctypes.c_int, ctypes.c_bool]
    qp.quadPatches.restype = ctypes.c_int
    return qw, qp


def qr_parameters(lib_dir, job, keep):
    p = QRParameters()
    p.useFlowSolver = True
    p.flow_config_filename = os.path.join(lib_dir, "config", "main_config", "flow_virtual_simple.json").encode()
    p.satsuma_config_filename = os.path.join(lib_dir, "config", "satsuma", "default.json").encode()
    p.initialRemeshing = True
    p.initialRemeshingEdgeFactor = 1
    p.reproject = True
    p.splitConcaves = False
    p.finalSmoothing = True
    p.ilpMethod = 1                       # least squares
    p.alpha = job["alpha"]
    p.isometry = True
    p.regularityQuadrilaterals = True
    p.regularityNonQuadrilaterals = True
    p.regularityNonQuadrilateralsWeight = 0.9
    p.alignSingularities = True
    p.alignSingularitiesWeight = 0.1
    p.repeatLosingConstraintsIterations = True
    p.repeatLosingConstraintsQuads = False
    p.repeatLosingConstraintsNonQuads = False
    p.repeatLosingConstraintsAlign = True
    p.feasibilityFix = False
    p.hardParityConstraint = True
    p.timeLimit = job["time_limit"]
    p.gapLimit = 0.0
    p.minimumGap = 0.4
    keep.append((ctypes.c_float * 8)(*CALLBACK_TIME))
    keep.append((ctypes.c_float * 8)(*CALLBACK_GAP))
    p.callbackTimeLimit = keep[-2]
    p.callbackGapLimit = keep[-1]
    p.chartSmoothingIterations = 0
    p.quadrangulationFixedSmoothingIterations = 0
    p.quadrangulationNonFixedSmoothingIterations = 0
    p.doubletRemoval = True
    p.resultSmoothingIterations = 5
    p.resultSmoothingNRing = 3
    p.resultSmoothingLaplacianIterations = 2
    p.resultSmoothingLaplacianNRing = 3
    return p


# --- mesh helpers -----------------------------------------------------------------------------

def mesh_from_arrays(verts, tris):
    me = bpy.data.meshes.new("sts_quad_src")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(tris.size)
    me.loops.foreach_set("vertex_index", tris.ravel())
    me.polygons.add(len(tris))
    me.polygons.foreach_set("loop_start", np.arange(0, tris.size, 3, dtype=np.int32))
    me.update(calc_edges=True)
    return me


def surface_area(verts, tris):
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())


def open_edge_count(tris):
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e.sort(axis=1)
    key = e[:, 0].astype(np.int64) * (int(e.max()) + 1) + e[:, 1]
    _, counts = np.unique(key, return_counts=True)
    return int((counts != 2).sum())


def build_proxy(obj, job, closed, area):
    """Voxel remesh (closed surfaces) then decimate to about job['proxy_tris'] triangles."""
    me = obj.data
    if job["proxy"] == 'VOXEL' or (job["proxy"] == 'AUTO' and closed):
        quad_edge = math.sqrt(area / job["target_faces"])
        voxel = quad_edge / job["voxel_div"]
        # never ask OpenVDB for more than ~4M faces
        voxel = max(voxel, math.sqrt(area / 4_000_000))
        me.remesh_voxel_size = voxel
        me.remesh_voxel_adaptivity = 0.0
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            bpy.ops.object.voxel_remesh()
        print(f"STS_INFO voxel {voxel:.4f} -> {len(obj.data.polygons)} faces", flush=True)
    tri_now = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    surface = None
    if tri_now > job["proxy_tris"]:
        from mathutils.bvhtree import BVHTree
        surface = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())
        m = obj.modifiers.new("dec", 'DECIMATE')
        m.ratio = job["proxy_tris"] / tri_now
        m.use_symmetry = False
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier=m.name)
    return surface


def repair_folds(bm, surface, rounds=8):
    """Decimation leaves thin folded fins in deep creases (eyelids, ears: 110 on the head
    scan). Without guides QuadWild glides over them; a guide line along the crease makes the
    quads follow the fold. Relax the vertices around each fold and put them back on the
    surface before decimation, until no fold is left."""
    fixed = 0
    for _ in range(rounds):
        for f in bm.faces:
            f.normal_update()
        bad = [e for e in bm.edges if len(e.link_faces) == 2
               and e.link_faces[0].normal.dot(e.link_faces[1].normal) < -0.2]
        if not bad:
            break
        area = {v for e in bad for v in e.verts}
        area |= {e2.other_vert(v) for v in list(area) for e2 in v.link_edges}
        for _ in range(3):
            for v in area:
                if v.is_boundary or not v.link_edges:
                    continue
                c = sum((e2.other_vert(v).co for e2 in v.link_edges), Vector()) / len(v.link_edges)
                hit = surface.find_nearest(c)[0] if surface is not None else None
                v.co = hit if hit is not None else c
        fixed += len(bad)
    for f in bm.faces:
        f.normal_update()
    left = sum(1 for e in bm.edges if len(e.link_faces) == 2
               and e.link_faces[0].normal.dot(e.link_faces[1].normal) < -0.5)
    print(f"STS_INFO folds repaired: {fixed} edge-rounds, left {left}", flush=True)


def untangle_result(result_path, proxy_path):
    """Safety net: relax folded quads (QuadWild can fold a sliver next to the end of an open
    guide line) and put them back on the proxy surface."""
    from mathutils.bvhtree import BVHTree
    PV, PF = read_obj(proxy_path)
    surface = BVHTree.FromPolygons([tuple(v) for v in PV], PF)
    V, F = read_obj(result_path)
    bm = bmesh.new()
    verts = [bm.verts.new(v) for v in V]
    for f in F:
        try:
            bm.faces.new([verts[i] for i in f])
        except ValueError:
            pass
    before = count_folds(bm)
    if before == 0:
        bm.free()
        return
    repair_folds(bm, surface)
    after = count_folds(bm)
    print(f"STS_INFO result folds {before} -> {after}", flush=True)
    write_obj(bm, result_path)
    bm.free()


def _density_at(points, verts, dens, k=6):
    """Inverse-distance density of the source at the given points (subsampled source)."""
    from mathutils import kdtree
    step = max(1, len(verts) // 400_000)          # the map is smooth: a subsample is enough
    src = verts[::step]
    val = np.asarray(dens, dtype=np.float64)[::step]
    kd = kdtree.KDTree(len(src))
    for i, p in enumerate(src):
        kd.insert(p, i)
    kd.balance()
    out = []
    for p in points:
        near = kd.find_n(p, k)
        w = sum(1.0 / (d + 1e-9) for _c, _i, d in near)
        out.append(sum(val[i] / (d + 1e-9) for _c, i, d in near) / w)
    return out


def density_contours(bm, verts, dens, quad_edge, level=0.5):
    """The 0.5 contour of the density map on the proxy, as hard guides.

    A quad patch is a regular grid: the quad size can only change across patch borders.
    Making the edge of the painted area a feature line puts a patch border there (egg, top
    painted x2.5: size ratio 1.38 without it, 1.64 with it, 10-10)."""
    bm.verts.index_update()
    d = _density_at([v.co for v in bm.verts], verts, dens)
    # marching triangles: one segment per triangle the level crosses
    seg_of_edge = {}
    links = {}

    def cross(e):
        a, b = e.verts
        da, db = d[a.index] - level, d[b.index] - level
        if (da < 0) == (db < 0):
            return None
        if e not in seg_of_edge:
            t = da / (da - db)
            seg_of_edge[e] = a.co.lerp(b.co, t)
        return e
    for f in bm.faces:
        hits = [e for e in f.edges if cross(e) is not None]
        if len(hits) == 2:
            a, b = hits
            links.setdefault(a, []).append(b)
            links.setdefault(b, []).append(a)
    lines = []
    seen = set()
    for start in links:
        if start in seen:
            continue
        # walk to one end (or around a loop), then collect
        prev, cur = None, start
        while True:
            nxt = [x for x in links[cur] if x is not prev]
            if len(links[cur]) < 2 or not nxt or nxt[0] is start:
                break
            prev, cur = cur, nxt[0]
        chain = [cur]
        seen.add(cur)
        prev = None
        closed = False
        while True:
            nxt = [x for x in links[chain[-1]] if x is not prev and x not in seen]
            if not nxt:
                closed = len(chain) > 2 and chain[0] in links[chain[-1]]
                break
            prev = chain[-1]
            chain.append(nxt[0])
            seen.add(nxt[0])
        pts = [seg_of_edge[e] for e in chain]
        length = sum((b - a).length for a, b in zip(pts, pts[1:]))
        if length >= 4.0 * quad_edge:
            lines.append({"points": [list(p) for p in pts], "closed": closed, "hard": True})
    return lines


def write_sizing(job_dir, traced_path, verts, ratio):
    """Per-vertex quad size factors of the traced mesh -> <traced>.sizing, read by the STS build
    of quadPatches: each patch's target edge = base edge x the mean factor of its vertices.
    painted 1 -> 1/ratio (smaller quads), 0 -> 1. QRemeshify's own build ignores the file."""
    dens_path = os.path.join(job_dir, "density.npy")
    if not os.path.isfile(dens_path):
        return False
    TV, _F = read_obj(traced_path)
    out = [1.0 / (1.0 + (ratio - 1.0) * d) for d in _density_at([Vector(p) for p in TV], verts, np.load(dens_path))]
    with open(os.path.splitext(traced_path)[0] + ".sizing", "w") as f:
        f.write(f"{len(out)}\n" + "".join(f"{x:.5f}\n" for x in out))
    print(f"STS_INFO sizing: {len(out)} vertices, factor {min(out):.2f}..{max(out):.2f}", flush=True)
    return True


def check_symmetry(bm, axes, quad_edge):
    """Warn when the shape is not mirror-symmetric: the mirrored half then floats off the real
    surface and 'Fit to Source' folds it (head scan turned a few degrees: up to 10 mm, 10-10)."""
    from mathutils.bvhtree import BVHTree
    if not any(axes):
        return
    co = np.array([v.co for v in bm.verts])
    tree = BVHTree.FromBMesh(bm)
    sample = co[:: max(1, len(co) // 5000)]
    for i, on in enumerate(axes):
        if not on:
            continue
        m = sample.copy()
        m[:, i] *= -1.0
        d = np.array([tree.find_nearest(p)[3] for p in m])   # to the surface, not to a vertex
        off = float(np.percentile(d, 95))
        if off > 0.25 * quad_edge:
            print(f"STS_WARN {'XYZ'[i]} {off:.6g} {off / quad_edge:.2f}", flush=True)


def cut_symmetry(bm, axes):
    for i, on in enumerate(axes):
        if not on:
            continue
        no = [0.0, 0.0, 0.0]
        no[i] = 1.0
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=(0, 0, 0), plane_no=no,
                               clear_outer=False, clear_inner=True)


def write_obj(bm, path):
    bm.verts.index_update()
    with open(path, "w") as f:
        f.write("".join(f"v {v.co.x:.6f} {v.co.y:.6f} {v.co.z:.6f}\n" for v in bm.verts))
        f.write("".join("f " + " ".join(str(v.index + 1) for v in face.verts) + "\n" for face in bm.faces))


def _resample(points, closed, step):
    """Polyline -> points every `step` (keeps both ends of an open line)."""
    pts = [Vector(p) for p in points]
    if closed:
        pts.append(pts[0])
    out = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        if seg == 0.0:
            continue
        t = step - carry
        while t <= seg:
            out.append(a.lerp(b, t / seg))
            t += step
        carry = seg - (t - step)
    if not closed and (out[-1] - pts[-1]).length > 1e-9:
        out.append(pts[-1])
    if closed and len(out) > 2 and (out[-1] - out[0]).length < 0.5 * step:
        out.pop()
    return out


def _segments(adj):
    """Split a line graph at its nodes (degree != 2): lists of vertices, node to node.
    Loops without any node come out once, starting and ending at the same vertex."""
    seen = set()
    out = []
    nodes = [v for v in adj if len(adj[v]) != 2]
    for n in nodes:
        for w in adj[n]:
            if (n, w) in seen:
                continue
            seg = [n, w]
            seen.add((n, w))
            while len(adj[seg[-1]]) == 2:
                nxt = [x for x in adj[seg[-1]] if x is not seg[-2]]
                if not nxt:
                    break
                seen.add((seg[-1], nxt[0]))
                seg.append(nxt[0])
            seen.add((seg[-1], seg[-2]))
            out.append(seg)
    for v in adj:                      # pure loops
        if len(adj[v]) == 2 and not any((v, w) in seen for w in adj[v]):
            seg = [v]
            prev = None
            cur = v
            while True:
                nxt = [x for x in adj[cur] if x is not prev][0]
                seen.add((cur, nxt))
                seen.add((nxt, cur))
                prev, cur = cur, nxt
                seg.append(cur)
                if cur is v:
                    break
            out.append(seg)
    return out


def _join_straight(segments, adj, min_turn=0.7):
    """Join segments through a junction where one continues the other almost straight
    (direction dot < -min_turn, measured a few vertices away); cube corners stay split."""
    def direction(seg, at_start):
        a = seg[0] if at_start else seg[-1]
        b = seg[min(3, len(seg) - 1)] if at_start else seg[max(-4, -len(seg))]
        d = b.co - a.co
        return d.normalized() if d.length > 0 else d
    segs = [list(s) for s in segments]
    alive = [True] * len(segs)
    changed = True
    while changed:
        changed = False
        ends = {}
        for i, sg in enumerate(segs):
            if not alive[i] or sg[0] is sg[-1]:
                continue
            ends.setdefault(sg[0], []).append((i, True))
            ends.setdefault(sg[-1], []).append((i, False))
        for node, inc in ends.items():
            if len(adj.get(node, ())) < 3 or len(inc) < 2:
                continue
            best = None
            for x in range(len(inc)):
                for y in range(x + 1, len(inc)):
                    (i, si), (j, sj) = inc[x], inc[y]
                    if i == j:
                        continue
                    dot = direction(segs[i], si).dot(direction(segs[j], sj))
                    if dot < -min_turn and (best is None or dot < best[0]):
                        best = (dot, i, si, j, sj)
            if best:
                _, i, si, j, sj = best
                a = segs[i][::-1] if si else segs[i]          # ... node
                b = segs[j] if sj else segs[j][::-1]          # node ...
                segs[i] = a + b[1:]
                alive[j] = False
                changed = True
                break
    return [s for s, ok in zip(segs, alive) if ok]


def detect_creases(bm, angle, quad_edge, min_quads):
    """Crease lines (ridges and valleys) of the proxy as smooth polylines.

    Edges sharper than `angle` come in short dashes (triangle edges zigzag across a crease).
    Per sign (convex = ridge, concave = valley): join the dashes into chains, bridge an end to
    a chain ahead of it within 2 quad edges, take each chain's longest path, drop the ones
    shorter than min_quads quad edges, smooth them and put them back on the surface."""
    import heapq
    from mathutils import kdtree
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromBMesh(bm)
    lines = []
    for convex in (False, True):
        adj = {}
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.is_convex == convex and e.calc_face_angle(0.0) > angle:
                u, v = e.verts
                adj.setdefault(u, set()).add(v)
                adj.setdefault(v, set()).add(u)
        if not adj:
            continue

        def components():
            comp, c = {}, 0
            for s in adj:
                if s in comp:
                    continue
                stack = [s]
                comp[s] = c
                while stack:
                    x = stack.pop()
                    for y in adj[x]:
                        if y not in comp:
                            comp[y] = c
                            stack.append(y)
                c += 1
            return comp
        comp = components()
        verts = list(adj)
        kd = kdtree.KDTree(len(verts))
        for i, v in enumerate(verts):
            kd.insert(v.co, i)
        kd.balance()
        for v in [v for v in verts if len(adj[v]) == 1]:
            ahead = (v.co - next(iter(adj[v])).co).normalized()
            best = None
            for _co, i, d in kd.find_range(v.co, 2.0 * quad_edge):
                w = verts[i]
                if comp[w] == comp[v] or d < 1e-12 or (w.co - v.co).normalized().dot(ahead) < 0.5:
                    continue
                if best is None or d < best[1]:
                    best = (w, d)
            if best:
                adj[v].add(best[0])
                adj[best[0]].add(v)
        # prune spurs (zigzag side branches) shorter than one quad edge
        for _ in range(4):
            for seg in _segments(adj):
                ends = (seg[0], seg[-1])
                length = sum((x.co - y.co).length for x, y in zip(seg, seg[1:]))
                leaf = [v for v in ends if len(adj[v]) == 1]
                hub = [v for v in ends if len(adj[v]) >= 3]
                if leaf and hub and length < quad_edge:
                    for x, y in zip(seg, seg[1:]):
                        adj[x].discard(y)
                        adj[y].discard(x)
            for v in [v for v in adj if not adj[v]]:
                del adj[v]
        for chain in _join_straight(_segments(adj), adj):
            length = sum((x.co - y.co).length for x, y in zip(chain, chain[1:]))
            if length < min_quads * quad_edge:
                continue
            pts = [v.co.copy() for v in chain]
            for _ in range(6):
                pts = [pts[0]] + [tree.find_nearest((pts[i - 1] + 2 * pts[i] + pts[i + 1]) / 4)[0]
                                  for i in range(1, len(pts) - 1)] + [pts[-1]]
            lines.append({"points": [list(p) for p in pts], "convex": convex, "length": length})
    return lines


def _trim_close(lines, gap, min_length):
    """Longest lines first; drop the parts of a line that run within `gap` of a line already
    kept, keep what is left if it is at least min_length. Two creases closer than a quad
    (upper and lower eyelid, 1 mm apart on the head scan) would leave a sliver of patch that
    QuadWild folds, and they cap how coarse the result can get."""
    from mathutils import kdtree

    def length(run):
        return sum((b - a).length for a, b in zip(run, run[1:]))
    kept, kept_pts = [], []
    for run, closed in sorted(lines, key=lambda l: -length(l[0])):
        if kept_pts:
            kd = kdtree.KDTree(len(kept_pts))
            for i, p in enumerate(kept_pts):
                kd.insert(p, i)
            kd.balance()
            free = [kd.find(p)[2] >= gap for p in run]
        else:
            free = [True] * len(run)
        if all(free):
            pieces = [(run, closed)]
        else:
            pieces, cur = [], []
            for p, ok in zip(run, free):
                if ok:
                    cur.append(p)
                elif cur:
                    pieces.append((cur, False))
                    cur = []
            if cur:
                pieces.append((cur, False))
        for piece, cl in pieces:
            if len(piece) >= 2 and length(piece) >= min_length:
                kept.append((piece, cl))
                kept_pts.extend(piece)
    return kept


def count_folds(bm):
    for f in bm.faces:
        f.normal_update()
    return sum(1 for e in bm.edges if len(e.link_faces) == 2
               and e.link_faces[0].normal.dot(e.link_faces[1].normal) < -0.5)


def guide_tangents(bm, guides, step, axes):
    """Resampled guide points on the proxy with their unit tangents: [(point, tangent)]."""
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromBMesh(bm)
    out = []
    for g in guides:
        pts = []
        for p in _resample(g["points"], g["closed"], 0.5 * step):
            if any(on and p[i] < -1e-6 for i, on in enumerate(axes)):
                continue
            hit = tree.find_nearest(p)[0]
            if hit is not None:
                pts.append(hit)
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]
            b = pts[min(len(pts) - 1, i + 1)]
            t = b - a
            if t.length > 0:
                out.append((p, t.normalized()))
    return out


def steer_field(rem_obj, rosy_path, samples, radius):
    """Turn QuadWild's cross field toward the guide tangents near the guides (soft guides).

    A cross field is 4-symmetric: blend in the 4x-angle space, weight 1 on the line fading
    to 0 at `radius`. Proven 10-10 on an egg: a 45-degree field gave 100% diagonal edges."""
    from mathutils import kdtree
    if not samples:
        return 0
    V, F = read_obj(rem_obj)
    with open(rosy_path) as f:
        lines = f.read().split()
    nf, ndir = int(lines[0]), int(lines[1])
    if nf != len(F):
        print(f"STS_INFO field size mismatch {nf} != {len(F)}: guides not steered", flush=True)
        return 0
    dirs = np.array(lines[2:2 + 3 * nf], dtype=np.float64).reshape(-1, 3)
    kd = kdtree.KDTree(len(samples))
    for i, (p, _t) in enumerate(samples):
        kd.insert(p, i)
    kd.balance()
    changed = 0
    for fi, f in enumerate(F):
        a, b, c = (Vector(V[f[0]]), Vector(V[f[1]]), Vector(V[f[2]]))
        center = (a + b + c) / 3
        _co, idx, d = kd.find(center)
        if d >= radius:
            continue
        w = 1.0 - d / radius
        n = (b - a).cross(c - a).normalized()
        e1 = Vector(dirs[fi])
        e1 = (e1 - n * e1.dot(n)).normalized()
        e2 = n.cross(e1)
        t = samples[idx][1]
        th = math.atan2(t.dot(e2), t.dot(e1))
        zr = (1.0 - w) + w * math.cos(4 * th)
        zi = w * math.sin(4 * th)
        ang = math.atan2(zi, zr) / 4.0
        nd = e1 * math.cos(ang) + e2 * math.sin(ang)
        dirs[fi] = (nd.x, nd.y, nd.z)
        changed += 1
    with open(rosy_path, "w") as f:
        f.write(f"{nf}\n{ndir}\n" + "".join(f"{x:.6f} {y:.6f} {z:.6f}\n" for x, y, z in dirs))
    return changed


def embed_guides(bm, guides, step, axes, quad_edge):
    """Make every guide polyline an exact chain of proxy edges and return those edges.

    1. resample each line, project it onto the proxy (drop the mirrored-away side)
    2. split the triangles near the line once, so the chain can follow it closely
    3. shortest edge path between consecutive samples, preferring edges near the line
    4. move the path vertices onto the line, relax their neighbours back onto the surface
    QuadWild then gets the chain as feature edges and lays a row of quad edges on it."""
    from mathutils.bvhtree import BVHTree
    from mathutils import kdtree
    import heapq

    tree = BVHTree.FromBMesh(bm)
    lines = []
    for g in guides:
        pts = []
        for p in _resample(g["points"], g["closed"], 0.5 * step):
            if any(on and p[i] < -1e-6 for i, on in enumerate(axes)):
                pts.append(None)              # mirrored-away side: breaks the line here
                continue
            hit = tree.find_nearest(p)
            pts.append(hit[0] if hit[0] is not None else None)
        run = []
        for p in pts + [None]:
            if p is None:
                if len(run) >= 2:
                    lines.append((run, g["closed"] and len(run) == len(pts)))
                run = []
            else:
                run.append(p)
    lines = _trim_close(lines, 0.8 * quad_edge, 2.0 * quad_edge)
    if not lines:
        return set()

    samples = [p for run, _ in lines for p in run]
    kd = kdtree.KDTree(len(samples))
    for i, p in enumerate(samples):
        kd.insert(p, i)
    kd.balance()

    # 2. refine near the lines
    near = [f for f in bm.faces if any(kd.find(v.co)[2] < 1.5 * step for v in f.verts)]
    edges = list({e for f in near for e in f.edges})
    if edges:
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    surface = BVHTree.FromBMesh(bm)
    bm.verts.ensure_lookup_table()
    vkd = kdtree.KDTree(len(bm.verts))
    for v in bm.verts:
        vkd.insert(v.co, v.index)
    vkd.balance()

    def line_dist(co):
        return kd.find(co)[2]

    def path(a, b):
        if a is b:
            return [a]
        best = {a: 0.0}
        prev = {}
        heap = [(0.0, id(a), a)]
        limit = 6.0 * max((a.co - b.co).length, step)
        while heap:
            d, _, v = heapq.heappop(heap)
            if v is b:
                break
            if d > best.get(v, 1e30) or d > limit:
                continue
            for e in v.link_edges:
                w = e.other_vert(v)
                mid = 0.5 * (v.co + w.co)
                nd = d + e.calc_length() * (1.0 + 8.0 * line_dist(mid) / step)
                if nd < best.get(w, 1e30):
                    best[w] = nd
                    prev[w] = v
                    heapq.heappush(heap, (nd, id(w), w))
        if b not in prev:
            return [a, b] if b in {e.other_vert(a) for e in a.link_edges} else [a]
        out = [b]
        while out[-1] is not a:
            out.append(prev[out[-1]])
        return out[::-1]

    for f in bm.faces:
        f.normal_update()
    normals0 = {f: f.normal.copy() for f in bm.faces}
    original = {v: v.co.copy() for v in bm.verts}
    feature = set()
    on_line = set()
    for run, closed in lines:
        anchors = []
        for p in run:
            v = bm.verts[vkd.find(p)[1]]
            if not anchors or anchors[-1] is not v:
                anchors.append(v)
        if closed and len(anchors) > 2:
            anchors.append(anchors[0])
        chain = [anchors[0]]
        for a, b in zip(anchors, anchors[1:]):
            chain += path(a, b)[1:]
        # 4. onto the line, keeping the chain's order along it: each vertex goes to the nearest
        #    point at or after the previous one (arc length never runs backwards), so two
        #    neighbours cannot swap places and turn a triangle over
        pts = run + [run[0]] if closed else run
        cum = [0.0]
        for p0, p1 in zip(pts, pts[1:]):
            cum.append(cum[-1] + (p1 - p0).length)
        total = cum[-1]

        def at(sv):
            sv = min(max(sv, 0.0), total)
            k = max(0, min(len(cum) - 2, next((i for i in range(1, len(cum)) if cum[i] >= sv), len(cum) - 1) - 1))
            seg = cum[k + 1] - cum[k]
            return pts[k].lerp(pts[k + 1], 0.0 if seg == 0 else (sv - cum[k]) / seg)

        def nearest_param(co, lo):
            best = None
            for k in range(len(pts) - 1):
                if cum[k + 1] < lo:
                    continue
                p0, p1 = pts[k], pts[k + 1]
                ab = p1 - p0
                t = max(0.0, min(1.0, (co - p0).dot(ab) / max(ab.length_squared, 1e-20)))
                sv = max(cum[k] + t * (cum[k + 1] - cum[k]), lo)
                d = (at(sv) - co).length_squared
                if best is None or d < best[0]:
                    best = (d, sv)
                if cum[k] > lo + 4.0 * step:      # far enough ahead
                    break
            return best[1] if best else lo
        params = []
        last = -1.0
        for v in chain:
            sv = nearest_param(v.co, max(last, 0.0)) if last >= 0 else nearest_param(v.co, 0.0)
            params.append(sv)
            last = sv
        if closed and len(chain) > 1 and chain[-1] is chain[0]:
            params[-1] = total
        # spread runs of equal parameters evenly up to the next distinct one
        i = 0
        while i < len(params):
            j = i
            while j + 1 < len(params) and params[j + 1] - params[i] < 1e-9:
                j += 1
            if j > i:
                nxt = params[j + 1] if j + 1 < len(params) else min(total, params[i] + 0.5 * step)
                for k in range(i, j + 1):
                    params[k] = params[i] + (nxt - params[i]) * (k - i) / (j - i + 1)
            i = j + 1
        for v, sv in zip(chain, params):
            if v.is_boundary or v in on_line:
                continue
            v.co = at(sv)
            on_line.add(v)
        for a, b in zip(chain, chain[1:]):
            if a is b:
                continue
            for e in a.link_edges:
                if e.other_vert(a) is b:
                    feature.add(e)
    if os.environ.get("STS_DEBUG"):
        mv = sorted((v.co - original[v]).length / step for v in on_line)
        if mv:
            print(f"STS_DEBUG snap move/step: median {mv[len(mv)//2]:.2f} p90 {mv[int(len(mv)*0.9)]:.2f} max {mv[-1]:.2f}", flush=True)
        for f in {f for v in on_line for f in v.link_faces}:
            f.normal_update()
        print(f"STS_DEBUG inverted right after snap: {sum(1 for f in {f for v in on_line for f in v.link_faces} if f.normal.dot(normals0[f]) < -0.2)}", flush=True)
    # (relaxing the neighbours here turned more triangles over than it fixed: 5 -> 17 on the
    # egg ring, 10-10; only the moves that turn a triangle over are undone below)
    ring = set()
    # undo the move where a triangle still turned over (the chain then zigzags a little there)
    moved = on_line | ring
    reverted = 0
    for _ in range(6):
        bad = [f for f in {f for v in moved for f in v.link_faces}
               if f.normal_update() is None and f.normal.dot(normals0.get(f, f.normal)) < -0.2]
        if not bad:
            break
        for f in bad:
            for v in f.verts:
                if v in original and (v.co - original[v]).length > 0:
                    v.co = original[v]
                    reverted += 1
    print(f"STS_INFO guides: {len(lines)} lines -> {len(feature)} feature edges, {reverted} moves undone", flush=True)
    return feature


def write_sharp(bm, path, angle, min_length, forced=()):
    """QuadWild .sharp: one line 'convex,face,edge-in-face' per feature edge (borders too).

    angle None: no automatic sharp edges, only `forced` (guide) edges and the borders.
    Sharp chains shorter than min_length are dropped: on a scan the decimated proxy has
    thousands of short 'sharp' creases (2.7 m of them on the head, 10-10) and every one cuts
    the patches, so the face count can no longer go down to the target."""
    bm.faces.index_update()
    bm.verts.index_update()
    cand = [] if angle is None else [e for e in bm.edges if e.link_faces and not e.is_boundary
                                     and len(e.link_faces) == 2 and e.calc_face_angle(0.0) > angle]
    parent = list(range(len(bm.verts)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in cand:
        a, b = root(e.verts[0].index), root(e.verts[1].index)
        if a != b:
            parent[a] = b
    length = {}
    for e in cand:
        r = root(e.verts[0].index)
        length[r] = length.get(r, 0.0) + e.calc_length()
    keep = [e for e in cand if length[root(e.verts[0].index)] >= min_length]
    keep += [e for e in bm.edges if e.is_boundary]
    keep = list(dict.fromkeys(keep + [e for e in forced if e.is_valid and e.link_faces]))
    lines = []
    for e in keep:
        f = e.link_faces[0]
        k = list(f.edges).index(e)
        lines.append(f"{1 if e.is_convex else 0},{f.index},{k}")
    with open(path, "w") as fh:
        fh.write(f"{len(lines)}\n" + "".join(s + "\n" for s in lines))
    print(f"STS_INFO sharp: {len(cand)} candidate edges, kept {len(keep)}", flush=True)
    return len(lines)


def read_obj(path):
    V, F = [], []
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("f "):
                F.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    return np.array(V, dtype=np.float64), F


def mean_edge_and_area(path):
    V, F = read_obj(path)
    edges = set()
    area = 0.0
    for f in F:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            edges.add((a, b) if a < b else (b, a))
        for i in range(1, len(f) - 1):
            area += 0.5 * np.linalg.norm(np.cross(V[f[i]] - V[f[0]], V[f[i + 1]] - V[f[0]]))
    e = np.array(list(edges))
    return float(np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1).mean()), area


def count_faces(path):
    n = q = 0
    with open(path) as f:
        for line in f:
            if line.startswith("f "):
                n += 1
                q += len(line.split()) == 5
    return n, q


# --- main ---------------------------------------------------------------------------------------

def main(job_dir):
    t0 = time.time()
    job = json.load(open(os.path.join(job_dir, "job.json")))
    verts = np.load(os.path.join(job_dir, "verts.npy")).astype(np.float32)
    tris = np.load(os.path.join(job_dir, "tris.npy")).astype(np.int32)
    progress(0.02, "Reading the surface")

    area = surface_area(verts, tris)
    closed = open_edge_count(tris) == 0
    mirrored = sum(1 for a in job["symmetry"] if a)
    # what QuadWild sees is the cut piece: its share of the face budget
    target_piece = max(50, job["target_faces"] / (2 ** mirrored))
    # the proxy is decimated whole and cut afterwards: budget per piece times the pieces
    per_piece = min(job["proxy_max"], max(job["proxy_min"], job["proxy_per_face"] * target_piece))
    job["proxy_tris"] = int(per_piece * 2 ** mirrored)

    me = mesh_from_arrays(verts, tris)
    obj = bpy.data.objects.new("sts_quad_src", me)
    bpy.context.scene.collection.objects.link(obj)
    progress(0.05, "Building the proxy")
    surface = build_proxy(obj, job, closed, area)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    repair_folds(bm, surface)
    if job.get("mode") == "detect":
        progress(0.6, "Finding crease lines")
        lines = detect_creases(bm, job["crease_angle"], math.sqrt(area / job["target_faces"]), job["crease_min_quads"])
        with open(os.path.join(job_dir, "creases.json"), "w") as f:
            json.dump(lines, f)
        print(f"STS_INFO total {time.time() - t0:.1f}s", flush=True)
        print(f"STS_RESULT {len(lines)} 0", flush=True)
        return
    check_symmetry(bm, job["symmetry"], math.sqrt(area / job["target_faces"]))
    cut_symmetry(bm, job["symmetry"])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    if len(bm.faces) < 20:
        print("STS_ERROR The surface is too small after cutting", flush=True)
        return
    forced = set()
    soft = []
    job.setdefault("guides", [])
    if job.get("density_edges") and os.path.isfile(os.path.join(job_dir, "density.npy")):
        progress(0.12, "Finding density edges")
        contours = density_contours(bm, verts, np.load(os.path.join(job_dir, "density.npy")),
                                    math.sqrt(area / job["target_faces"]))
        job["guides"] += contours
        print(f"STS_INFO density edges: {len(contours)} lines", flush=True)
    if job["guides"]:
        progress(0.15, "Embedding guide lines")
        bm.edges.ensure_lookup_table()
        step = sum(e.calc_length() for e in bm.edges) / len(bm.edges)
        quad_edge = math.sqrt(area / job["target_faces"])
        mode = job.get("guide_mode", "soft")
        hard_min = job.get("hard_min_quads", 10.0) * quad_edge

        def g_len(g):
            pts = [Vector(p) for p in g["points"]]
            return sum((b - a).length for a, b in zip(pts, pts[1:]))
        hard = [g for g in job["guides"] if g.get("hard") or mode == "hard"
                or (mode == "hybrid" and (g["closed"] or g_len(g) >= hard_min))]
        soft_g = [g for g in job["guides"] if g not in hard]
        # soft guides first: their samples are positions, so later refinement does not matter
        soft = guide_tangents(bm, soft_g, step, job["symmetry"])
        if hard:
            forced = embed_guides(bm, hard, step, job["symmetry"], quad_edge)
        print(f"STS_INFO guides: {len(hard)} hard, {len(soft_g)} soft; proxy folds {count_folds(bm)}", flush=True)
    mesh_path = os.path.join(job_dir, "proxy.obj")
    write_obj(bm, mesh_path)
    base = os.path.splitext(mesh_path)[0]
    has_feature = False
    if job["sharp"] or forced:
        n = write_sharp(bm, base + "_rem.sharp", job["sharp_angle"] if job["sharp"] else None,
                        job["sharp_min_quads"] * math.sqrt(area / job["target_faces"]), forced)
        has_feature = n > 0
    print(f"STS_INFO proxy {len(bm.faces)} tris, closed={closed}, area={area:.4g}", flush=True)
    bm.free()

    lib_dir = job["engine"]
    qw, qp = load_engine(lib_dir)
    progress(0.20, "Computing the field")
    params = Parameters(remesh=False, sharpAngle=math.degrees(job["sharp_angle"]) if job["sharp"] else -1.0,
                        alpha=0.01, scaleFact=1.0, hasFeature=has_feature, hasField=False)
    qw.remeshAndField2(ctypes.byref(params), mesh_path.encode(), (base + "_rem.sharp").encode(),
                       (base + "_rem.rosy").encode())
    if soft:
        n = steer_field(base + "_rem.obj", base + "_rem.rosy", soft, job.get("steer_quads", 1.5) * math.sqrt(area / job["target_faces"]))
        print(f"STS_INFO field steered on {n} faces", flush=True)
    progress(0.50, "Tracing patches")
    if not qw.trace2((base + "_rem").encode()):
        print("STS_ERROR Tracing failed", flush=True)
        return

    traced = base + "_rem_p0.obj"
    sized = write_sizing(job_dir, traced, verts, job.get("detail_ratio", 2.5))
    mean_edge, traced_area = mean_edge_and_area(traced)
    keep = []
    qrp = qr_parameters(lib_dir, job, keep)
    out = base + "_rem_p0_0_quadrangulation" + ("_smooth" if job["smooth"] else "") + ".obj"
    # faces ~ area / edge^2 for a regular quad grid; QuadWild lands about 1.4x denser than
    # that (head scan, 10-10), then each pass corrects from the real count
    edge = math.sqrt(FILL * traced_area / target_piece)
    scale = edge / mean_edge
    best = None
    for attempt in range(job["passes"]):
        progress(0.65 + 0.1 * attempt, f"Quadrangulating (pass {attempt + 1})")
        qp.quadPatches(traced.encode(), ctypes.byref(qrp), ctypes.c_float(scale), 0, job["smooth"])
        n, q = count_faces(out)
        print(f"STS_INFO pass {attempt + 1}: scale {scale:.3f} -> {n} faces", flush=True)
        if n == 0:
            break
        err = abs(n / target_piece - 1.0)
        if best is None or err < best[0]:
            best = (err, n, q)
            os.replace(out, os.path.join(job_dir, "result.obj"))
        if err < job["tolerance"]:
            break
        scale *= math.sqrt(n / target_piece)
    if best is None:
        print("STS_ERROR QuadWild produced no faces", flush=True)
        return
    untangle_result(os.path.join(job_dir, "result.obj"), mesh_path)
    print(f"STS_INFO total {time.time() - t0:.1f}s", flush=True)
    print(f"STS_RESULT {best[1]} {best[2]}", flush=True)


if __name__ == "__main__":
    try:
        main(sys.argv[sys.argv.index("--") + 1])
    except Exception as exc:  # report, then let the parent see a non-zero exit
        print(f"STS_ERROR {type(exc).__name__}: {exc}", flush=True)
        raise
