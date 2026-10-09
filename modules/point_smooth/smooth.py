"""Point smoothing: the selection is split into pieces and every piece is
handled on its own — open chain -> straighten, closed loop -> loop smoothing,
2D patch -> Laplacian relax.

Replaces: point_smooth_rap_all.py (its _loop_targets / _mesh_laplacian /
_project_tangent / _surface_* helpers, reworked per the new spec: pieces
instead of one global decision, no LINE mode, a loop step that actually
smooths and keeps its size).
"""

import bmesh
from mathutils import Vector

RELAX = 0.5        # how far a loop point moves toward its neighbours' average
RELAX_STEPS = 2    # relax passes per iteration


# ---------------------------------------------------------------- targets

def _line_targets(positions):
    """Evenly spaced points on the line between the first and the last."""
    n = len(positions) - 1
    if n < 1:
        return [p.copy() for p in positions]
    p0, p1 = positions[0], positions[-1]
    return [p0.lerp(p1, i / n) for i in range(n + 1)]


def _even_spaced(positions):
    """Resample a closed loop at equal arc-length intervals."""
    n = len(positions)
    segs = [(positions[(i + 1) % n] - positions[i]).length for i in range(n)]
    total = sum(segs)
    if total < 1e-12:
        return [p.copy() for p in positions]
    cumul = [0.0]
    for s in segs:
        cumul.append(cumul[-1] + s)
    interval = total / n
    result = [positions[0].copy()]
    for i in range(1, n):
        td = i * interval
        for j in range(n):
            lo, hi = cumul[j], cumul[j + 1]
            if lo <= td <= hi or j == n - 1:
                span = hi - lo
                t = (td - lo) / span if span > 1e-12 else 0.0
                result.append(positions[j].lerp(positions[(j + 1) % n], max(0.0, min(1.0, t))))
                break
    return result


def _loop_step(positions, strength):
    """One loop iteration: even spacing -> relax to the neighbours' average ->
    restore the loop's size (mean distance from its centre). Unlike the old
    'even spacing along the current polyline' this keeps changing the shape."""
    n = len(positions)
    c0 = sum(positions, Vector()) / n
    r0 = sum((p - c0).length for p in positions) / n
    pos = _even_spaced(positions)
    for _ in range(RELAX_STEPS):
        pos = [pos[i].lerp((pos[i - 1] + pos[(i + 1) % n]) * 0.5, RELAX) for i in range(n)]
    c = sum(pos, Vector()) / n
    r = sum((p - c).length for p in pos) / n
    if r0 > 1e-12 and r > 1e-12:
        k = r0 / r
        pos = [c + (p - c) * k for p in pos]
    return [p.lerp(t, strength) for p, t in zip(positions, pos)]


# ---------------------------------------------------------------- mesh

def _mesh_pieces(bm):
    """Selected vertices split into pieces connected through edges between
    selected vertices. Returns (adj, pieces)."""
    sel = [v for v in bm.verts if v.select]
    sel_set = set(sel)
    adj = {v: [e.other_vert(v) for e in v.link_edges if e.other_vert(v) in sel_set] for v in sel}
    pieces = []
    seen = set()
    for v in sel:
        if v in seen:
            continue
        seen.add(v)
        stack, comp = [v], []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for n in adj[cur]:
                if n not in seen:
                    seen.add(n)
                    stack.append(n)
        pieces.append(comp)
    return adj, pieces


def _piece_kind(comp, adj):
    if len(comp) < 3:
        return None
    degs = [len(adj[v]) for v in comp]
    if all(d == 2 for d in degs):
        return 'LOOP'
    if degs.count(1) == 2 and degs.count(2) == len(comp) - 2:
        return 'CHAIN'
    return 'AREA'


def _walk_chain(comp, adj):
    start = next(v for v in comp if len(adj[v]) == 1)
    chain, prev, cur = [start], None, start
    for _ in range(len(comp) + 1):
        nxt = next((n for n in adj[cur] if n is not prev), None)
        if nxt is None:
            break
        chain.append(nxt)
        prev, cur = cur, nxt
    return chain


def _walk_loop(comp, adj):
    start = comp[0]
    loop, prev, cur = [start], None, start
    for _ in range(len(comp) + 1):
        nxt = next((n for n in adj[cur] if n is not prev), None)
        if nxt is None or nxt is start:
            break
        loop.append(nxt)
        prev, cur = cur, nxt
    return loop


def _laplacian(bm, comp, adj, op):
    """2D piece: Laplacian relax. fix_boundary keeps the outer vertices
    (touching unselected ones or on the mesh border); tangent_smooth moves
    only along the surface."""
    comp_set = set(comp)
    anchors = {v: [e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in comp_set]
               for v in comp}
    fixed = {v for v in comp if anchors[v] or v.is_boundary} if op.fix_boundary else set()
    for _ in range(op.iterations):
        if op.tangent_smooth:
            bm.normal_update()
            normals = {v: v.normal.copy() for v in comp}
        snap = {v: v.co.copy() for v in comp}
        new_pos = {}
        for v in comp:
            pos = snap[v]
            if v in fixed:
                new_pos[v] = pos
                continue
            nbrs = [snap[n] for n in adj[v]] + [n.co.copy() for n in anchors[v]]
            if not nbrs:
                new_pos[v] = pos
                continue
            avg = sum(nbrs, Vector()) / len(nbrs)
            if op.tangent_smooth:
                delta = avg - pos
                nrm = normals[v]
                if nrm.length > 1e-9:
                    nrm.normalize()
                    delta -= nrm * delta.dot(nrm)
                new_pos[v] = pos + delta * op.strength
            else:
                new_pos[v] = pos.lerp(avg, op.strength)
        for v, p in new_pos.items():
            v.co = p


def smooth_mesh(obj, op):
    bm = bmesh.from_edit_mesh(obj.data)
    adj, pieces = _mesh_pieces(bm)
    processed = False
    for comp in pieces:
        kind = _piece_kind(comp, adj)
        if kind is None:
            continue
        processed = True
        if kind == 'CHAIN':
            ordered = _walk_chain(comp, adj)
            for _ in range(op.iterations):
                targets = _line_targets([v.co.copy() for v in ordered])
                for v, t in zip(ordered, targets):
                    v.co = v.co.lerp(t, op.strength)
        elif kind == 'LOOP':
            ordered = _walk_loop(comp, adj)
            for _ in range(op.iterations):
                new_pos = _loop_step([v.co.copy() for v in ordered], op.strength)
                for v, p in zip(ordered, new_pos):
                    v.co = p
        else:
            _laplacian(bm, comp, adj, op)
    if processed:
        bmesh.update_edit_mesh(obj.data)
    return processed


# ---------------------------------------------------------------- curves

def _runs(flags, cyclic):
    """Runs of consecutive selected indices; on a cyclic spline a run that
    crosses the head/tail border is joined into one."""
    n = len(flags)
    idx = [i for i in range(n) if flags[i]]
    if not idx:
        return []
    runs, cur = [], [idx[0]]
    for i in idx[1:]:
        if i == cur[-1] + 1:
            cur.append(i)
        else:
            runs.append(cur)
            cur = [i]
    runs.append(cur)
    if cyclic and len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == n - 1:
        runs[0] = runs.pop() + runs[0]
    return runs


def _bezier_run(sel, is_loop, op):
    n = len(sel)
    for _ in range(op.iterations):
        positions = [p.co.copy() for p in sel]
        if is_loop:
            new_pos = _loop_step(positions, op.strength)
        else:
            new_pos = [p.lerp(t, op.strength) for p, t in zip(positions, _line_targets(positions))]
        for pt, old, new in zip(sel, positions, new_pos):
            delta = new - old
            pt.co = new
            pt.handle_left += delta
            pt.handle_right += delta
        # handle directions along the run's tangent (ends of an open run keep theirs)
        for i in range(n):
            if not is_loop and i in (0, n - 1):
                continue
            prev_co = sel[i - 1].co
            next_co = sel[(i + 1) % n].co
            tangent = next_co - prev_co
            if tangent.length < 1e-9:
                continue
            t = tangent.normalized()
            pt = sel[i]
            if op.auto_handle_length:
                len_r = (next_co - pt.co).length / 3.0
                len_l = (pt.co - prev_co).length / 3.0
            else:
                len_r = (pt.handle_right - pt.co).length
                len_l = (pt.handle_left - pt.co).length
            pt.handle_right = pt.co + t * len_r
            pt.handle_left = pt.co - t * len_l
            pt.handle_left_type = 'FREE'
            pt.handle_right_type = 'FREE'


def _point_run(pts, run, is_loop, op):
    """NURBS / Poly points: co has 4 components; the weight (w) is untouched."""
    for _ in range(op.iterations):
        positions = [Vector(pts[i].co[:3]) for i in run]
        if is_loop:
            new_pos = _loop_step(positions, op.strength)
        else:
            new_pos = [p.lerp(t, op.strength) for p, t in zip(positions, _line_targets(positions))]
        for i, new in zip(run, new_pos):
            p = pts[i]
            p.co = (new.x, new.y, new.z, p.co[3])


def smooth_curve(obj, op):
    processed = False
    for spline in obj.data.splines:
        if spline.type == 'BEZIER':
            pts = list(spline.bezier_points)
            flags = [p.select_control_point for p in pts]
        elif spline.type in ('NURBS', 'POLY'):
            pts = list(spline.points)
            flags = [p.select for p in pts]
        else:
            continue
        cyclic = spline.use_cyclic_u
        for run in _runs(flags, cyclic):
            if len(run) < 3:
                continue
            processed = True
            is_loop = cyclic and len(run) == len(pts)
            if spline.type == 'BEZIER':
                _bezier_run([pts[i] for i in run], is_loop, op)
            else:
                _point_run(pts, run, is_loop, op)
    return processed


# ---------------------------------------------------------------- NURBS surfaces

def _surface_straighten(pts, nu, comp, op):
    us = sorted({u for u, _ in comp})
    vs = sorted({v for _, v in comp})
    if len(vs) == 1:
        line = [(u, vs[0]) for u in us]
    else:
        line = [(us[0], v) for v in vs]
    for _ in range(op.iterations):
        positions = [Vector(pts[v * nu + u].co[:3]) for u, v in line]
        targets = _line_targets(positions)
        for (u, v), p, t in zip(line, positions, targets):
            pt = pts[v * nu + u]
            new = p.lerp(t, op.strength)
            pt.co = (new.x, new.y, new.z, pt.co[3])


def _surface_laplacian(pts, nu, nv, comp, op):
    comp_set = set(comp)
    fixed = set()
    if op.fix_boundary:
        for (u, v) in comp:
            for du, dv in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                u2, v2 = u + du, v + dv
                if not (0 <= u2 < nu and 0 <= v2 < nv) or (u2, v2) not in comp_set:
                    fixed.add((u, v))
                    break
    for _ in range(op.iterations):
        snap = {(u, v): Vector(pts[v * nu + u].co[:3]) for v in range(nv) for u in range(nu)}
        new_pos = {}
        for (u, v) in comp:
            pos = snap[(u, v)]
            if (u, v) in fixed:
                new_pos[(u, v)] = pos
                continue
            nbrs = []
            for du, dv in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                u2, v2 = u + du, v + dv
                # outside the grid: self-anchor (prevents shrinking)
                nbrs.append(snap[(u2, v2)] if 0 <= u2 < nu and 0 <= v2 < nv else pos)
            avg = sum(nbrs, Vector()) / len(nbrs)
            if op.tangent_smooth:
                du = (snap[(u + 1, v)] - snap[(u - 1, v)]) if 0 < u < nu - 1 else \
                     (snap[(u + 1, v)] - pos if u == 0 else pos - snap[(u - 1, v)])
                dv = (snap[(u, v + 1)] - snap[(u, v - 1)]) if 0 < v < nv - 1 else \
                     (snap[(u, v + 1)] - pos if v == 0 else pos - snap[(u, v - 1)])
                nrm = du.cross(dv)
                delta = avg - pos
                if nrm.length > 1e-9:
                    nrm.normalize()
                    delta -= nrm * delta.dot(nrm)
                new_pos[(u, v)] = pos + delta * op.strength
            else:
                new_pos[(u, v)] = pos.lerp(avg, op.strength)
        for (u, v), target in new_pos.items():
            pt = pts[v * nu + u]
            pt.co = (target.x, target.y, target.z, pt.co[3])


def smooth_surface(obj, op):
    processed = False
    for spline in obj.data.splines:
        if spline.type != 'NURBS':
            continue
        nu, nv = spline.point_count_u, spline.point_count_v
        pts = spline.points
        sel = {(u, v) for v in range(nv) for u in range(nu) if pts[v * nu + u].select}
        seen = set()
        for start in sel:
            if start in seen:
                continue
            seen.add(start)
            stack, comp = [start], []
            while stack:
                u, v = stack.pop()
                comp.append((u, v))
                for du, dv in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nb = (u + du, v + dv)
                    if nb in sel and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            if len(comp) < 3:
                continue
            processed = True
            if len({v for _, v in comp}) == 1 or len({u for u, _ in comp}) == 1:
                _surface_straighten(pts, nu, comp, op)
            else:
                _surface_laplacian(pts, nu, nv, comp, op)
    return processed
