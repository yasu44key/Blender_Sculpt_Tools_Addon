"""Add generated meshes at the 3D cursor: lattice, hex grid, random grid, leaf venation.

Replaces: CrystalStructureMesh.py, TetrahedralSpace-Filling.py, HexagonalMeshGenerator.py,
gridmesh3.py, LeafVenationMeshGenerator4.py

No mouse interaction. Everything is an operator parameter (F9-adjustable); random
things are driven by a `seed` so the same seed gives the same mesh.
"""

import math
import random

import bpy
import bmesh
from mathutils import Vector, kdtree


# ---------------------------------------------------------------------------
# Common helpers

def _to_object_mode(context):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def _finish(context, bm, name):
    """Write the bmesh into a new mesh object at the 3D cursor; select only it."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = context.scene.cursor.location
    context.collection.objects.link(obj)
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj


# ---------------------------------------------------------------------------
# Lattice: cube grid / tetrahedral-octahedral (octet) honeycomb

_OCTET_DIRS = ((1, 1, 0), (1, -1, 0), (1, 0, 1), (1, 0, -1), (0, 1, 1), (0, 1, -1))


class MESH_OT_sts_add_lattice(bpy.types.Operator):
    """Add a lattice at the 3D cursor: cube grid or the tetrahedral-octahedral (octet) honeycomb"""
    bl_idname = "mesh.sts_add_lattice"
    bl_label = "Lattice Grid"
    bl_options = {'REGISTER', 'UNDO'}

    cell: bpy.props.EnumProperty(
        name="Cell Type",
        items=[('CUBE', "Cube", "Simple cube grid"),
               ('OCTET', "Octet", "Tetrahedral-octahedral honeycomb: cube corners and face centres, joined to their nearest neighbours")],
        default='CUBE')
    size: bpy.props.FloatProperty(name="Size", description="Cell edge", default=1.0,
                                  min=0.01, max=100.0, unit='LENGTH')
    count_x: bpy.props.IntProperty(name="Count X", description="Cells along X", default=3, min=1, max=16)
    count_y: bpy.props.IntProperty(name="Count Y", description="Cells along Y", default=3, min=1, max=16)
    count_z: bpy.props.IntProperty(name="Count Z", description="Cells along Z", default=3, min=1, max=16)
    style: bpy.props.EnumProperty(
        name="Build Style",
        items=[('WIRE', "Wire", "Lattice edges only; every vertex and edge once"),
               ('CELLS', "Cells", "Closed solids, one per cell")],
        default='WIRE')
    gap: bpy.props.FloatProperty(name="Cell Gap", default=0.1, min=0.0, max=0.9,
                                 description="Cells style: shrink each cell toward its own centre")

    def execute(self, context):
        _to_object_mode(context)
        bm = bmesh.new()
        if self.style == 'WIRE':
            self._wire(bm)
        else:
            self._cells(bm)
        _finish(context, bm, "Lattice")
        return {'FINISHED'}

    def _wire(self, bm):
        half = self.size / 2.0
        if self.cell == 'CUBE':
            pts = {}
            for i in range(self.count_x + 1):
                for j in range(self.count_y + 1):
                    for k in range(self.count_z + 1):
                        pts[(i, j, k)] = bm.verts.new(
                            ((i - self.count_x / 2.0) * self.size,
                             (j - self.count_y / 2.0) * self.size,
                             (k - self.count_z / 2.0) * self.size))
            for key, v in pts.items():
                for d in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                    n = pts.get((key[0] + d[0], key[1] + d[1], key[2] + d[2]))
                    if n is not None:
                        bm.edges.new((v, n))
        else:
            # FCC points: integer coordinates in half-cell units, even coordinate sum
            pts = {}
            for a in range(2 * self.count_x + 1):
                for b in range(2 * self.count_y + 1):
                    for c in range(2 * self.count_z + 1):
                        if (a + b + c) % 2 == 0:
                            pts[(a, b, c)] = bm.verts.new(
                                ((a - self.count_x) * half,
                                 (b - self.count_y) * half,
                                 (c - self.count_z) * half))
            for key, v in pts.items():
                for d in _OCTET_DIRS:  # 6 of the 12 nearest-neighbour directions: each pair once
                    n = pts.get((key[0] + d[0], key[1] + d[1], key[2] + d[2]))
                    if n is not None:
                        bm.edges.new((v, n))

    def _cells(self, bm):
        f = 1.0 - self.gap
        half = self.size / 2.0
        if self.cell == 'CUBE':
            for i in range(self.count_x):
                for j in range(self.count_y):
                    for k in range(self.count_z):
                        cx = (i + 0.5 - self.count_x / 2.0) * self.size
                        cy = (j + 0.5 - self.count_y / 2.0) * self.size
                        cz = (k + 0.5 - self.count_z / 2.0) * self.size
                        vs = [bm.verts.new((cx + sx * half * f, cy + sy * half * f, cz + sz * half * f))
                              for sx in (1, -1) for sy in (1, -1) for sz in (1, -1)]
                        bm.faces.new((vs[0], vs[2], vs[6], vs[4]))  # +z
                        bm.faces.new((vs[1], vs[5], vs[7], vs[3]))  # -z
                        bm.faces.new((vs[0], vs[4], vs[5], vs[1]))  # +y
                        bm.faces.new((vs[2], vs[3], vs[7], vs[6]))  # -y
                        bm.faces.new((vs[0], vs[1], vs[3], vs[2]))  # +x
                        bm.faces.new((vs[4], vs[6], vs[7], vs[5]))  # -x
            return
        nx, ny, nz = self.count_x, self.count_y, self.count_z

        def W(a, b, c):  # half-cell integer coords -> world, whole lattice centred on the origin
            return Vector(((a - nx) * half, (b - ny) * half, (c - nz) * half))

        def solid(coords):
            cen = sum(coords, Vector()) / len(coords)
            vs = [bm.verts.new(cen + (c - cen) * f) for c in coords]
            if len(vs) == 4:  # tetrahedron
                for tri in ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)):
                    bm.faces.new((vs[tri[0]], vs[tri[1]], vs[tri[2]]))
            else:  # octahedron: coords are the three opposite pairs (0,1) (2,3) (4,5)
                for sx in (1, -1):
                    for sy in (1, -1):
                        for sz in (1, -1):
                            bm.faces.new((vs[0 if sx > 0 else 1], vs[2 if sy > 0 else 3], vs[4 if sz > 0 else 5]))

        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    o = (2 * i, 2 * j, 2 * k)
                    # the centre octahedron: the 6 face centres of the cube cell
                    solid([W(o[0] + 1, o[1] + 1, o[2]), W(o[0] + 1, o[1] + 1, o[2] + 2),
                           W(o[0] + 1, o[1], o[2] + 1), W(o[0] + 1, o[1] + 2, o[2] + 1),
                           W(o[0], o[1] + 1, o[2] + 1), W(o[0] + 2, o[1] + 1, o[2] + 1)])
                    # 8 corner tetrahedra: corner + the 3 face centres touching it
                    for dx in (0, 2):
                        for dy in (0, 2):
                            for dz in (0, 2):
                                p = (o[0] + dx, o[1] + dy, o[2] + dz)
                                sx = 1 if dx == 0 else -1
                                sy = 1 if dy == 0 else -1
                                sz = 1 if dz == 0 else -1
                                solid([W(*p), W(p[0] + sx, p[1] + sy, p[2]),
                                       W(p[0] + sx, p[1], p[2] + sz), W(p[0], p[1] + sy, p[2] + sz)])
        # one octahedron on every INTERIOR cube edge (all 4 cells around it exist)
        for i in range(nx):
            for j in range(1, ny):
                for k in range(1, nz):
                    m = (2 * i + 1, 2 * j, 2 * k)  # edge along x
                    solid([W(m[0] - 1, m[1], m[2]), W(m[0] + 1, m[1], m[2]),
                           W(m[0], m[1] - 1, m[2]), W(m[0], m[1] + 1, m[2]),
                           W(m[0], m[1], m[2] - 1), W(m[0], m[1], m[2] + 1)])
        for j in range(ny):
            for i in range(1, nx):
                for k in range(1, nz):
                    m = (2 * i, 2 * j + 1, 2 * k)  # edge along y
                    solid([W(m[0] - 1, m[1], m[2]), W(m[0] + 1, m[1], m[2]),
                           W(m[0], m[1] - 1, m[2]), W(m[0], m[1] + 1, m[2]),
                           W(m[0], m[1], m[2] - 1), W(m[0], m[1], m[2] + 1)])
        for k in range(nz):
            for i in range(1, nx):
                for j in range(1, ny):
                    m = (2 * i, 2 * j, 2 * k + 1)  # edge along z
                    solid([W(m[0] - 1, m[1], m[2]), W(m[0] + 1, m[1], m[2]),
                           W(m[0], m[1] - 1, m[2]), W(m[0], m[1] + 1, m[2]),
                           W(m[0], m[1], m[2] - 1), W(m[0], m[1], m[2] + 1)])


# ---------------------------------------------------------------------------
# Hexagonal grid (flat-top hexagons, odd columns shifted half a row)

class MESH_OT_sts_add_hex_grid(bpy.types.Operator):
    """Add a grid of hexagons at the 3D cursor; gap 0 = one connected sheet, gap > 0 = separate tiles"""
    bl_idname = "mesh.sts_add_hex_grid"
    bl_label = "Hexagonal Grid"
    bl_options = {'REGISTER', 'UNDO'}

    rows: bpy.props.IntProperty(name="Rows", default=5, min=1, max=64)
    cols: bpy.props.IntProperty(name="Cols", default=5, min=1, max=64)
    size: bpy.props.FloatProperty(name="Size", description="Hexagon edge", default=0.5,
                                  min=0.01, max=10.0, unit='LENGTH')
    gap: bpy.props.FloatProperty(name="Tile Gap", default=0.0, min=0.0, max=0.9,
                                 description="Shrink each hexagon toward its centre (0 = shared vertices)")

    def execute(self, context):
        _to_object_mode(context)
        bm = bmesh.new()
        s = self.size
        f = 1.0 - self.gap
        # corner offsets as exact integers: x in half-edge units, y in half-row (sqrt3*size/2) units
        CX = (2, 1, -1, -2, -1, 1)
        CY = (0, 1, 1, 0, -1, -1)
        pts = {}
        for col in range(self.cols):
            for row in range(self.rows):
                cx2 = 3 * col                    # centre x, half-edge units
                cy2 = 2 * row + (col & 1)        # centre y, half-row units (odd columns shifted)
                vs = []
                for i in range(6):
                    if self.gap > 0.0:
                        cen = (cx2 * s / 2.0, cy2 * math.sqrt(3.0) * s / 2.0)
                        vx = (cx2 + CX[i]) * s / 2.0
                        vy = (cy2 + CY[i]) * math.sqrt(3.0) * s / 2.0
                        vs.append(bm.verts.new((cen[0] + (vx - cen[0]) * f, cen[1] + (vy - cen[1]) * f, 0.0)))
                    else:
                        key = (cx2 + CX[i], cy2 + CY[i])
                        v = pts.get(key)
                        if v is None:
                            v = bm.verts.new((key[0] * s / 2.0, key[1] * math.sqrt(3.0) * s / 2.0, 0.0))
                            pts[key] = v
                        vs.append(v)
                bm.faces.new(vs)
        _finish(context, bm, "Hex Grid")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Random (jittered) quad grid

class MESH_OT_sts_add_random_grid(bpy.types.Operator):
    """Add a quad grid at the 3D cursor with every vertex jittered by a seeded random offset"""
    bl_idname = "mesh.sts_add_random_grid"
    bl_label = "Random Grid"
    bl_options = {'REGISTER', 'UNDO'}

    rows: bpy.props.IntProperty(name="Rows", default=5, min=1, max=64)
    cols: bpy.props.IntProperty(name="Cols", default=5, min=1, max=64)
    size: bpy.props.FloatProperty(name="Size", description="Quad edge", default=1.0,
                                  min=0.01, max=100.0, unit='LENGTH')
    jitter_x: bpy.props.FloatProperty(name="Jitter X", default=0.1, min=0.0, max=0.5,
                                      description="Random offset as a fraction of Size")
    jitter_y: bpy.props.FloatProperty(name="Jitter Y", default=0.1, min=0.0, max=0.5,
                                      description="Random offset as a fraction of Size")
    jitter_z: bpy.props.FloatProperty(name="Jitter Z", default=0.0, min=0.0, max=0.5,
                                      description="Random offset as a fraction of Size")
    midpoints: bpy.props.BoolProperty(name="Add Midpoints", default=False,
                                      description="Split every quad into four; the midpoints are jittered too")
    seed: bpy.props.IntProperty(name="Seed", default=0, min=0, max=1000000,
                                description="Same seed, same mesh")

    def execute(self, context):
        _to_object_mode(context)
        bm = bmesh.new()
        rng = random.Random(self.seed)
        nr = 2 * self.rows + 1 if self.midpoints else self.rows + 1
        nc = 2 * self.cols + 1 if self.midpoints else self.cols + 1
        step = self.size / 2.0 if self.midpoints else self.size
        grid = []
        for i in range(nr):
            row = []
            for j in range(nc):
                x = (i - (nr - 1) / 2.0) * step + rng.uniform(-1.0, 1.0) * self.jitter_x * self.size
                y = (j - (nc - 1) / 2.0) * step + rng.uniform(-1.0, 1.0) * self.jitter_y * self.size
                z = rng.uniform(-1.0, 1.0) * self.jitter_z * self.size
                row.append(bm.verts.new((x, y, z)))
            grid.append(row)
        for i in range(nr - 1):
            for j in range(nc - 1):
                bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
        _finish(context, bm, "Random Grid")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Leaf venation by space colonization

def _inside(poly, x, y):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _ellipse_poly(length, n=48):
    a, b = length / 4.0, length / 2.0  # width = length / 2
    return [(a * math.cos(-math.pi / 2.0 + math.tau * i / n),
             b * math.sin(-math.pi / 2.0 + math.tau * i / n)) for i in range(n)]


def _oval_poly(length, n=48):
    # egg: narrower at the top, rounded at the bottom; starts at the lowest point
    a, b, e = length / 4.0, length / 2.0, 0.25
    pts = []
    for i in range(n):
        t = -math.pi / 2.0 + math.tau * i / n
        pts.append((a * math.cos(t) * (1.0 - e * math.sin(t)), b * math.sin(t)))
    return pts


def _lance_poly(length, n=24):
    # lanceolate: pointed at both ends, widest in the middle
    a, b = length / 8.0, length / 2.0
    poly = []
    for i in range(n + 1):
        y = -b + 2.0 * b * i / n
        poly.append((a * (1.0 - (y / b) ** 2), y))
    for i in range(1, n):
        y = b - 2.0 * b * i / n
        poly.append((-a * (1.0 - (y / b) ** 2), y))
    return poly


def _curve_polygon(obj):
    """The curve's first closed spline (else its first spline, closed), sampled in the curve's local XY."""
    splines = list(obj.data.splines)
    spline = next((sp for sp in splines if sp.use_cyclic_u), splines[0] if splines else None)
    if spline is None:
        return None
    pts = list(spline.bezier_points if spline.type == 'BEZIER' else spline.points)
    if len(pts) < 2:
        return None
    n = len(pts)
    poly = []
    if spline.type == 'BEZIER':
        m = 12  # samples per segment
        for i in range(n):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]
            ax, ay = p0.co.x, p0.co.y
            bx, by = p0.handle_right.x, p0.handle_right.y
            cx, cy = p1.handle_left.x, p1.handle_left.y
            dx, dy = p1.co.x, p1.co.y
            for t in range(m):
                u = t / m
                iu = 1.0 - u
                poly.append((iu ** 3 * ax + 3 * iu * iu * u * bx + 3 * iu * u * u * cx + u ** 3 * dx,
                             iu ** 3 * ay + 3 * iu * iu * u * by + 3 * iu * u * u * cy + u ** 3 * dy))
    else:  # POLY / NURBS / handle-less points: knot points as a closed polygon
        for p in pts:
            poly.append((p.co.x, p.co.y))
    return poly if len(poly) >= 3 else None


def _colonize(poly, attractors_n, step, kill_distance, influence, seed):
    """Space colonization (Runions et al. 2005): every attractor pulls only its nearest vein
    point within `influence`; each pulled vein point grows ONE new point, `step` along the
    average of its pulling directions; attractors within `kill_distance` of a vein die.
    Veins start at the base (lowest outline point). Returns (points, parent index)."""
    rng = random.Random(seed)
    minx = min(p[0] for p in poly)
    maxx = max(p[0] for p in poly)
    miny = min(p[1] for p in poly)
    maxy = max(p[1] for p in poly)
    attractors = []
    tries = 0
    limit = attractors_n * 60 + 1000
    while len(attractors) < attractors_n and tries < limit:
        tries += 1
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        if _inside(poly, x, y):
            attractors.append(Vector((x, y, 0.0)))

    root = min(poly, key=lambda p: p[1])
    veins = [Vector((root[0], root[1], 0.0))]
    parents = [-1]
    active = list(range(len(attractors)))

    def tree():
        kd = kdtree.KDTree(len(veins))
        for i, v in enumerate(veins):
            kd.insert(v, i)
        kd.balance()
        return kd

    kd = tree()
    for _it in range(20000):
        if not active or len(veins) >= 20000:
            break
        pull = {}
        for ai in active:
            _co, idx, dist = kd.find(attractors[ai])
            if dist <= influence:
                d = attractors[ai] - veins[idx]
                if d.length > 1e-12:
                    pull.setdefault(idx, Vector()).__iadd__(d.normalized())
        if not pull:
            # nothing in reach yet (the stalk): grow the newest point toward the nearest attractor
            last = len(veins) - 1
            best = min(active, key=lambda ai: (attractors[ai] - veins[last]).length)
            pull = {last: attractors[best] - veins[last]}
        grown = 0
        for idx in sorted(pull):
            d = pull[idx]
            if d.length < 1e-9:
                continue
            p = veins[idx] + d.normalized() * step
            if not _inside(poly, p.x, p.y) or kd.find(p)[2] < step * 0.5:
                continue
            veins.append(p)
            parents.append(idx)
            grown += 1
        if not grown:
            break
        kd = tree()
        if kill_distance > 0.0:
            active = [ai for ai in active if kd.find(attractors[ai])[2] > kill_distance]
    return veins, parents


def _skin_radii(obj, veins, parents, length):
    """Skin thickness: pipe model, sqrt of the share of tips beyond the point (base = thickest)."""
    me = obj.data
    children = [[] for _ in veins]
    for i, p in enumerate(parents):
        if p >= 0:
            children[p].append(i)
    tips = [0] * len(veins)
    for i in range(len(veins) - 1, -1, -1):  # parents always have a lower index than children
        tips[i] = 1 if not children[i] else sum(tips[c] for c in children[i])
    scale = 0.015 * length                      # radius at the base
    data = me.skin_vertices[0].data
    for i in range(len(veins)):
        r = scale * max(0.15, (tips[i] / tips[0]) ** 0.5)
        data[i].radius = (r, r)
    for i in range(len(veins), len(me.vertices)):  # outline ring vertices
        data[i].radius = (scale * 0.15, scale * 0.15)
    data[0].use_root = True  # the base (lowest point) is the Skin root


class MESH_OT_sts_add_leaf_venation(bpy.types.Operator):
    """Add leaf venation at the 3D cursor: veins grown by space colonization inside an outline"""
    bl_idname = "mesh.sts_add_leaf_venation"
    bl_label = "Leaf Venation"
    bl_options = {'REGISTER', 'UNDO'}

    outline: bpy.props.EnumProperty(
        name="Leaf Outline",
        items=[('ELLIPSE', "Ellipse", ""), ('OVAL', "Oval", ""), ('LANCE', "Lance", ""),
               ('CURVE', "Curve", "The active curve's first closed spline")],
        default='ELLIPSE')
    length: bpy.props.FloatProperty(name="Length", description="Outline length", default=2.0,
                                    min=0.1, max=100.0, unit='LENGTH')
    attractors: bpy.props.IntProperty(name="Attractors", description="Points scattered inside the outline",
                                      default=200, min=1, max=5000)
    step: bpy.props.FloatProperty(name="Growth Step", default=0.05, min=0.001, max=1.0, unit='LENGTH')
    kill_distance: bpy.props.FloatProperty(name="Kill Distance", default=0.05, min=0.0, max=1.0,
                                           unit='LENGTH', description="Attractors this close to a new vein point are removed")
    influence: bpy.props.FloatProperty(name="Pull Radius", default=0.5, min=0.01, max=10.0,
                                       unit='LENGTH', description="An attractor pulls its nearest vein point within this radius")
    seed: bpy.props.IntProperty(name="Seed", default=0, min=0, max=1000000,
                                description="Same seed, same veins")
    include_outline: bpy.props.BoolProperty(name="Include Outline", default=False,
                                            description="Add the outline as a closed ring")
    use_skin: bpy.props.BoolProperty(name="Use Skin", default=False,
                                     description="Skin modifier; thickness tapers from the base to the tips")

    def execute(self, context):
        if self.outline == 'CURVE':
            obj = context.active_object or context.view_layer.objects.active
            if obj is None or obj.type != 'CURVE':
                self.report({'WARNING'}, "A curve must be active for the CURVE outline")
                return {'CANCELLED'}
            poly = _curve_polygon(obj)
            if poly is None:
                self.report({'WARNING'}, "The active curve has no closed spline")
                return {'CANCELLED'}
        else:
            poly = {'ELLIPSE': _ellipse_poly, 'OVAL': _oval_poly, 'LANCE': _lance_poly}[self.outline](self.length)
        _to_object_mode(context)
        veins, parents = _colonize(poly, self.attractors, self.step, self.kill_distance,
                                   self.influence, self.seed)
        bm = bmesh.new()
        if self.use_skin:
            bm.verts.layers.skin.new()  # create the layer before taking vertex references
        vmap = {}
        vverts = []
        for v in veins:
            vert = bm.verts.new(v)
            vverts.append(vert)
            vmap[(round(v.x, 6), round(v.y, 6))] = vert
        for i, p in enumerate(parents):
            if p >= 0:
                bm.edges.new((vverts[i], vverts[p]))
        if self.include_outline:
            ring = []
            for (x, y) in poly:
                key = (round(x, 6), round(y, 6))
                vert = vmap.get(key)
                if vert is None:
                    vert = bm.verts.new((x, y, 0.0))
                    vmap[key] = vert
                ring.append(vert)
            n = len(ring)
            for i in range(n):
                a, b = ring[i], ring[(i + 1) % n]
                if a != b:
                    bm.edges.new((a, b))
        obj = _finish(context, bm, "Leaf Venation")
        if self.use_skin:
            obj.modifiers.new("STS Skin", 'SKIN')
            _skin_radii(obj, veins, parents, self.length)
        return {'FINISHED'}


# ---------------------------------------------------------------------------

GENERATORS = (
    (MESH_OT_sts_add_lattice, 'MESH_ICOSPHERE'),
    (MESH_OT_sts_add_hex_grid, 'MESH_GRID'),
    (MESH_OT_sts_add_random_grid, 'MESH_PLANE'),
    (MESH_OT_sts_add_leaf_venation, 'MESH_MONKEY'),
)


def add_menu(self, _context):
    layout = self.layout
    layout.separator()
    for op, icon in GENERATORS:
        layout.operator(op.bl_idname, icon=icon)


classes = tuple(op for op, _icon in GENERATORS)
