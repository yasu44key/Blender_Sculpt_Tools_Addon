"""The Draw Edges modal operator and its scene settings.

Replaces: Edge_Creation_Tool_4_5.py (OBJECT_OT_create_edge)

Fill Face and Toggle Edit Mode are not wrapped here: Blender's own F
(mesh.edge_face_add) and Tab do exactly that.
"""

import bpy

from ...core import view3d
from . import logic

HELP_LINES = (
    "Click: add point",
    "Drag: add points continuously",
    "Backspace: remove last",
    "C: close loop and finish",
    "Enter, Right-click: finish",
    "Esc: cancel (discard)",
    "Middle mouse, wheel: navigate",
)


class EdgeCreationSettings(bpy.types.PropertyGroup):
    """Settings for the next Draw Edges session."""

    target: bpy.props.EnumProperty(
        name="Target",
        items=(
            ('NEW', "New Object", "Draw into a new mesh object"),
            ('ACTIVE', "Active Mesh", "Add the vertices to the active mesh object"),
        ),
        default='NEW',
        description="Which mesh the drawn vertices go into",
    )
    surface_offset: bpy.props.FloatProperty(
        name="Surface Offset", default=0.0, min=0.0, max=1.0, unit='LENGTH',
        description="Move placed points along the surface normal",
    )
    depth_mode: bpy.props.EnumProperty(
        name="Depth Mode",
        items=view3d.DEPTH_ITEMS,
        default='SURFACE',
        description="How the depth of a placed point is found",
    )
    plane_axis: bpy.props.EnumProperty(
        name="Plane Axis",
        items=view3d.PLANE_ITEMS,
        default='XY',
        description="Which world plane the points are placed on",
    )
    drag_interval: bpy.props.FloatProperty(
        name="Drag Interval", default=0.1, min=0.001, unit='LENGTH',
        description="Minimum distance between the points placed while dragging",
    )
    fill_on_close: bpy.props.BoolProperty(
        name="Fill On Close", default=False,
        description="Make one face out of the added points when closing the loop",
    )


class MESH_OT_sts_edge_draw(bpy.types.Operator):
    """Click in the 3D view to place vertices and edges snapped to surfaces"""
    bl_idname = "mesh.sts_edge_draw"
    bl_label = "Draw Edges"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.mode in {'OBJECT', 'EDIT_MESH'})

    def invoke(self, context, _event):
        settings = context.scene.sts_edge_creation
        target = None
        if settings.target == 'ACTIVE':
            obj = context.object
            if obj is None or obj.type != 'MESH':
                self.report({'WARNING'}, "No active mesh object")
                return {'CANCELLED'}
            target = obj
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        self._builder = logic.EdgeBuilder(context, target)
        self._ended = False
        self._dragging = False
        self._last_co = None
        self._header(context, True)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _header(self, context, show):
        if context.area:
            context.area.header_text_set("   ".join(HELP_LINES) if show else None)

    def _region(self, context, event):
        return view3d.window_region_under_mouse(context.area, event.mouse_x, event.mouse_y)

    def _point(self, context, event, region):
        """World position of the point under the mouse, per depth_mode."""
        s = context.scene.sts_edge_creation
        return view3d.pick_point(context, region, event.mouse_x, event.mouse_y, s.depth_mode,
                                 s.plane_axis, s.surface_offset, exclude=self._builder.object)

    def modal(self, context, event):
        # While the left button is held down, every move that is far enough
        # places the next point: check this before classify_event, which lets
        # mouse moves through as viewport navigation.
        if self._dragging and event.type in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            region = self._region(context, event)
            if region is not None:
                co = self._point(context, event, region)
                interval = context.scene.sts_edge_creation.drag_interval
                if logic.drag_far_enough(self._last_co, co, interval):
                    self._builder.add_point(co)
                    self._last_co = co
            return {'RUNNING_MODAL'}

        action = logic.classify_event(event.type, event.value)
        if action == 'PASS':
            return {'PASS_THROUGH'}
        if action == 'ADD':
            region = self._region(context, event)
            if region is None:
                return {'PASS_THROUGH'}  # click on the sidebar / header: not ours
            self._last_co = self._point(context, event, region)
            self._builder.add_point(self._last_co)
            self._dragging = True
            return {'RUNNING_MODAL'}
        if action == 'END_DRAG':
            if not self._dragging:
                return {'PASS_THROUGH'}  # release of a click the sidebar handled
            self._dragging = False
            return {'RUNNING_MODAL'}
        if action == 'UNDO':
            self._builder.undo_last()
            self._last_co = None
            return {'RUNNING_MODAL'}
        if action == 'CLOSE':
            self._builder.close_loop(fill=context.scene.sts_edge_creation.fill_on_close)
            return self._end(context)
        if action == 'CANCEL':
            self._header(context, False)
            self._ended = True
            self._builder.cancel()
            return {'CANCELLED'}
        if action == 'FINISH':
            return self._end(context)
        return {'RUNNING_MODAL'}

    def _end(self, context):
        self._header(context, False)
        self._ended = True
        return {'FINISHED'} if self._builder.finish() is not None else {'CANCELLED'}

    def cancel(self, context):
        """Cancelled from outside the modal: discard, like Esc."""
        if not self._ended:
            self._header(context, False)
            self._ended = True
            self._builder.cancel()


classes = (
    EdgeCreationSettings,
    MESH_OT_sts_edge_draw,
)
