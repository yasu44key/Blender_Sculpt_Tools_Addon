"""Convert Bezier points to other object types."""

import bpy

from ...core import curve_utils as cu


def build_metaballs(context, curve_obj, scale, resolution, selected_only):
    mb = bpy.data.metaballs.new(curve_obj.name + "_Meta")
    mb.resolution = resolution
    mw = curve_obj.matrix_world
    for spline in curve_obj.data.splines:
        if spline.type != 'BEZIER':
            continue
        for p in spline.bezier_points:
            if selected_only and not p.select_control_point:
                continue
            elem = mb.elements.new(type='BALL')
            elem.co = mw @ p.co
            elem.radius = p.radius * scale
    return cu.link_new_object(context, mb.name, mb, location=(0.0, 0.0, 0.0))


def remove_object_and_data(obj):
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0:
        bpy.data.metaballs.remove(data)


class CURVE_OT_sts_points_to_metaballs(bpy.types.Operator):
    """Put a metaball on every Bezier point (selected points in Edit Mode).
    While running: F / Shift+F = size, Up / Down = resolution, Enter = confirm, Esc = cancel"""
    bl_idname = "curve.sts_points_to_metaballs"
    bl_label = "Points to Metaballs"
    bl_options = {'REGISTER', 'UNDO'}

    scale: bpy.props.FloatProperty(name="Scale", default=1.0, min=0.01)
    resolution: bpy.props.FloatProperty(name="Resolution", default=0.2, min=0.01, max=1.0)

    @classmethod
    def poll(cls, context):
        return cu.poll_curve_object_or_edit(context)

    def _build(self, context):
        curve = context.object
        selected_only = context.mode == 'EDIT_CURVE'
        if selected_only:
            # Leave Edit Mode first; selection flags are kept on the data.
            bpy.ops.object.mode_set(mode='OBJECT')
        return build_metaballs(context, curve, self.scale, self.resolution, selected_only)

    def execute(self, context):
        self._build(context)
        return {'FINISHED'}

    def invoke(self, context, _event):
        self._obj = self._build(context)
        if not self._obj.data.elements:
            remove_object_and_data(self._obj)
            self.report({'WARNING'}, "No Bezier points selected")
            return {'CANCELLED'}
        self._header(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        if context.area:
            context.area.header_text_set(
                f"Scale {self.scale:.2f} (F / Shift+F)   Resolution {self.resolution:.2f} "
                "(Up / Down)   Enter: confirm   Esc: cancel")

    def _end(self, context):
        if context.area:
            context.area.header_text_set(None)

    def modal(self, context, event):
        if event.value == 'PRESS':
            if event.type == 'F':
                prev = self.scale
                self.scale = max(0.01, prev - 0.1) if event.shift else prev + 0.1
                for elem in self._obj.data.elements:
                    elem.radius *= self.scale / prev
            elif event.type in {'UP_ARROW', 'DOWN_ARROW'}:
                step = -0.01 if event.type == 'UP_ARROW' else 0.01
                self.resolution = min(1.0, max(0.01, self.resolution + step))
                self._obj.data.resolution = self.resolution
            elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'}:
                self._end(context)
                return {'FINISHED'}
            elif event.type in {'ESC', 'RIGHTMOUSE'}:
                remove_object_and_data(self._obj)
                self._end(context)
                return {'CANCELLED'}
            else:
                return {'PASS_THROUGH'}
            self._header(context)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


classes = (
    CURVE_OT_sts_points_to_metaballs,
)
