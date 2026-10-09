"""N-panel UI.

Curve tab
  Bezier Draw            settings for the next stroke, Start / Finish
    Effects              Spiral, Radius, Twist, Handles (scope follows the mode)
    Points               Subdivide / Decimate (Edit Mode)
    Convert              Points to Metaballs
Generate tab
  Parametric Curves      Spiral, Lissajous, Strand, Cross Net
"""

import bpy
from bpy.app.translations import pgettext_iface as iface

from ...core import curve_utils as cu
from ...core import tabs
from . import ops_draw, ops_generate


class _Panel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'


class VIEW3D_PT_sts_bezier_draw(_Panel, bpy.types.Panel):
    bl_label = "Bezier Draw"
    bl_category = tabs.CURVE

    def draw(self, context):
        layout = self.layout
        ds = context.scene.sts_bezier_draw
        obj = context.object
        drawing = context.mode == 'EDIT_CURVE'

        row = layout.row(align=True)
        row.scale_y = 1.4
        if drawing:
            row.operator("curve.sts_draw_finish", icon='CHECKMARK')
        else:
            row.operator("curve.sts_draw_start", icon='BRUSH_DATA')

        layout.use_property_split = True
        layout.use_property_decorate = False

        box = layout.box()
        box.label(text="New Stroke", icon='GREASEPENCIL')
        col = box.column()
        col.prop(ds, "bevel_depth")
        col.prop(ds, "bevel_resolution")
        col.prop(ds, "depth_mode")
        col.prop(ds, "use_pressure")
        row = col.row(heading="Mirror", align=True)
        row.prop(ds, "mirror_x", toggle=True)
        row.prop(ds, "mirror_y", toggle=True)
        row.prop(ds, "mirror_z", toggle=True)

        if cu.is_curve(obj):
            box = layout.box()
            box.label(text=iface("Active Curve") + ": " + obj.name, icon='CURVE_DATA',
                      translate=False)
            col = box.column()
            col.prop(obj.data, "bevel_depth", text="Curve Thickness")
            col.prop(obj.data, "bevel_resolution", text="Bevel Resolution")
            mod = ops_draw.mirror_modifier(obj)
            if mod:
                row = col.row(heading="Mirror", align=True)
                for i, axis in enumerate("XYZ"):
                    row.prop(mod, "use_axis", index=i, text=axis, toggle=True)


class VIEW3D_PT_sts_bezier_effects(_Panel, bpy.types.Panel):
    bl_label = "Effects"
    bl_category = tabs.CURVE
    bl_parent_id = "VIEW3D_PT_sts_bezier_draw"

    @classmethod
    def poll(cls, context):
        return cu.poll_curve_object_or_edit(context)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Applies to: " + cu.scope_label(context), icon='INFO')
        col = layout.column(align=True)
        col.operator("curve.sts_spiral", icon='FORCE_VORTEX')
        col.operator("curve.sts_radius_profile", icon='FULLSCREEN_EXIT')
        col.operator("curve.sts_tilt_step", icon='MOD_SCREW')
        col.operator("curve.sts_smooth_handles", icon='HANDLE_AUTO')


class VIEW3D_PT_sts_bezier_points(_Panel, bpy.types.Panel):
    bl_label = "Points"
    bl_category = tabs.CURVE
    bl_parent_id = "VIEW3D_PT_sts_bezier_draw"

    @classmethod
    def poll(cls, context):
        return cu.is_curve(context.object) and context.mode == 'EDIT_CURVE'

    def draw(self, _context):
        row = self.layout.row(align=True)
        row.operator("curve.sts_subdivide", icon='PARTICLE_POINT')
        row.operator("curve.sts_decimate", icon='MOD_DECIM')


class VIEW3D_PT_sts_bezier_convert(_Panel, bpy.types.Panel):
    bl_label = "Convert"
    bl_category = tabs.CURVE
    bl_parent_id = "VIEW3D_PT_sts_bezier_draw"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return cu.poll_curve_object_or_edit(context)

    def draw(self, context):
        self.layout.operator("curve.sts_points_to_metaballs", icon='META_BALL')
        if context.mode == 'OBJECT':
            self.layout.operator("curve.sts_connect_g1", icon='LINKED')


class VIEW3D_PT_sts_curve_generate(_Panel, bpy.types.Panel):
    bl_label = "Parametric Curves"
    bl_category = tabs.GENERATE

    def draw(self, context):
        col = self.layout.column(align=True)
        col.enabled = context.mode == 'OBJECT'
        for op, icon in ops_generate.GENERATORS:
            col.operator(op.bl_idname, icon=icon)
        if context.mode != 'OBJECT':
            self.layout.label(text="Object Mode only", icon='INFO')


classes = (
    VIEW3D_PT_sts_bezier_draw,
    VIEW3D_PT_sts_bezier_effects,
    VIEW3D_PT_sts_bezier_points,
    VIEW3D_PT_sts_bezier_convert,
    VIEW3D_PT_sts_curve_generate,
)
