"""Inflate and wrap for Point Smooth (Edit Mode: mesh / curve / NURBS surface).

Inflate: push the selected points along their normals, strongest in the
middle of the selection. Wrap: pull them onto another object's evaluated
surface (modifiers included).

Replaces: point_smooth_rap_all.py (its do_inflate_mesh / do_inflate_curve /
do_inflate_surface / do_wrap_mesh / do_wrap_surface / _hop_weights, reworked
per the new spec: settings live on the operator, the wrap target is read from
its evaluated mesh, every object in edit mode is processed, the direction
flip button is gone (amount can be negative) and NURBS point weights stay
untouched).
"""

import math
from collections import deque

import bmesh
from mathutils import Vector

from .smooth import _runs

NEIGH = ((-1, 0), (1, 0), (0, -1), (0, 1))


# ---------------------------------------------------------------- selection

def _mesh_adj(verts):
    """{v: (selected neighbours, anchor neighbours)}."""
    sel = set(verts)
    adj = {}
    for v in verts:
        nbrs, anchors = [], []
        for e in v.link_edges:
            other = e.other_vert(v)
            (nbrs if other in sel else anchors).append(other)
        adj[v] = (nbrs, anchors)
    return adj


def _hop_weights(verts, adj, fix_boundary):
    """sin(pi/2 * d/dmax) over the BFS hop distance d from the selection
    boundary (touching unselected points or on the mesh border).
    fix_boundary off, or no boundary at all -> 1.0 everywhere."""
    if not fix_boundary:
        return {v: 1.0 for v in verts}
    boundary = {v for v in verts if adj[v][1] or v.is_boundary}
    if not boundary:
        return {v: 1.0 for v in verts}
    dist = {v: 0 if v in boundary else None for v in verts}
    queue = deque(boundary)
    while queue:
        cur = queue.popleft()
        for nb in adj[cur][0]:
            if dist[nb] is None:
                dist[nb] = dist[cur] + 1
                queue.append(nb)
    dmax = max((d for d in dist.values() if d is not None), default=1) or 1
    return {v: math.sin(math.pi / 2 * (dist[v] or 0) / dmax) for v in verts}


def _surface_boundary(sel, nu, nv):
    """Grid points touching an unselected point or on the grid border."""
    sel_set = set(sel)
    fixed = set()
    for (u, v) in sel:
        for du, dv in NEIGH:
            u2, v2 = u + du, v + dv
            if not (0 <= u2 < nu and 0 <= v2 < nv) or (u2, v2) not in sel_set:
                fixed.add((u, v))
                break
    return fixed


def _surface_hop_weights(sel, nu, nv):
    """sin(pi/2 * d/dmax) over grid-step hop distance; no boundary -> 1.0."""
    boundary = _surface_boundary(sel, nu, nv)
    if not boundary:
        return {uv: 1.0 for uv in sel}
    dist = {uv: 0 if uv in boundary else None for uv in sel}
    queue = deque(boundary)
    while queue:
        u, v = queue.popleft()
        for du, dv in NEIGH:
            nb = (u + du, v + dv)
            if nb in dist and dist[nb] is None:
                dist[nb] = dist[(u, v)] + 1
                queue.append(nb)
    dmax = max((d for d in dist.values() if d is not None), default=1) or 1
    return {uv: math.sin(math.pi / 2 * (dist[uv] or 0) / dmax) for uv in sel}


# ---------------------------------------------------------------- inflate

def inflate_mesh(obj, op):
    bm = bmesh.from_edit_mesh(obj.data)
    verts = [v for v in bm.verts if v.select]
    if len(verts) < 3:
        return False
    bm.normal_update()
    normals = {v: v.normal.copy() for v in verts}
    weights = _hop_weights(verts, _mesh_adj(verts), op.fix_boundary)
    moved = False
    for v in verts:
        w, nrm = weights[v], normals[v]
        if w < 1e-9 or nrm.length < 1e-9:
            continue
        v.co = v.co + nrm * (op.amount * w)
        moved = True
    if moved:
        bmesh.update_edit_mesh(obj.data)
    return moved


def _run_normal(positions):
    """Normal of the run's plane from the cross products of its segments;
    None for a straight (or degenerate) run."""
    normal = Vector((0.0, 0.0, 0.0))
    for i in range(1, len(positions) - 1):
        cross = (positions[i] - positions[i - 1]).cross(positions[i + 1] - positions[i])
        if cross.length > 1e-9:
            normal += cross.normalized()
    if normal.length < 1e-9:
        return None
    normal.normalize()
    return normal


def inflate_curve(obj, op):
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
        for run in _runs(flags, spline.use_cyclic_u):
            if len(run) < 3:
                continue
            positions = [Vector(pts[i].co[:3]) for i in run]
            normal = _run_normal(positions)
            if normal is None:
                continue  # straight run: no plane to inflate along
            n = len(run) - 1
            for k, i in enumerate(run):
                w = math.sin(math.pi * k / n) if op.fix_boundary else 1.0
                delta = normal * (op.amount * w)
                pt = pts[i]
                if spline.type == 'BEZIER':
                    pt.co = pt.co + delta
                    pt.handle_left = pt.handle_left + delta
                    pt.handle_right = pt.handle_right + delta
                else:
                    new = Vector(pt.co[:3]) + delta
                    pt.co = (new.x, new.y, new.z, pt.co[3])  # weight untouched
            processed = True
    return processed


def inflate_surface(obj, op):
    processed = False
    for spline in obj.data.splines:
        if spline.type != 'NURBS':
            continue
        nu, nv = spline.point_count_u, spline.point_count_v
        pts = spline.points
        sel = {(u, v) for v in range(nv) for u in range(nu) if pts[v * nu + u].select}
        if len(sel) < 3:
            continue
        snap = {(u, v): Vector(pts[v * nu + u].co[:3]) for v in range(nv) for u in range(nu)}

        def grid_normal(u, v):
            p = snap[(u, v)]
            du = (snap[(u + 1, v)] - snap[(u - 1, v)]) if 0 < u < nu - 1 else \
                 (snap[(u + 1, v)] - p if u == 0 else p - snap[(u - 1, v)])
            dv = (snap[(u, v + 1)] - snap[(u, v - 1)]) if 0 < v < nv - 1 else \
                 (snap[(u, v + 1)] - p if v == 0 else p - snap[(u, v - 1)])
            n = dv.cross(du)
            return n.normalized() if n.length > 1e-9 else Vector((0.0, 0.0, 1.0))

        weights = _surface_hop_weights(sel, nu, nv) if op.fix_boundary else {uv: 1.0 for uv in sel}
        for (u, v) in sel:
            w = weights[(u, v)]
            if w < 1e-9:
                continue
            new = snap[(u, v)] + grid_normal(u, v) * (op.amount * w)
            pt = pts[v * nu + u]
            pt.co = (new.x, new.y, new.z, pt.co[3])  # weight untouched
        processed = True
    return processed


# ---------------------------------------------------------------- wrap

def _wrap_matrices(context, target):
    """Evaluated target mesh plus the matrices to move between the edited
    object's local space and the target's (normals via inverse transpose)."""
    dg = context.evaluated_depsgraph_get()
    te = target.evaluated_get(dg)
    tmat = te.matrix_world
    return te, tmat, tmat.inverted(), tmat.inverted().transposed().to_3x3()


def wrap_mesh(obj, target, op, context):
    bm = bmesh.from_edit_mesh(obj.data)
    verts = [v for v in bm.verts if v.select]
    if not verts:
        return False
    adj = _mesh_adj(verts)
    fixed = {v for v in verts if adj[v][1] or v.is_boundary} if op.fix_boundary else set()

    te, tmat, tmat_inv, nmat = _wrap_matrices(context, target)
    emat, emat_inv = obj.matrix_world, obj.matrix_world.inverted()
    for _ in range(op.iterations):
        for v in verts:
            if v in fixed:
                continue
            result, loc, nor, _idx = te.closest_point_on_mesh(tmat_inv @ (emat @ v.co))
            if not result:
                continue
            goal_world = tmat @ loc + (nmat @ nor).normalized() * op.offset
            v.co = v.co.lerp(emat_inv @ goal_world, op.strength)
    bmesh.update_edit_mesh(obj.data)
    return True


def wrap_surface(obj, target, op, context):
    te, tmat, tmat_inv, nmat = _wrap_matrices(context, target)
    emat, emat_inv = obj.matrix_world, obj.matrix_world.inverted()
    processed = False
    for spline in obj.data.splines:
        if spline.type != 'NURBS':
            continue
        nu, nv = spline.point_count_u, spline.point_count_v
        pts = spline.points
        sel = {(u, v) for v in range(nv) for u in range(nu) if pts[v * nu + u].select}
        if not sel:
            continue
        fixed = _surface_boundary(sel, nu, nv) if op.fix_boundary else set()
        for _ in range(op.iterations):
            for (u, v) in sel:
                if (u, v) in fixed:
                    continue
                pt = pts[v * nu + u]
                co = Vector(pt.co[:3])
                result, loc, nor, _idx = te.closest_point_on_mesh(tmat_inv @ (emat @ co))
                if not result:
                    continue
                goal_world = tmat @ loc + (nmat @ nor).normalized() * op.offset
                new = co.lerp(emat_inv @ goal_world, op.strength)
                pt.co = (new.x, new.y, new.z, pt.co[3])  # weight untouched
        processed = True
    return processed
