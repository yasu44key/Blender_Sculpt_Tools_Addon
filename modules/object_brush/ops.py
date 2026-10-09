"""The Object Brush modal operator and its scene settings.

Replaces: Object_Brush_Pro_Collection1_15.py (VIEW3D_OT_object_brush)

Fixed from the old version: mouse positions come from core.view3d (a
sidebar button no longer offsets the stroke), the random rotation turns
around the face normal, GRID snaps X / Y only and keeps the surface
height, copies carry no parent / constraints, one scene.ray_cast with the
brush source and the placed copies excluded replaces the per-object
casts, Ctrl+Z deletes copies that can no longer be redone, and there is
no separate "Set Selected as Brush" operator (the PointerProperty fields
have an eyedropper).
"""

import random

import bpy
from mathutils import Vector

from ...core import view3d
from . import logic

HELP_LINES = (
    "Drag: paint",
    "Ctrl+Z, Ctrl+Shift+Z: undo, redo",
    "Esc, Right-click: end (copies stay)",
)


class ObjectBrushSettings(bpy.types.PropertyGroup):
    """Settings for the next Object Brush session."""

    source: bpy.props.EnumProperty(
        name="Brush Source",
        items=(
            ('OBJECT', "Object", "Always place copies of one object"),
            ('COLLECTION', "Collection", "Pick a random object from a collection"),
        ),
        default='OBJECT',
        description="What the copies are made from",
    )
    brush_object: bpy.props.PointerProperty(
        name="Brush Object", type=bpy.types.Object,
        description="Object to copy (click the field, then click an object)",
    )
    brush_collection: bpy.props.PointerProperty(
        name="Brush Collection", type=bpy.types.Collection,
        description="Collection to pick copies from at random",
    )

    use_output_collection: bpy.props.BoolProperty(
        name="Output Collection", default=True,
        description="Put the copies into one collection",
    )
    target_collection: bpy.props.PointerProperty(
        name="Target Collection", type=bpy.types.Collection,
        description="Existing collection to put the copies into",
    )
    new_collection_name: bpy.props.StringProperty(
        name="New Collection Name", default="Brush_Output",
        description="Collection to create when none is picked",
    )

    brush_mode: bpy.props.EnumProperty(
        name="Placement Mode",
        items=(
            ('STROKE', "Stroke", "Place every spacing distance along the drag"),
            ('GRID', "Grid", "Place on a world grid (X / Y only, the height stays)"),
        ),
        default='STROKE',
        description="How copies are spaced while dragging",
    )
    spacing: bpy.props.FloatProperty(
        name="Stroke Spacing", default=1.0, min=0.01, unit='LENGTH',
        description="Distance between copies along the stroke",
    )
    grid_size: bpy.props.FloatProperty(
        name="Grid Spacing", default=1.0, min=0.01, unit='LENGTH',
        description="Distance between grid cells (X / Y)",
    )
    base_scale: bpy.props.FloatProperty(
        name="Base Scale", default=1.0, min=0.01,
        description="Size of a copy relative to the source",
    )
    use_pressure: bpy.props.BoolProperty(
        name="Pen Pressure", default=True,
        description="Scale the copies by pen pressure (a mouse counts as full pressure)",
    )

    align_to_normal: bpy.props.BoolProperty(
        name="Align to Normal", default=True,
        description="Point the copy's Z axis along the surface normal",
    )
    align_to_stroke: bpy.props.BoolProperty(
        name="Align to Stroke", default=False,
        description="Point the copy's Y axis along the drag direction",
    )

    jitter_scale: bpy.props.FloatProperty(
        name="Scale Jitter", default=0.0, min=0.0, max=1.0,
        description="Random scale variation",
    )
    random_rotation: bpy.props.FloatProperty(
        name="Random Rotation", default=0.0, min=0.0, max=3.14159, subtype='ANGLE',
        description="Random turn around the surface normal, up to this angle",
    )
    jitter_x: bpy.props.FloatProperty(
        name="Jitter X", default=0.0, unit='LENGTH',
        description="Random offset along the copy's X axis",
    )
    jitter_y: bpy.props.FloatProperty(
        name="Jitter Y", default=0.0, unit='LENGTH',
        description="Random offset along the copy's Y axis",
    )
    jitter_z: bpy.props.FloatProperty(
        name="Jitter Z", default=0.0, unit='LENGTH',
        description="Random offset along the copy's Z axis (the normal)",
    )


class OBJECT_OT_sts_object_brush(bpy.types.Operator):
    """Drag in the 3D view to place copies of the brush source on surfaces"""
    bl_idname = "object.sts_object_brush"
    bl_label = "Object Brush"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.mode == 'OBJECT')

    def invoke(self, context, event):
        s = context.scene.sts_object_brush
        if s.source == 'OBJECT':
            if s.brush_object is None:
                self.report({'WARNING'}, "Set a brush object first")
                return {'CANCELLED'}
        elif s.brush_collection is None or not s.brush_collection.objects:
            self.report({'WARNING'}, "Set a brush collection with objects first")
            return {'CANCELLED'}

        self._col = self._output_collection(context, s)
        self._history = logic.StrokeHistory()
        self._painting = False
        self._ended = False
        self._last_pos = None
        self._last_depth = None
        self._stroke_dir = Vector((0.0, 1.0, 0.0))
        self._grid_used = set()
        self._mouse = (event.mouse_x, event.mouse_y)
        self._pressure = getattr(event, "pressure", 0.0)

        context.area.header_text_set("   ".join(HELP_LINES))
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        s = context.scene.sts_object_brush

        if event.value == 'PRESS' and event.type == 'Z' and event.ctrl:
            if event.shift:
                self._history.redo(self._col)
            else:
                self._history.undo(self._col)
            return {'RUNNING_MODAL'}

        if event.value == 'PRESS' and event.type in {'ESC', 'RIGHTMOUSE', 'RET', 'NUMPAD_ENTER'}:
            return self._end(context)  # the copies placed so far stay

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                region = view3d.window_region_under_mouse(context.area, event.mouse_x, event.mouse_y)
                if region is None:
                    return {'PASS_THROUGH'}  # click on the sidebar / header: not ours
                self._remember(event)
                self._painting = True
                self._last_pos = None
                self._grid_used.clear()
                self._history.begin()
                self._try_place(context, region, s, force=True)  # the first copy lands on the press
                return {'RUNNING_MODAL'}
            if event.value == 'RELEASE':
                if not self._painting:
                    return {'PASS_THROUGH'}  # release of a click the sidebar handled
                self._painting = False
                self._last_pos = None
                self._history.end()
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if event.type in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            self._remember(event)
            if self._painting:
                region = view3d.window_region_under_mouse(context.area, event.mouse_x, event.mouse_y)
                if region is not None:
                    self._try_place(context, region, s)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}  # viewport navigation

    # ---------------------------------------------------------------- helpers

    def _remember(self, event):
        self._mouse = (event.mouse_x, event.mouse_y)
        self._pressure = getattr(event, "pressure", 0.0)

    @staticmethod
    def _output_collection(context, s):
        if not s.use_output_collection:
            return context.collection
        if s.target_collection:
            return s.target_collection
        name = s.new_collection_name or "Brush_Output"
        col = bpy.data.collections.get(name)
        if col is None:
            col = bpy.data.collections.new(name)
            context.scene.collection.children.link(col)
        return col

    def _exclude(self, s):
        """Ray-cast exclusion: the brush source and the copies placed so far."""
        exclude = set()
        if s.source == 'OBJECT':
            if s.brush_object:
                exclude.add(s.brush_object)
        elif s.brush_collection:
            exclude.update(s.brush_collection.objects)
        exclude.update(self._col.objects)
        return exclude

    def _surface_hit(self, context, origin, direction, s):
        """(Vector, normal) where the mouse ray hits a surface, or (None, None).

        The same scene.ray_cast + re-shoot rule as view3d.surface_point, but
        keeping the face normal (align_to_normal needs it).
        """
        exclude = self._exclude(s)
        depsgraph = context.evaluated_depsgraph_get()
        direction = Vector(direction).normalized()
        step = direction * 1e-4
        loc = Vector(origin)
        for _ in range(32):
            hit, co, normal, _index, obj, _matrix = context.scene.ray_cast(depsgraph, loc, direction)
            if not hit:
                return None, None
            if obj in exclude or getattr(obj, "original", None) in exclude:
                loc = co + step
                continue
            return co, normal.normalized()
        return None, None

    def _try_place(self, context, region, s, force=False):
        origin, direction = view3d.mouse_ray(region, self._mouse[0], self._mouse[1])
        co, normal = self._surface_hit(context, origin, direction, s)
        if co is None:
            # off the surface: keep the depth of the last hit (or the cursor depth)
            co = logic.depth_fallback(origin, direction, self._last_depth, context.scene.cursor.location)
            normal = -direction
        else:
            self._last_depth = (co - origin).length

        if self._last_pos is not None:
            diff = co - self._last_pos
            if diff.length > 1e-6:
                self._stroke_dir = diff.normalized()

        if s.brush_mode == 'GRID':
            snapped = logic.grid_snap_xy(co, s.grid_size)
            key = (round(snapped.x, 4), round(snapped.y, 4))
            if key in self._grid_used:
                return
            self._grid_used.add(key)
            self._place_at(context, s, snapped, normal)
            self._last_pos = snapped
            return

        if not force and not view3d.drag_far_enough(self._last_pos, co, s.spacing):
            return
        self._place_at(context, s, co, normal)
        self._last_pos = co

    def _pick_source(self, s):
        if s.source == 'OBJECT':
            return s.brush_object
        objects = list(s.brush_collection.objects)
        return random.choice(objects) if objects else None

    def _place_at(self, context, s, location, normal):
        source = self._pick_source(s)
        if source is None:
            return
        spin = random.uniform(-s.random_rotation, s.random_rotation)
        q = logic.instance_rotation(normal, self._stroke_dir, s.align_to_normal,
                                    s.align_to_stroke, spin)
        pressure = self._pressure if s.use_pressure else 1.0
        if pressure < 0.01:
            pressure = 1.0  # a plain mouse counts as full pressure
        scale = s.base_scale * pressure * (1.0 + random.uniform(-s.jitter_scale, s.jitter_scale))
        offset = Vector((random.uniform(-s.jitter_x, s.jitter_x),
                         random.uniform(-s.jitter_y, s.jitter_y),
                         random.uniform(-s.jitter_z, s.jitter_z)))
        obj = logic.place_instance(context, source, location + q @ offset, q, scale, self._col)
        self._history.add(obj)

    def _end(self, context):
        if self._painting:
            self._painting = False
            self._history.end()
        self._ended = True
        self._history.purge()  # copies that can no longer be redone are deleted
        if context.area:
            context.area.header_text_set(None)
        return {'FINISHED'}

    def cancel(self, context):
        """Cancelled from outside the modal: the copies placed so far stay."""
        if not self._ended:
            self._ended = True
            if self._painting:
                self._painting = False
                self._history.end()
            self._history.purge()
            if context.area:
                context.area.header_text_set(None)


classes = (
    ObjectBrushSettings,
    OBJECT_OT_sts_object_brush,
)
