"""GUI-free logic for the Edge Creation module.

Replaces: Edge_Creation_Tool_4_5.py

The modal operator only collects events and mouse coordinates; every
decision it makes lives here so it can be tested without a 3D view
(tests/test_edge_creation.py).
"""

import bpy
import bmesh
from mathutils import Vector

# Point picking is shared with other modules; kept importable from here.
from ...core.view3d import drag_far_enough, plane_point, surface_point  # noqa: F401

# Event types that are viewport navigation while drawing.
_NAV_TYPES = {
    'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
    'WHEELINMOUSE', 'WHEELOUTMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM',
    'MOUSEROTATE', 'MOUSESMARTZOOM', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'NDOF_MOTION',
}

_FINISH_TYPES = {'RET', 'NUMPAD_ENTER', 'RIGHTMOUSE'}

# World plane through the origin for each plane_axis: the normal is the axis
# that is missing from the name (XY -> Z = 0).


def classify_event(event_type, value):
    """Map a modal event to 'ADD' / 'UNDO' / 'CLOSE' / 'FINISH' / 'CANCEL' /
    'END_DRAG' / 'PASS' / 'NONE'.

    Esc discards (Blender's convention); Enter and right-click finish.
    """
    if event_type in _NAV_TYPES:
        return 'PASS'
    if event_type.startswith('NDOF_'):
        return 'PASS'
    if event_type.startswith('NUMPAD_'):
        if event_type == 'NUMPAD_ENTER' and value == 'PRESS':
            return 'FINISH'
        return 'PASS'
    if value == 'PRESS':
        if event_type == 'LEFTMOUSE':
            return 'ADD'
        if event_type == 'BACK_SPACE':
            return 'UNDO'
        if event_type == 'C':
            return 'CLOSE'
        if event_type == 'ESC':
            return 'CANCEL'
        if event_type in _FINISH_TYPES:
            return 'FINISH'
    elif value == 'RELEASE' and event_type == 'LEFTMOUSE':
        return 'END_DRAG'
    return 'NONE'


class EdgeBuilder:
    """Adds vertices and edges to a mesh one click at a time.

    target=None  -> a new mesh object is created on the first add_point
                    (not before).
    target=obj   -> vertices are appended to that object's mesh; world
                    coordinates are converted to its local space.

    Existing geometry is never modified or removed. The session keeps one
    bmesh (bmesh.new -> from_mesh -> edit -> to_mesh after every step) and
    holds direct BMVert references for the points it added: bmesh's index
    table goes stale once vertices are added, so bm.verts[i] is never used.
    finish() selects the added vertices by their coordinates instead.
    """

    def __init__(self, context, target=None):
        self._context = context
        self.object = target
        self._created = target is None
        self._bm = None
        self._verts = []   # BMVert references of the points we added
        self._coords = []  # their local coordinates (used by finish)

    @property
    def count(self):
        return len(self._verts)

    def _open_bm(self):
        if self._bm is None:
            self._bm = bmesh.new()
            if self.object is not None:
                self._bm.from_mesh(self.object.data)

    def _write_back(self):
        self._bm.to_mesh(self.object.data)
        self.object.data.update()

    def add_point(self, world_co):
        if self.object is None:
            mesh = bpy.data.meshes.new("EdgePath")
            obj = bpy.data.objects.new("Edge Path", mesh)
            self._context.collection.objects.link(obj)
            self.object = obj

        local = self.object.matrix_world.inverted() @ Vector(world_co)
        self._open_bm()
        prev = self._verts[-1] if self._verts else None
        try:
            new_v = self._bm.verts.new(local)
        except ValueError:  # same spot clicked twice
            return
        if prev is not None:
            self._bm.edges.new((prev, new_v))
        self._verts.append(new_v)
        self._coords.append(local)
        self._write_back()

    def undo_last(self):
        if not self._verts:
            return False
        self._bm.verts.remove(self._verts.pop())
        self._coords.pop()
        self._write_back()
        return True

    def close_loop(self, fill=False):
        """Connect the last point back to the first. With fill=True, also make
        one face out of the points this session added.
        """
        if self.count < 3:
            return False
        if self._bm.edges.get((self._verts[0], self._verts[-1])) is not None:
            return False
        self._bm.edges.new((self._verts[0], self._verts[-1]))
        if fill:
            try:
                self._bm.faces.new(self._verts)
            except ValueError:  # not a usable polygon (collinear points, ...)
                pass
        self._write_back()
        return True

    def cancel(self):
        """Discard everything this session added and end in Object Mode.

        Returns None. A target object keeps its own geometry: only the points
        (and the edges between them) this session added are removed. An object
        this session created is removed entirely.
        """
        obj = self.object
        if self._bm is not None:
            for v in self._verts:  # removing a vertex removes its edges too
                try:
                    self._bm.verts.remove(v)
                except ValueError:
                    pass
            self._verts.clear()
            self._coords.clear()
            if obj is not None and not self._created:
                self._write_back()
            self._bm.free()
            self._bm = None

        if obj is not None and self._created:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data.users == 0:
                bpy.data.meshes.remove(data)
        self.object = None
        return None

    def finish(self):
        """End the session. Returns the object, or None when nothing was added.

        An object this builder created is removed when no points were added;
        a user's target object is never removed.
        """
        obj = self.object
        if self._bm is not None:
            self._bm.free()
            self._bm = None

        if self.count == 0:
            if obj is not None and self._created:
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if data.users == 0:
                    bpy.data.meshes.remove(data)
            self.object = None
            return None

        for o in self._context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        self._context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(obj.data)
        for v in bm.verts:
            v.select = any((v.co - c).length < 1e-6 for c in self._coords)
        bmesh.update_edit_mesh(obj.data)
        return obj
