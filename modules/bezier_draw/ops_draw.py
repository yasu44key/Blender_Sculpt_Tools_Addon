"""Start / finish freehand Bezier drawing."""

import bpy

MIRROR_MOD_NAME = "STS Mirror"


class BezierDrawSettings(bpy.types.PropertyGroup):
    """Settings for the next stroke (Start Drawing)."""

    bevel_depth: bpy.props.FloatProperty(
        name="Curve Thickness", default=0.1, min=0.0, max=10.0, step=1, unit='LENGTH',
        description="Bevel depth of the new curve",
    )
    bevel_resolution: bpy.props.IntProperty(
        name="Bevel Resolution", default=4, min=0, max=32,
        description="Cross-section detail (0 = flat ribbon)",
    )
    depth_mode: bpy.props.EnumProperty(
        name="Depth",
        items=[
            ('SURFACE', "Surface", "Draw on the surface of other objects"),
            ('CURSOR',  "Cursor",  "Draw at the depth of the 3D cursor"),
        ],
        default='SURFACE',
    )
    use_pressure: bpy.props.BoolProperty(
        name="Pressure Radius", default=True,
        description="Tablet pressure changes the stroke thickness",
    )
    mirror_x: bpy.props.BoolProperty(name="X", description="Mirror the new curve across X")
    mirror_y: bpy.props.BoolProperty(name="Y", description="Mirror the new curve across Y")
    mirror_z: bpy.props.BoolProperty(name="Z", description="Mirror the new curve across Z")


def mirror_modifier(obj):
    return obj.modifiers.get(MIRROR_MOD_NAME) if obj else None


class CURVE_OT_sts_draw_start(bpy.types.Operator):
    """Create a new curve at the 3D cursor and switch to the Draw tool"""
    bl_idname = "curve.sts_draw_start"
    bl_label = "Start Drawing"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        ds = context.scene.sts_bezier_draw

        bpy.ops.curve.primitive_bezier_curve_add()
        obj = context.object
        obj.name = "DrawnBezier"
        cu = obj.data
        cu.dimensions = '3D'
        cu.bevel_depth = ds.bevel_depth
        cu.bevel_resolution = ds.bevel_resolution
        cu.bevel_mode = 'ROUND'
        cu.use_fill_caps = True

        # Mirror is a modifier (plane through the 3D cursor = object origin),
        # so it is live while drawing and never duplicates objects.
        axes = (ds.mirror_x, ds.mirror_y, ds.mirror_z)
        if any(axes):
            mod = obj.modifiers.new(MIRROR_MOD_NAME, 'MIRROR')
            mod.use_axis = axes

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.delete(type='VERT')

        cps = context.scene.tool_settings.curve_paint_settings
        cps.curve_type = 'BEZIER'
        cps.use_pressure_radius = ds.use_pressure
        cps.depth_mode = ds.depth_mode

        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.draw")
        except RuntimeError:
            # No 3D View (e.g. run from a script) — the curve is still ready.
            pass
        return {'FINISHED'}


class CURVE_OT_sts_draw_finish(bpy.types.Operator):
    """Leave drawing (back to Object Mode). An empty curve is removed"""
    bl_idname = "curve.sts_draw_finish"
    bl_label = "Finish Drawing"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.object
        if len(obj.data.splines) == 0:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data.users == 0:
                bpy.data.curves.remove(data)
            self.report({'INFO'}, "Nothing was drawn; the empty curve was removed")
        return {'FINISHED'}


classes = (
    BezierDrawSettings,
    CURVE_OT_sts_draw_start,
    CURVE_OT_sts_draw_finish,
)
