"""Strip Draw operators and the settings for the next stroke."""

import bpy

from . import points, strip, surface


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
    # Plain Blender units (no unit display): 1 unit = 1 mm in a millimetre scene.
    width: bpy.props.FloatProperty(name="Width", default=5.0, min=0.0001, soft_max=50.0,
                                   description="Band width (times the pen pressure)")
    offset: bpy.props.FloatProperty(name="Offset", default=0.1, soft_min=-5.0, soft_max=5.0,
                                    description="Lift above the surface")
    thickness: bpy.props.FloatProperty(name="Band Thickness", default=1.0, min=0.0, soft_max=20.0,
                                       description="Thickness of the band (0 = a flat ribbon)")
    voxel_size: bpy.props.FloatProperty(name="Voxel Size", default=0.1, min=0.0001, soft_max=5.0,
                                        description="Detail of the clay remesh")
    spacing: bpy.props.FloatProperty(name="Point Spacing", default=1.0, min=0.0, soft_max=10.0,
                                     description="Distance between the points of a drawn stroke, "
                                                 "evened out right after each stroke (0 = keep every pen sample)")
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
        if strip.get(obj) is not None:
            # strokes were evened one by one while drawing (live.py), so a Subdivide done
            # in between is kept; only pen taps are dropped here
            points.drop_stray(obj.data)
            strip.node_group()          # strips on an older node group move onto the current one
            found = surface.fit_target(context, obj, strip.get(obj), strip)
            if found is not None:
                msg = bpy.app.translations.pgettext("Drawn on {}: Target set to it")
                self.report({'INFO'}, msg.format(found.name))
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


class _PointsOperator:
    """Rebuild the points of the selected curves (Object Mode), or of the edited curve
    (Edit Mode: the splines with a selected point, or all of them when none is selected)."""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_CURVE'} and bool(_curves(context))

    def points_fn(self):
        raise NotImplementedError

    def execute(self, context):
        editing = context.mode == 'EDIT_CURVE'
        if editing:
            bpy.ops.object.mode_set(mode='OBJECT')
        fn = self.points_fn()
        before = after = 0
        for o in _curves(context):
            b, a = points.apply(o.data, fn, only_selected=editing)
            before, after = before + b, after + a
        if editing:
            bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, f"Points: {before} -> {after}")
        return {'FINISHED'}


def _curves(context):
    if context.mode == 'EDIT_CURVE':
        return [context.object] if context.object is not None else []
    return [o for o in context.selected_objects if o.type == 'CURVE']


class CURVE_OT_sts_strip_resample(_PointsOperator, bpy.types.Operator):
    """Even out the points of the strips: one point every Point Spacing"""
    bl_idname = "curve.sts_strip_resample"
    bl_label = "Even Spacing"

    spacing: bpy.props.FloatProperty(name="Point Spacing", default=1.0, min=0.0001, soft_max=10.0,
                                     description="Distance between the points")

    def invoke(self, context, _event):
        self.spacing = max(context.scene.sts_strip_draw.spacing, 0.0001)
        return self.execute(context)

    def points_fn(self):
        return lambda pts, cyclic: points.resample(pts, self.spacing, cyclic)


class CURVE_OT_sts_strip_decimate(_PointsOperator, bpy.types.Operator):
    """Thin out the points of the strips (keep every Nth point; the ends stay)"""
    bl_idname = "curve.sts_strip_decimate"
    bl_label = "Decimate"

    keep_every: bpy.props.IntProperty(name="Keep Every", default=2, min=2, soft_max=10,
                                      description="Keep one point out of this many")

    def points_fn(self):
        return lambda pts, cyclic: points.decimate(pts, self.keep_every, cyclic)


class CURVE_OT_sts_strip_subdivide(_PointsOperator, bpy.types.Operator):
    """Add points between the points of the strips"""
    bl_idname = "curve.sts_strip_subdivide"
    bl_label = "Subdivide"

    cuts: bpy.props.IntProperty(name="Cuts", default=1, min=1, soft_max=10,
                                description="Points added in every segment")

    def points_fn(self):
        return lambda pts, cyclic: points.subdivide(pts, self.cuts, cyclic)


classes = (
    StripDrawSettings,
    CURVE_OT_sts_strip_start,
    CURVE_OT_sts_strip_finish,
    OBJECT_OT_sts_strip_from_curves,
    OBJECT_OT_sts_strip_to_mesh,
    CURVE_OT_sts_strip_resample,
    CURVE_OT_sts_strip_decimate,
    CURVE_OT_sts_strip_subdivide,
)
