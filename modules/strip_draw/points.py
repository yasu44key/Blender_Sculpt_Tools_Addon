"""Point density of drawn strips: resample to a spacing, decimate, subdivide.

A pen stroke records a point every few pixels, so a strip carries hundreds of jittery points;
the band follows every wobble (saw teeth along the edges). Fewer, evenly spaced points give a
calm band, more points follow a tight bend.

Only POLY splines are touched (drawn strokes are POLY); radius (pen pressure) and tilt are
interpolated along with the position. A spline is rebuilt (POLY points can be added but not
removed), so these work on curve data in Object Mode.
"""

from mathutils import Vector


def read(sp):
    return [(Vector(p.co[:3]), p.radius, p.tilt) for p in sp.points]


def _lerp(a, b, t):
    return (a[0].lerp(b[0], t), a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def resample(pts, spacing, cyclic=False):
    """Evenly spaced points about `spacing` apart (the ends kept; a closed loop keeps its start)."""
    if spacing <= 0.0 or len(pts) < 2:
        return pts
    loop = pts + [pts[0]] if cyclic else pts
    seg = [(loop[i + 1][0] - loop[i][0]).length for i in range(len(loop) - 1)]
    total = sum(seg)
    if total <= 0.0:
        return pts[:1]
    n = max(1, round(total / spacing))            # segments
    step = total / n
    out = [loop[0]]
    i, walked = 0, 0.0                             # walked = length up to the start of seg[i]
    for k in range(1, n):
        d = k * step
        while i < len(seg) - 1 and walked + seg[i] < d:
            walked += seg[i]
            i += 1
        t = (d - walked) / seg[i] if seg[i] > 0.0 else 0.0
        out.append(_lerp(loop[i], loop[i + 1], min(max(t, 0.0), 1.0)))
    if not cyclic:
        out.append(loop[-1])
    return out


def decimate(pts, keep_every=2, cyclic=False):
    """Keep every Nth point (and the last one of an open stroke)."""
    if keep_every < 2 or len(pts) < 3:
        return pts
    out = pts[::keep_every]
    if not cyclic and out[-1] is not pts[-1]:
        out.append(pts[-1])
    return out


def subdivide(pts, cuts=1, cyclic=False):
    """Put `cuts` evenly spaced points into every segment."""
    if cuts < 1 or len(pts) < 2:
        return pts
    loop = pts + [pts[0]] if cyclic else pts
    out = []
    for a, b in zip(loop, loop[1:]):
        out.append(a)
        out.extend(_lerp(a, b, j / (cuts + 1)) for j in range(1, cuts + 1))
    if not cyclic:
        out.append(pts[-1])
    return out


def write(curve, old, pts):
    sp = curve.splines.new('POLY')
    sp.use_cyclic_u = old.use_cyclic_u
    sp.use_smooth = old.use_smooth
    sp.material_index = old.material_index
    sp.points.add(len(pts) - 1)
    for p, (co, radius, tilt) in zip(sp.points, pts):
        p.co = (*co, 1.0)
        p.radius = radius
        p.tilt = tilt
    curve.splines.remove(old)


def apply(curve, fn, only_selected=False):
    """Rebuild the POLY splines of `curve` with fn(points, cyclic) -> points.

    only_selected: just the splines with a selected point (when any point is selected).
    Splines left with fewer than 2 points are dropped. Returns (points before, after).
    """
    splines = [sp for sp in curve.splines if sp.type == 'POLY']
    if only_selected:
        chosen = [sp for sp in splines if any(p.select for p in sp.points)]
        splines = chosen or splines
    before = after = 0
    for sp in splines:
        pts = read(sp)
        new = fn(pts, sp.use_cyclic_u)
        before += len(pts)
        if len(new) < 2:
            curve.splines.remove(sp)
            continue
        after += len(new)
        if new is not pts:
            write(curve, sp, new)
    return before, after


def drop_stray(curve):
    """Remove splines of a single point (a tap of the pen)."""
    for sp in [sp for sp in curve.splines if len(sp.points) < 2 and sp.type == 'POLY']:
        curve.splines.remove(sp)
