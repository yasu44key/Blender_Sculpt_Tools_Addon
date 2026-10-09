"""The Metaball Brush modal operator and its scene settings.

Replaces: MetaballBrushTool_v87.py (OBJECT_OT_metaball_brush_v87)

Fixed from the old version: mouse positions come from core.view3d instead of
context.region (a sidebar button no longer offsets the stroke), the draw
handler gets no startup context, the stroke object is created lazily (no
empty MetaStroke), TIME mode places the first ball on press, there is no
View Depth mode, and the mirror center is the 3D cursor.
"""

import math
import time

import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from ...core import view3d
from . import logic

HELP_LINES = (
    "Drag: paint",
    "Esc, Right-click: end (strokes stay)",
    "Middle mouse, wheel: navigate",
)


class MetaballBrushSettings(bpy.types.PropertyGroup):
    """Settings for the next Metaball Brush session."""

    depth_mode: bpy.props.EnumProperty(
        name="Depth Mode",
        items=view3d.DEPTH_ITEMS,
        default='CURSOR',
        description="How the depth of a placed ball is found",
    )
    plane_axis: bpy.props.EnumProperty(
        name="Plane Axis",
        items=view3d.PLANE_ITEMS,
        default='XY',
        description="Which world plane the balls are placed on",
    )
    placement_mode: bpy.props.EnumProperty(
        name="Placement Mode",
        items=(
            ('TIME', "Time", "Place a ball every interval while holding"),
            ('DISTANCE', "Distance", "Place a ball every distance_px pixels of mouse movement"),
        ),
        default='TIME',
        description="How balls are spaced while dragging",
    )
    undo_mode: bpy.props.EnumProperty(
        name="Undo Mode",
        items=(
            ('STROKE', "Stroke", "One undo step per stroke"),
            ('ELEMENT', "Element", "One undo step per placed ball"),
        ),
        default='STROKE',
        description="What Ctrl+Z undoes",
    )
    interval: bpy.props.FloatProperty(
        name="Placement Interval", default=0.1, min=0.01, max=2.0,
        description="Seconds between balls while holding (Time mode)",
    )
    distance_px: bpy.props.FloatProperty(
        name="Pixel Distance", default=20.0, min=1.0, max=200.0, subtype='PIXEL',
        description="Mouse movement in pixels before the next ball (Distance mode)",
    )
    min_size: bpy.props.FloatProperty(
        name="Min Size", default=0.25, min=0.001, unit='LENGTH',
        description="Ball radius at the lightest pen pressure",
    )
    max_size: bpy.props.FloatProperty(
        name="Max Size", default=1.0, min=0.001, unit='LENGTH',
        description="Ball radius at full pen pressure (and with a mouse)",
    )
    pressure_curve: bpy.props.FloatProperty(
        name="Pressure Curve", default=0.5, min=0.01, max=4.0,
        description="Pressure is raised to this power between min and max size",
    )
    resolution: bpy.props.FloatProperty(
        name="Resolution", default=0.1, min=0.01, max=1.0,
        description="Metaball resolution of the stroke object",
    )
    mirror_x: bpy.props.BoolProperty(
        name="Mirror X", default=False,
        description="Mirror each ball across the 3D cursor on X",
    )
    mirror_y: bpy.props.BoolProperty(
        name="Mirror Y", default=False,
        description="Mirror each ball across the 3D cursor on Y",
    )
    mirror_z: bpy.props.BoolProperty(
        name="Mirror Z", default=False,
        description="Mirror each ball across the 3D cursor on Z",
    )


class OBJECT_OT_sts_metaball_brush(bpy.types.Operator):
    """Drag in the 3D view to paint metaballs under the mouse"""
    bl_idname = "object.sts_metaball_brush"
    bl_label = "Metaball Brush"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.mode == 'OBJECT')

    def invoke(self, context, event):
        s = context.scene.sts_metaball_brush
        self._builder = None
        self._timer = None
        self._draw_handle = None
        self._ended = False
        self._last_time = None
        self._last_px = None
        self._mouse = (event.mouse_x, event.mouse_y)
        self._pressure = getattr(event, "pressure", 0.0)

        wm = context.window_manager
        self._timer = wm.event_timer_add(max(0.01, s.interval), window=context.window)
        self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (), 'WINDOW', 'POST_PIXEL')
        self._header(context, True)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        s = context.scene.sts_metaball_brush

        if event.value == 'PRESS' and event.type in {'ESC', 'RIGHTMOUSE'}:
            return self._end(context)  # the strokes drawn so far stay

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                region = view3d.window_region_under_mouse(context.area, event.mouse_x, event.mouse_y)
                if region is None:
                    return {'PASS_THROUGH'}  # click on the sidebar / header: not ours
                self._remember(event)
                self._builder = logic.StrokeBuilder(context, s.resolution)
                self._last_time = time.time()
                self._last_px = self._mouse
                self._place(context, region, s)  # the first ball lands on the press
                return {'RUNNING_MODAL'}
            if event.value == 'RELEASE':
                if self._builder is None:
                    return {'PASS_THROUGH'}  # release of a click the sidebar handled
                self._finish_stroke(context, s)
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if event.type in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            self._remember(event)
            if self._builder is None:
                return {'PASS_THROUGH'}
            if s.placement_mode == 'DISTANCE':
                region = view3d.window_region_under_mouse(context.area, event.mouse_x, event.mouse_y)
                if (region is not None
                        and logic.should_place('DISTANCE', 0.0, None, 0.0,
                                               self._mouse, self._last_px, s.distance_px)):
                    self._last_px = self._mouse
                    self._place(context, region, s)
            return {'RUNNING_MODAL'}

        if event.type == 'TIMER':
            if self._builder is not None and s.placement_mode == 'TIME':
                now = time.time()
                if logic.should_place('TIME', now, self._last_time, s.interval, None, None, 0.0):
                    region = view3d.window_region_under_mouse(context.area, *self._mouse)
                    if region is not None:
                        self._last_time = now
                        self._place(context, region, s)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}  # viewport navigation, Ctrl+Z, ...

    # ---------------------------------------------------------------- helpers

    def _remember(self, event):
        self._mouse = (event.mouse_x, event.mouse_y)
        self._pressure = getattr(event, "pressure", 0.0)

    def _place(self, context, region, s):
        co = view3d.pick_point(context, region, self._mouse[0], self._mouse[1],
                               s.depth_mode, s.plane_axis, 0.0,
                               exclude=self._builder.object)
        radius = logic.radius_from_pressure(self._pressure, s.min_size, s.max_size,
                                            s.pressure_curve)
        self._builder.add(co, radius, mirror=(s.mirror_x, s.mirror_y, s.mirror_z))
        if s.undo_mode == 'ELEMENT':
            self._undo_push("Add Metaball")

    def _finish_stroke(self, context, s):
        obj = self._builder.finish()
        self._builder = None
        self._last_time = None
        self._last_px = None
        if obj is not None and s.undo_mode == 'STROKE':
            self._undo_push("Metaball Stroke")

    @staticmethod
    def _undo_push(message):
        try:
            bpy.ops.ed.undo_push(message=message)
        except Exception:
            pass

    def _header(self, context, show):
        if context.area:
            context.area.header_text_set("   ".join(HELP_LINES) if show else None)

    def _cleanup(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if self._draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            self._draw_handle = None
        self._header(context, False)

    def _end(self, context):
        if self._builder is not None:
            self._finish_stroke(context, context.scene.sts_metaball_brush)
        self._ended = True
        self._cleanup(context)
        return {'FINISHED'}

    def cancel(self, context):
        """Cancelled from outside the modal: the strokes drawn so far stay."""
        if not self._ended:
            self._ended = True
            if self._builder is not None:
                self._builder.finish()
                self._builder = None
            self._cleanup(context)

    # ---------------------------------------------------------------- preview

    def _draw(self):
        """Brush circle at the mouse. Gets no startup context: it reads
        bpy.context and the operator's own mouse / pressure."""
        context = bpy.context
        area = context.area
        if area is None or area.type != 'VIEW_3D' or self._mouse is None:
            return
        region = view3d.window_region_under_mouse(area, self._mouse[0], self._mouse[1])
        if region is None or region.data is None:
            return
        s = context.scene.sts_metaball_brush
        radius = logic.radius_from_pressure(self._pressure, s.min_size, s.max_size,
                                            s.pressure_curve)
        rv3d = region.data
        center = view3d.mouse_on_plane(region, self._mouse[0], self._mouse[1],
                                       context.scene.cursor.location)
        right = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
        c2 = location_3d_to_region_2d(region, rv3d, center)
        e2 = location_3d_to_region_2d(region, rv3d, center + right * radius)
        if c2 is None or e2 is None:
            return
        r_px = max((c2 - e2).length, 1.0)
        x = self._mouse[0] - region.x
        y = self._mouse[1] - region.y
        verts = [(x + r_px * math.cos(2 * math.pi * i / 48),
                  y + r_px * math.sin(2 * math.pi * i / 48)) for i in range(48)]
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": verts})
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", (1.0, 1.0, 1.0, 0.7))
        batch.draw(shader)
        gpu.state.blend_set('NONE')


classes = (
    MetaballBrushSettings,
    OBJECT_OT_sts_metaball_brush,
)
