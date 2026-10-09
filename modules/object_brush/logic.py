"""GUI-free logic for the Object Brush module.

Replaces: Object_Brush_Pro_Collection1_15.py

The grid snapping (X / Y only, the height stays), the rotation spun around
the face normal, the depth kept when the ray misses, the parent-free
instance copy and the stroke-level undo / redo live here so they can be
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
                    bpy.data.objects.remove(obj, do_unlink=True)
        self._redo.clear()
