"""Point Smooth operators (Edit Mode: mesh / curve / NURBS surface)."""

import bpy

from . import inflate_wrap, smooth


class PointSmoothSettings(bpy.types.PropertyGroup):
    """Scene settings. Only the wrap target lives here (an operator cannot
    hold an Object reference); amounts and strengths live on the operators."""

    def _poll_mesh(self, obj):
        return obj is not None and obj.type == 'MESH'

    wrap_target: bpy.props.PointerProperty(
        name="Wrap Target",
        description="Mesh object the selected points are wrapped onto",
        type=bpy.types.Object,
        poll=_poll_mesh,
    )


class OBJECT_OT_sts_point_smooth(bpy.types.Operator):
    bl_idname = "object.sts_point_smooth"
    bl_label = "Point Smooth"
    bl_options = {'REGISTER', 'UNDO'}

    strength: bpy.props.FloatProperty(
        name="Strength",
        description="How far each point moves toward the smoothed position",
        subtype='FACTOR', default=1.0, min=0.0, max=1.0)
    iterations: bpy.props.IntProperty(
        name="Iterations",
        description="Repeat the smoothing this many times",
        default=1, min=1, max=100)
    fix_boundary: bpy.props.BoolProperty(
        name="Fix Boundary",
        description="Keep the outer vertices of a 2D selection "
                    "(touching unselected points or on the mesh border)",
        default=True)
    tangent_smooth: bpy.props.BoolProperty(
        name="Tangent Smooth",
        description="Move only along the surface (no shrinking toward the inside)",
        default=False)
    auto_handle_length: bpy.props.BoolProperty(
        name="Auto Handle Length",
        description="Set Bezier handle length to a third of the distance to the neighbouring points",
        default=False)

    @classmethod
    def poll(cls, context):
        return context.mode in {'EDIT_MESH', 'EDIT_CURVE', 'EDIT_SURFACE'}

    def execute(self, context):
        processed = False
        for obj in context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                processed = smooth.smooth_mesh(obj, self) or processed
            elif obj.type == 'CURVE':
                processed = smooth.smooth_curve(obj, self) or processed
            elif obj.type == 'SURFACE':
                processed = smooth.smooth_surface(obj, self) or processed
        if not processed:
            self.report({'WARNING'}, "Select at least 3 connected points to smooth")
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_OT_sts_point_inflate(bpy.types.Operator):
    bl_idname = "object.sts_point_inflate"
    bl_label = "Inflate Points"
    bl_description = ("Push the selected points along their normals "
                      "(boundary stays, the middle moves the most)")
    bl_options = {'REGISTER', 'UNDO'}

    amount: bpy.props.FloatProperty(
        name="Amount",
        description="Distance along the normal (negative moves inward)",
        unit='LENGTH', default=0.1)
    fix_boundary: bpy.props.BoolProperty(
        name="Fix Boundary",
        description="Keep the outer points of the selection "
                    "(touching unselected points or on the mesh / grid border)",
        default=True)

    @classmethod
    def poll(cls, context):
        return context.mode in {'EDIT_MESH', 'EDIT_CURVE', 'EDIT_SURFACE'}

    def execute(self, context):
        context.view_layer.update()
        processed = False
        for obj in context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                processed = inflate_wrap.inflate_mesh(obj, self) or processed
            elif obj.type == 'CURVE':
                processed = inflate_wrap.inflate_curve(obj, self) or processed
            elif obj.type == 'SURFACE':
                processed = inflate_wrap.inflate_surface(obj, self) or processed
        if not processed:
            self.report({'WARNING'}, "Select at least 3 points (a straight run has no plane to inflate along)")
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_OT_sts_point_wrap(bpy.types.Operator):
    bl_idname = "object.sts_point_wrap"
    bl_label = "Wrap Points"
    bl_description = ("Move the selected points onto the wrap target's surface "
                      "(modifiers included) plus an offset along its normal")
    bl_options = {'REGISTER', 'UNDO'}

    strength: bpy.props.FloatProperty(
        name="Strength",
        description="How far each point moves toward the target surface",
        subtype='FACTOR', default=1.0, min=0.0, max=1.0)
    offset: bpy.props.FloatProperty(
        name="Offset",
        description="Distance from the target surface along its normal",
        unit='LENGTH', default=0.0)
    iterations: bpy.props.IntProperty(
        name="Iterations",
        description="Repeat the wrapping this many times",
        default=1, min=1, max=100)
    fix_boundary: bpy.props.BoolProperty(
        name="Fix Boundary",
        description="Keep the outer points of the selection "
                    "(touching unselected points or on the mesh / grid border)",
        default=True)

    @classmethod
    def poll(cls, context):
        return context.mode in {'EDIT_MESH', 'EDIT_SURFACE'}

    def execute(self, context):
        target = context.scene.sts_point_smooth.wrap_target
        if target is None:
            self.report({'WARNING'}, "Set a Wrap Target (a mesh object) first")
            return {'CANCELLED'}
        context.view_layer.update()
        objs = [o for o in context.objects_in_mode_unique_data if o != target]
        if not objs:
            self.report({'WARNING'}, "The Wrap Target cannot be the object being edited")
            return {'CANCELLED'}
        processed = False
        for obj in objs:
            if obj.type == 'MESH':
                processed = inflate_wrap.wrap_mesh(obj, target, self, context) or processed
            elif obj.type == 'SURFACE':
                processed = inflate_wrap.wrap_surface(obj, target, self, context) or processed
        if not processed:
            self.report({'WARNING'}, "Select the points to wrap")
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (
    PointSmoothSettings,
    OBJECT_OT_sts_point_smooth,
    OBJECT_OT_sts_point_inflate,
    OBJECT_OT_sts_point_wrap,
)
