"""2D tile patterns and convex clipping (no bpy).

Every pattern is anchored to the pattern origin, so the same lattice cell gets
the same id and the same shape no matter which part of the plane is asked for.
That is what lets separate faces and separate patches on one plane line up.

Tiles are convex CCW polygons keyed by a hashable id.
"""

import math
import random

SQRT3 = math.sqrt(3.0)


# ---------------------------------------------------------------- clipping

def _left(p, a, b):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _cross_point(p, q, a, b):
    """Point where segment p-q crosses the line a-b (p and q are on opposite sides)."""
    dp = _left(p, a, b)
    dq = _left(q, a, b)
    t = dp / (dp - dq)
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def clip_halfplane(poly, a, b, eps=1e-12):
    """Keep the part of `poly` on the left of the directed line a->b."""
    out = []
    n = len(poly)
    for i in range(n):
        cur = poly[i]
        prev = poly[i - 1]
        cin = _left(cur, a, b) >= -eps
        pin = _left(prev, a, b) >= -eps
        if cin:
            if not pin:
                out.append(_cross_point(prev, cur, a, b))
            out.append(cur)
        elif pin:
            out.append(_cross_point(prev, cur, a, b))
    return out


def clip_convex(poly, clip):
    """Sutherland-Hodgman: `poly` clipped by the convex CCW polygon `clip`."""
    out = list(poly)
    for i in range(len(clip)):
        if len(out) < 3:
            return []
        out = clip_halfplane(out, clip[i - 1], clip[i])
    return out if len(out) >= 3 else []


def area(poly):
    """Signed area (positive = CCW)."""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i - 1]
        x1, y1 = poly[i]
        s += x0 * y1 - x1 * y0
    return s * 0.5


def bounds(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def dedupe(poly, eps):
    """Drop consecutive points closer than eps (clipping leaves them on corners)."""
    out = []
    for p in poly:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) <= eps and abs(out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


# ---------------------------------------------------------------- patterns
#
# Each generator: (x0, y0, x1, y1, size, opts) -> iterable of (id, polygon).
# The window is in pattern space and only needs to be covered, not matched.

def _span(lo, hi, step, pad=1):
    return range(math.floor(lo / step) - pad, math.floor(hi / step) + pad + 1)


def squares(x0, y0, x1, y1, s, opts):
    for j in _span(y0, y1, s):
        for i in _span(x0, x1, s):
            x, y = i * s, j * s
            yield ('Q', i, j), [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]


def bricks(x0, y0, x1, y1, s, opts):
    """Running bond: s = brick length, height = s / ratio, rows shifted by offset * s."""
    h = s / max(opts.get("ratio", 2.0), 1e-6)
    shift = opts.get("offset", 0.5)
    for j in _span(y0, y1, h):
        dx = ((j * shift) % 1.0) * s
        for i in _span(x0 - dx, x1 - dx, s):
            x, y = i * s + dx, j * h
            yield ('B', i, j), [(x, y), (x + s, y), (x + s, y + h), (x, y + h)]


def triangles(x0, y0, x1, y1, s, opts):
    """Equilateral triangles with edge s."""
    h = s * SQRT3 / 2.0
    for j in _span(y0, y1, h):
        y = j * h
        dx = (j % 2) * s / 2.0
        for i in _span(x0 - dx, x1 - dx, s):
            x = i * s + dx
            yield ('TU', i, j), [(x, y), (x + s, y), (x + s / 2.0, y + h)]
            yield ('TD', i, j), [(x + s, y), (x + 1.5 * s, y + h), (x + s / 2.0, y + h)]


def hexagons(x0, y0, x1, y1, s, opts):
    """Flat-top regular hexagons with edge s."""
    cw = 1.5 * s
    rh = SQRT3 * s
    corners = [(s * math.cos(math.pi / 3.0 * k), s * math.sin(math.pi / 3.0 * k)) for k in range(6)]
    for i in _span(x0, x1, cw):
        oy = rh / 2.0 if i % 2 else 0.0
        for j in _span(y0 - oy, y1 - oy, rh):
            cx, cy = i * cw, j * rh + oy
            yield ('H', i, j), [(cx + a, cy + b) for a, b in corners]


def octagons(x0, y0, x1, y1, s, opts):
    """Octagons and squares (4.8.8). s = octagon width across flats."""
    a = s / (1.0 + math.sqrt(2.0))       # edge length
    hw = s / 2.0
    ha = a / 2.0
    r = a / math.sqrt(2.0)               # small square: centre to corner
    octo = [(ha, -hw), (hw, -ha), (hw, ha), (ha, hw), (-ha, hw), (-hw, ha), (-hw, -ha), (-ha, -hw)]
    sq = [(0.0, -r), (r, 0.0), (0.0, r), (-r, 0.0)]
    for j in _span(y0, y1, s):
        for i in _span(x0, x1, s):
            cx, cy = i * s, j * s
            yield ('O', i, j), [(cx + p, cy + q) for p, q in octo]
            yield ('S', i, j), [(cx + hw + p, cy + hw + q) for p, q in sq]


def _seed_point(i, j, s, randomness, seed):
    """Seed of lattice cell (i, j): a hexagonal lattice, jittered by a per-cell RNG."""
    h = s * SQRT3 / 2.0
    x = i * s + (j % 2) * s / 2.0
    y = j * h
    if randomness > 0.0:
        rng = random.Random(hash((seed, i, j)) & 0xFFFFFFFF)
        ang = rng.uniform(0.0, 2.0 * math.pi)
        rad = math.sqrt(rng.random()) * randomness * s * 0.5
        x += rad * math.cos(ang)
        y += rad * math.sin(ang)
    return x, y


def voronoi(x0, y0, x1, y1, s, opts):
    """Voronoi cells around a jittered hexagonal lattice of seeds (spacing s).

    Randomness 0 gives regular hexagons; 1 lets each seed wander half a spacing.
    Neighbours are looked up in a fixed lattice window, which is enough because
    no seed leaves its own half-spacing disc.
    """
    rnd = max(0.0, min(1.0, opts.get("randomness", 0.6)))
    seed = opts.get("seed", 0)
    h = s * SQRT3 / 2.0
    big = s * 4.0
    for j in _span(y0, y1, h, pad=2):
        for i in _span(x0, x1, s, pad=2):
            px, py = _seed_point(i, j, s, rnd, seed)
            cell = [(px - big, py - big), (px + big, py - big), (px + big, py + big), (px - big, py + big)]
            for dj in range(-3, 4):
                for di in range(-3, 4):
                    if di == 0 and dj == 0:
                        continue
                    qx, qy = _seed_point(i + di, j + dj, s, rnd, seed)
                    dx, dy = qx - px, qy - py
                    mx, my = (px + qx) / 2.0, (py + qy) / 2.0
                    # keep the side of the bisector that contains p
                    a = (mx + dy, my - dx)
                    b = (mx - dy, my + dx)
                    cell = clip_halfplane(cell, a, b)
                    if len(cell) < 3:
                        break
            if len(cell) >= 3:
                yield ('V', i, j), cell


PATTERNS = {
    'SQUARE': squares,
    'BRICK': bricks,
    'TRIANGLE': triangles,
    'HEXAGON': hexagons,
    'OCTAGON': octagons,
    'VORONOI': voronoi,
}


def tiles(pattern, window, size, opts=None):
    x0, y0, x1, y1 = window
    return PATTERNS[pattern](x0, y0, x1, y1, size, opts or {})
