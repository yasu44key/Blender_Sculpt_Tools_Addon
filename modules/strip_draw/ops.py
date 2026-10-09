"""Strip Draw operators and the settings for the next stroke."""

import bpy

from . import strip


def _mesh_poll(_self, obj):
    return obj.type == 'MESH'


class StripDrawSettings(bpy.types.PropertyGroup):
    """Settings for the next strip (each strip keeps its own copy on its modifier)."""

    target: bpy.props.PointerProperty(
        name="Draw On", type=bpy.types.Object, poll=_mesh_poll,
        description="Mesh to draw on (empty = the active mesh when drawing starts)")
    style: bpy.props.EnumProperty(
        name="Style",
        items=(('RIBBON', "Ribbon", "A clean band (armor plates, straps)"),
               ('CLAY', "Clay", "A soft remeshed strip (clay added by hand)")),
        default='RIBBON')
    width: bpy.props.FloatProperty(name="Width", default=0.05, min=0.0001, soft_max=1.0, unit='LENGTH',
                                   description="Band width (times the pen pressure)")
    offset: bpy.props.FloatProperty(name="Offset", default=0.002, soft_min=-0.1, soft_max=0.1, unit='LENGTH',
                                    description="Lift above the surface")
    thickness: bpy.props.FloatProperty(name="Band Thickness", default=0.01, min=0.0, soft_max=0.2, unit='LENGTH',
                                       description="Thickness of the band (0 = a flat ribbon)")
    voxel_size: bpy.props.FloatProperty(name="Voxel Size", default=0.005, min=0.0001, soft_max=0.1, unit='LENGTH',
                                        description="Detail of the clay remesh")
    use_pressure: bpy.props.BoolProperty(name="Pressure Width", default=True,
                                         description="Pen pressure changes the band width")


def _target(context):
    s = context.scene.sts_strip_draw
    if s.target is not None:
        return s.target
    obj = context.active_object
    return obj if obj is not None and obj.type == 'MESH' else None


class CURVE_OT_sts_strip_start(bpy.types.Operator):
    """Start drawing a strip on the surface (the active mesh, or the Surface set in the panel)"""
    bl_idname = "curve.sts_strip_start"
    bl_label = "Start Strip"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        s = context.scene.sts_strip_draw
        target = _target(context)
        if target is None:
            self.report({'WARNING'}, "Select the surface (a mesh) first")
            return {'CANCELLED'}
        s.target = target
        data = bpy.data.curves.new("Strip", 'CURVE')
        data.dimensions = '3D'
        obj = bpy.data.objects.new("Strip", data)      # at the origin: drawn points are world positions
        context.collection.objects.link(obj)
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        strip.add(obj, target, s)
        bpy.ops.object.mode_set(mode='EDIT')

        cps = context.scene.tool_settings.curve_paint_settings
        cps.curve_type = 'POLY'
        cps.depth_mode = 'SURFACE'
        cps.use_pressure_radius = s.use_pressure
        cps.surface_offset = 0.0
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.draw")
        except RuntimeError:
            pass   # no 3D view (scripts / tests)
        return {'FINISHED'}


class CURVE_OT_sts_strip_finish(bpy.types.Operator):
    """Stop drawing (back to Object Mode). A strip with nothing drawn is removed"""
    bl_idname = "curve.sts_strip_finish"
    bl_label = "Finish Strip"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.object
        if strip.get(obj) is not None and len(obj.data.splines) == 0:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data.users == 0:
                bpy.data.curves.remove(data)
            self.report({'INFO'}, "Nothing was drawn; the empty strip was removed")
        return {'FINISHED'}


class OBJECT_OT_sts_strip_from_curves(bpy.types.Operator):
    """Turn the selected curves into strips on the surface (the Surface set in the panel,
or the active object if it is a mesh)"""
    bl_idname = "object.sts_strip_from_curves"
    bl_label = "Strips from Curves"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        target = _target(context)
        curves = [o for o in context.selected_objects if o.type == 'CURVE']
        if target is None or not curves:
            self.report({'WARNING'}, "Select curves and a surface (a mesh, active or set in the panel)")
            return {'CANCELLED'}
        context.scene.sts_strip_draw.target = target
        for c in curves:
            strip.add(c, target, context.scene.sts_strip_draw)
        return {'FINISHED'}


class OBJECT_OT_sts_strip_to_mesh(bpy.types.Operator):
    """Make the selected strips real meshes (the drawn curves become the band meshes)"""
    bl_idname = "object.sts_strip_to_mesh"
    bl_label = "Strips to Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        strips = [o for o in context.selected_objects if strip.get(o) is not None]
        if not strips:
            self.report({'WARNING'}, "Select strips")
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(o in strips)
        context.view_layer.objects.active = strips[0]
        bpy.ops.object.convert(target='MESH')
        return {'FINISHED'}


classes = (
    StripDrawSettings,
    CURVE_OT_sts_strip_start,
    CURVE_OT_sts_strip_finish,
    OBJECT_OT_sts_strip_from_curves,
    OBJECT_OT_sts_strip_to_mesh,
)
