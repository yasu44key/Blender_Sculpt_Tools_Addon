"""GUI-free logic for the Object Brush module.

Replaces: Object_Brush_Pro_Collection1_15.py

The grid snapping (X / Y only, the height stays), the rotation spun around
the face normal, the depth kept when the ray misses, the parent-free
instance copy, the curve through the copies' centers and the stroke-level
undo / redo live here so they can be
tested without a 3D view (tests/test_object_brush.py).
"""

import bpy
from mathutils import Matrix, Quaternion, Vector


def grid_snap_xy(co, size):
    """X and Y rounded to the `size` grid; the height (Z) stays as it is.

    The old version rounded Z too and lifted copies off the surface.
    """
    co = Vector(co)
    return Vector((round(co.x / size) * size, round(co.y / size) * size, co.z))


def instance_rotation(normal, stroke_dir, align_to_normal, align_to_stroke, spin):
    """Orientation of a placed copy as a Quaternion.

    The local Z axis points along the face normal (world up when
    align_to_normal is off), the local Y axis along the stroke direction
    when align_to_stroke is on, and the result is finally spun `spin`
    radians around that Z axis. The old version added the random angle to
    an Euler Z after the alignment, which did not turn the object around
    the normal.
    """
    z = Vector(normal).normalized() if align_to_normal else Vector((0.0, 0.0, 1.0))
    if align_to_stroke and stroke_dir is not None:
        y = Vector(stroke_dir)
        y = y - y.dot(z) * z
        if y.length < 1e-6:
            y = z.orthogonal()
        y.normalize()
    else:
        y = z.orthogonal()
    x = y.cross(z).normalized()
    y = z.cross(x)
    q = Matrix((x, y, z)).transposed().to_quaternion()
    if spin:
        q = Quaternion(z, spin) @ q  # turn around the normal; the normal stays put
    return q


def depth_fallback(origin, direction, last_depth, cursor):
    """Point on the ray when the surface was missed: keep the depth of the
    last hit, or (nothing hit yet) the distance to the 3D cursor."""
    origin = Vector(origin)
    direction = Vector(direction).normalized()
    depth = last_depth if last_depth is not None else (Vector(cursor) - origin).length
    return origin + direction * depth


def place_instance(context, source, location, rotation, scale, collection):
    """A copy of `source` at the given world transform, linked to `collection`.

    source.copy() carries the parent chain and the constraints over; a
    brush copy is a plain instance: no parent, no constraints, the mesh
    data shared.
    """
    obj = source.copy()
    obj.parent = None
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.constraints.clear()
    collection.objects.link(obj)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rotation
    obj.location = Vector(location)
    obj.scale = source.scale * scale
    return obj


def nearest_chain(points, start=0):
    """Indices of `points` in the order of a nearest-neighbour walk from `start`
    (each step goes to the closest point not visited yet)."""
    points = [Vector(p) for p in points]
    if not points:
        return []
    order = [start]
    left = set(range(len(points))) - {start}
    while left:
        last = points[order[-1]]
        nxt = min(left, key=lambda i: ((points[i] - last).length, i))
        order.append(nxt)
        left.remove(nxt)
    return order


def centers_curve(points, collection, smooth=True, bevel_depth=0.0, cyclic=False, name="Brush_Line"):
    """A curve object through `points` (the copies' centers, in placing order).

    smooth: a Bezier spline with AUTO handles - it passes exactly through
    every center and bends softly between them (a string of beads);
    otherwise a POLY spline (straight segments). bevel_depth gives the
    curve a round thickness (0 = a plain line). Returns None for fewer
    than two points.
    """
    points = [Vector(p) for p in points]
    if len(points) < 2:
        return None
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = bevel_depth
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    if smooth:
        sp = cu.splines.new('BEZIER')
        sp.bezier_points.add(len(points) - 1)
        for bp, co in zip(sp.bezier_points, points):
            bp.co = co
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        sp.resolution_u = 12
    else:
        sp = cu.splines.new('POLY')
        sp.points.add(len(points) - 1)
        for p, co in zip(sp.points, points):
            p.co = (co.x, co.y, co.z, 1.0)
    sp.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, cu)
    collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------- follow modes
#
# A line made by centers_curve keeps which object sits on which control point
# (line["sts_beads"] = {"<point index>": object}). Only one side can lead -
# both at once would be a dependency cycle - so the line is in one mode:
#   'NONE'    nothing follows
#   'OBJECTS' the curve follows the objects (one Hook modifier per point)
#   'CURVE'   the objects follow the curve (each object vertex-parented to its
#             point; it moves with the point, its own rotation stays)
# Every switch first writes where everything is now into the curve points, so
# nothing jumps.

FOLLOW_MODES = ('NONE', 'OBJECTS', 'CURVE')
HOOK_PREFIX = "STS Bead"


def link_beads(line, objects):
    """Remember objects[i] as the object on control point i of `line`."""
    line["sts_beads"] = {str(i): o for i, o in enumerate(objects)}
    line["sts_follow"] = 'NONE'


def line_beads(line):
    """[(point index, object)] of a line (objects deleted since are skipped)."""
    group = line.get("sts_beads")
    if not group:
        return []
    pairs = [(int(k), o) for k, o in group.items() if isinstance(o, bpy.types.Object)]
    return sorted(pairs, key=lambda p: p[0])


def find_line(obj):
    """The line `obj` belongs to: itself when it is one, else the line it is a bead of."""
    if obj is None:
        return None
    if obj.get("sts_beads"):
        return obj
    for line in bpy.data.objects:
        if line.get("sts_beads") and any(o == obj for _i, o in line_beads(line)):
            return line
    return None


def _set_point(spline, i, co):
    if spline.type == 'BEZIER':
        bp = spline.bezier_points[i]
        d = co - bp.co
        bp.co = co
        bp.handle_left = bp.handle_left + d
        bp.handle_right = bp.handle_right + d
    else:
        spline.points[i].co = (co.x, co.y, co.z, 1.0)


def _unparent_keep(obj):
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_world = mw


def set_follow(context, line, mode):
    """Switch `line` to follow mode `mode` (one of FOLLOW_MODES)."""
    context.view_layer.update()
    beads = line_beads(line)
    spline = line.data.splines[0]
    count = len(spline.bezier_points) if spline.type == 'BEZIER' else len(spline.points)
    beads = [(i, o) for i, o in beads if i < count]
    to_local = line.matrix_world.inverted()

    # 1) bake: the points go to where the objects are now (hooks / parents undone)
    for m in [m for m in line.modifiers if m.type == 'HOOK' and m.name.startswith(HOOK_PREFIX)]:
        line.modifiers.remove(m)
    for _i, o in beads:
        if o.parent == line:
            _unparent_keep(o)
    for i, o in beads:
        _set_point(spline, i, to_local @ o.matrix_world.translation)
    line.data.update_tag()
    context.view_layer.update()

    # 2) link the chosen side
    if mode == 'OBJECTS':
        for i, o in beads:
            m = line.modifiers.new(f"{HOOK_PREFIX} {i}", 'HOOK')
            m.object = o
            m.vertex_indices_set([3 * i, 3 * i + 1, 3 * i + 2] if spline.type == 'BEZIER' else [i])
            m.center = to_local @ o.matrix_world.translation
            m.matrix_inverse = o.matrix_world.inverted() @ line.matrix_world  # no jump now
    elif mode == 'CURVE':
        for i, o in beads:
            mw = o.matrix_world.copy()
            co = spline.bezier_points[i].co if spline.type == 'BEZIER' else spline.points[i].co.xyz
            o.parent = line
            o.parent_type = 'VERTEX'
            o.parent_vertices = (i, 0, 0)  # a Bezier point counts once here
            o.matrix_parent_inverse = (line.matrix_world @ Matrix.Translation(co)).inverted()
            o.matrix_basis = mw
    line["sts_follow"] = mode
    context.view_layer.update()


class StrokeHistory:
    """Stroke-level undo / redo (Ctrl+Z / Ctrl+Shift+Z inside the brush).

    begin() ... add(obj) ... end() is one stroke; an empty stroke is not
    recorded. undo() unlinks the last stroke and moves it to the redo
    side, redo() links it back. Copies waiting on the redo side can never
    come back once a new stroke ends (or the brush exits), so they are
    deleted there - the old version only unlinked them and left the
    objects behind as orphans.
    """

    def __init__(self):
        self._undo = []    # strokes still in the collection
        self._redo = []    # strokes unlinked, waiting to be re-linked or deleted
        self._current = None

    def begin(self):
        self._current = []

    def add(self, obj):
        if self._current is not None:
            self._current.append(obj)

    def current(self):
        """The copies placed so far in the stroke being drawn (a new list)."""
        return list(self._current or ())

    def end(self):
        stroke = self._current
        self._current = None
        if not stroke:
            return
        self._delete_redo()  # a new stroke was drawn: those can no longer be redone
        self._undo.append(stroke)

    def undo(self, collection):
        if not self._undo:
            return False
        stroke = self._undo.pop()
        for obj in stroke:
            if obj.name in collection.objects:
                collection.objects.unlink(obj)
        self._redo.append(stroke)
        return True

    def redo(self, collection):
        if not self._redo:
            return False
        stroke = self._redo.pop()
        for obj in stroke:
            if obj.name not in collection.objects:
                collection.objects.link(obj)
        self._undo.append(stroke)
        return True

    def purge(self):
        """Brush exit: delete everything still waiting on the redo side."""
        self._delete_redo()

    def _delete_redo(self):
        for stroke in self._redo:
            for obj in stroke:
                if obj.name in bpy.data.objects:
                    curve = obj.data if obj.type == 'CURVE' else None
                    bpy.data.objects.remove(obj, do_unlink=True)
                    if curve is not None and curve.users == 0:
                        bpy.data.curves.remove(curve)  # the line's own data (copies share theirs)
        self._redo.clear()
