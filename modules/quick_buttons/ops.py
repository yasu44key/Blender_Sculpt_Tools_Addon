"""One-press buttons: reset transforms, rotate / flatten / mirror / step along an axis.

Rotate, flatten, mirror and step go through Blender's own transform, so they work
in Object and Edit Mode and follow the current pivot point and the Affect Only toggles.
"""

import math

import bpy

AXES = (('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", ""))
_I = {'X': 0, 'Y': 1, 'Z': 2}


class QuickButtonsSettings(bpy.types.PropertyGroup):
    step: bpy.props.FloatProperty(name="Step", default=0.1, unit='LENGTH',
                                  description="Distance moved by the step buttons")


class OBJECT_OT_sts_quick_reset(bpy.types.Operator):
    """Reset location / rotation / scale of the selected objects (one axis or all)"""
    bl_idname = "object.sts_quick_reset"
    bl_label = "Reset Transform"
    bl_options = {'REGISTER', 'UNDO'}

    channel: bpy.props.EnumProperty(
        name="Channel",
        items=(('LOCATION', "Location", "Location to 0"),
               ('ROTATION', "Rotation", "Rotation to 0"),
               ('SCALE', "Scale", "Scale to 1")))
    axis: bpy.props.EnumProperty(name="Axis", items=AXES + (('ALL', "All", ""),), default='ALL')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects)

    def execute(self, context):
        axes = range(3) if self.axis == 'ALL' else (_I[self.axis],)
        for obj in context.selected_objects:
            for i in axes:
                if self.channel == 'LOCATION':
                    obj.location[i] = 0.0
                elif self.channel == 'SCALE':
                    obj.scale[i] = 1.0
                elif obj.rotation_mode in {'QUATERNION', 'AXIS_ANGLE'}:
                    if self.axis == 'ALL':      # no per-axis reset without Euler angles
                        obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                        obj.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
                else:
                    obj.rotation_euler[i] = 0.0
        return {'FINISHED'}


class _TransformButton:
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(name="Axis", items=AXES)

    @classmethod
    def poll(cls, context):
        return bpy.ops.transform.translate.poll()

    def _vector(self, along, rest):
        v = [rest, rest, rest]
        v[_I[self.axis]] = along
        return v

    def _axes(self):
        return [i == _I[self.axis] for i in range(3)]


class VIEW3D_OT_sts_quick_rotate(_TransformButton, bpy.types.Operator):
    """Rotate the selection around a global axis by a fixed angle"""
    bl_idname = "view3d.sts_quick_rotate"
    bl_label = "Quick Rotate"

    angle: bpy.props.FloatProperty(name="Angle", default=math.radians(90), subtype='ANGLE')

    def execute(self, context):
        bpy.ops.transform.rotate(value=self.angle, orient_axis=self.axis, orient_type='GLOBAL')
        return {'FINISHED'}


class VIEW3D_OT_sts_quick_flatten(_TransformButton, bpy.types.Operator):
    """Flatten the selection along a global axis (scale 0)"""
    bl_idname = "view3d.sts_quick_flatten"
    bl_label = "Flatten"

    def execute(self, context):
        bpy.ops.transform.resize(value=self._vector(0.0, 1.0), orient_type='GLOBAL',
                                 constraint_axis=self._axes())
        return {'FINISHED'}


class VIEW3D_OT_sts_quick_mirror(_TransformButton, bpy.types.Operator):
    """Mirror the selection along a global axis (scale -1)"""
    bl_idname = "view3d.sts_quick_mirror"
    bl_label = "Mirror"

    def execute(self, context):
        bpy.ops.transform.resize(value=self._vector(-1.0, 1.0), orient_type='GLOBAL',
                                 constraint_axis=self._axes())
        return {'FINISHED'}


class VIEW3D_OT_sts_quick_step(_TransformButton, bpy.types.Operator):
    """Move the selection along a global axis by the step distance"""
    bl_idname = "view3d.sts_quick_step"
    bl_label = "Step"

    distance: bpy.props.FloatProperty(name="Distance", default=0.1, unit='LENGTH')

    def execute(self, context):
        bpy.ops.transform.translate(value=self._vector(self.distance, 0.0), orient_type='GLOBAL',
                                    constraint_axis=self._axes())
        return {'FINISHED'}


classes = (
    QuickButtonsSettings,
    OBJECT_OT_sts_quick_reset,
    VIEW3D_OT_sts_quick_rotate,
    VIEW3D_OT_sts_quick_flatten,
    VIEW3D_OT_sts_quick_mirror,
    VIEW3D_OT_sts_quick_step,
)
