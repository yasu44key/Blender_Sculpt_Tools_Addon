"""GUI-free logic for the Metaball Brush module.

Replaces: MetaballBrushTool_v87.py

The pressure -> radius rule, the mirror offsets, the time / distance gating
and the stroke -> metaball-object building live here so they can be tested
without a 3D view (tests/test_metaball_brush.py).
"""

import bpy
from mathutils import Vector


def radius_from_pressure(pressure, min_size, max_size, curve):
    """Brush radius for a pen pressure. None / 0 (a plain mouse) -> max size."""
    if pressure is None or pressure <= 0.0:
        return max_size
    return min_size + (max_size - min_size) * pressure ** curve


def mirror_offsets(offset, mirror_x, mirror_y, mirror_z):
    """The offset position mirrored around the object origin (up to 8 copies).

    Offsets that land on the same spot (a point on a mirror plane) are
    collapsed into one entry.
    """
    offset = Vector(offset)
    out = []
    for sx in (1, -1) if mirror_x else (1,):
        for sy in (1, -1) if mirror_y else (1,):
            for sz in (1, -1) if mirror_z else (1,):
                v = Vector((offset.x * sx, offset.y * sy, offset.z * sz))
                if not any((v - u).length < 1e-9 for u in out):
                    out.append(v)
    return out


def should_place(mode, now, last_time, interval, mouse_px, last_px, distance_px):
    """Gate for placing the next ball while dragging.

    TIME: first placement, or interval seconds since the last one
    (interval - 1e-9 so float error does not skip a placement).
    DISTANCE: first placement, or the mouse moved distance_px pixels.
    """
    if mode == 'TIME':
        if last_time is None:
            return True
        return (now - last_time) >= interval - 1e-9
    if last_px is None:
        return True
    return (Vector(mouse_px) - Vector(last_px)).length >= distance_px


class StrokeBuilder:
    """One stroke = one metaball object.

    The object is created on the first add (not before), so a quick or
    misplaced click never leaves an empty MetaStroke behind. Its origin is
    the 3D cursor at creation time: mirror offsets are mirrored around it.
    """

    def __init__(self, context, resolution):
        self._context = context
        self._resolution = resolution
        self._count = 0
        self.object = None

    @property
    def count(self):
        return self._count

    def _ensure_object(self):
        if self.object is not None:
            return
        metaball = bpy.data.metaballs.new("MetaStroke")
        metaball.resolution = self._resolution
        obj = bpy.data.objects.new("MetaStroke", metaball)
        self._context.collection.objects.link(obj)
        obj.location = Vector(self._context.scene.cursor.location)
        self._context.view_layer.update()
        self.object = obj

    def add(self, world_co, radius, mirror=(False, False, False)):
        """Add a BALL (and its mirror copies) at a world position."""
        self._ensure_object()
        local = self.object.matrix_world.inverted() @ Vector(world_co)
        for off in mirror_offsets(local, *mirror):
            elem = self.object.data.elements.new(type='BALL')
            elem.co = off
            elem.radius = radius
            self._count += 1

    def finish(self):
        """End the stroke. Returns the object, or None when nothing was placed.

        An empty stroke removes the object it would have created; a stroke
        with elements keeps its object (also after finish).
        """
        obj = self.object
        if self._count == 0:
            if obj is not None:
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if data.users == 0:
                    bpy.data.metaballs.remove(data)
            self.object = None
            return None
        return obj
