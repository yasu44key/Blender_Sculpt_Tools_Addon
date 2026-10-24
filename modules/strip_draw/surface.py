"""Which mesh was a strip drawn on?

The band is laid flat using the Target's surface normals, so a Target other than the mesh under
the stroke (the panel remembers the last surface) stands the band on edge. The Draw tool puts the
stroke on whatever surface is under the pen, so the stroke itself tells which mesh it is.
"""

from mathutils import Vector

SAMPLES_PER_SPLINE = 6


def _samples(curve_obj):
    mw = curve_obj.matrix_world
    out = []
    for sp in curve_obj.data.splines:
        pts = sp.points
        n = len(pts)
        if n == 0:
            continue
        step = max(1, n // SAMPLES_PER_SPLINE)
        out.extend(mw @ Vector(pts[i].co[:3]) for i in range(0, n, step))
    return out


def _near_bbox(obj, p, margin):
    mw_inv = obj.matrix_world.inverted()
    q = mw_inv @ p
    lo = Vector(min(c[i] for c in obj.bound_box) for i in range(3))
    hi = Vector(max(c[i] for c in obj.bound_box) for i in range(3))
    return all(lo[i] - margin <= q[i] <= hi[i] + margin for i in range(3))


def mean_distance(mesh_obj, points):
    """Mean distance from world points to the mesh surface (inf if none can be measured)."""
    if not points:
        return float("inf")
    mw = mesh_obj.matrix_world
    mw_inv = mw.inverted()
    total = 0.0
    for p in points:
        ok, loc, _nor, _i = mesh_obj.closest_point_on_mesh(mw_inv @ p)
        if not ok:
            return float("inf")
        total += (mw @ loc - p).length
    return total / len(points)


def drawn_on(curve_obj, candidates, tolerance):
    """The candidate mesh the stroke lies on (mean distance <= tolerance), nearest first; or None."""
    pts = _samples(curve_obj)
    if not pts:
        return None
    best, best_d = None, tolerance
    for obj in candidates:
        if not all(_near_bbox(obj, p, tolerance) for p in pts[:3]):
            continue                                  # cheap reject before building a BVH
        d = mean_distance(obj, pts)
        if d <= best_d:
            best, best_d = obj, d
    return best


def fit_target(context, curve_obj, mod, strip):
    """Point the strip's Target at the mesh it was drawn on, if that is not the Target already.
    Returns the new target, or None when nothing changed."""
    current = strip.get_input(mod, "Target")
    pts = _samples(curve_obj)
    if not pts:
        return None
    width = strip.get_input(mod, "Width")
    tolerance = max(width * 0.5, 1e-4)
    if current is not None and mean_distance(current, pts) <= tolerance:
        return None
    candidates = [o for o in context.view_layer.objects
                  if o.type == 'MESH' and o is not current and o.visible_get() and strip.get(o) is None]
    found = drawn_on(curve_obj, candidates, tolerance)
    if found is not None:
        strip.set_input(mod, "Target", found)
        context.scene.sts_strip_draw.target = found
    return found
