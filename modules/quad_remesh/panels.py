"""Model tab panel for Quad Remesh."""

import bpy

from ...core import annotation, tabs
from . import engine, ops

QREMESHIFY_URL = "https://github.com/ksami/QRemeshify"


class VIEW3D_PT_sts_quad_remesh(bpy.types.Panel):
    bl_label = "Quad Remesh"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        if engine.find_engine() is None:
            box = layout.box()
            box.label(text="Needs QRemeshify (free, GPL)", icon='ERROR')
            box.label(text="It provides the QuadWild engine")
            box.operator("wm.url_open", text="Get QRemeshify", icon='URL').url = QREMESHIFY_URL
            return

        job = ops.RUN["job"]
        if job is not None:
            layout.progress(factor=job.fraction, type='BAR',
                            text=bpy.app.translations.pgettext_iface(job.message))
            layout.operator("object.sts_quad_cancel", icon='CANCEL')
            return

        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            layout.label(text="Select a mesh", icon='INFO')
            return
        lib = engine.find_engine()
        layout.label(text="Engine: STS (density maps)" if engine.supports_density(lib)
                     else "Engine: QRemeshify (no density maps)", icon='SETTINGS')
        layout.label(text=bpy.app.translations.pgettext_iface("Target: ") + bpy.app.translations.pgettext_iface(ops.target_label(context)))
        col = layout.column()
        col.scale_y = 1.3
        col.enabled = context.mode in {'OBJECT', 'EDIT_MESH', 'SCULPT'}
        col.operator("object.sts_quad_remesh", icon='MOD_REMESH')
        if not col.enabled:
            layout.label(text="Object, Edit or Sculpt Mode only", icon='INFO')

        self.draw_guides(context, layout, obj)

        fit = obj.modifiers.get(ops.FIT)
        if fit is not None:
            box = layout.box()
            box.label(text="Fit to Source", icon='MOD_SHRINKWRAP')
            box.use_property_split = True
            box.prop(fit, "target")
            box.prop(fit, "offset")
            box.prop(fit, "show_viewport", text="Show")
            col = box.column()
            col.scale_y = 1.2
            col.enabled = context.mode == 'OBJECT'
            col.operator("object.sts_quad_project_detail", icon='MOD_MULTIRES')


    def draw_guides(self, context, layout, obj):
        iface = bpy.app.translations.pgettext_iface
        box = layout.box()
        n = len(ops.guide_strokes(context, obj))
        box.label(text=iface("Guide Lines") + ": %d" % n, icon='GREASEPENCIL')
        col = box.column(align=True)
        sub = col.row(align=True)
        sub.enabled = annotation.CAN_WRITE and context.mode in {'OBJECT', 'SCULPT'}
        sub.operator("object.sts_quad_detect_creases", icon='VIEWZOOM')
        row = col.row(align=True)
        row.operator("object.sts_quad_draw_guides", text="Draw on Surface", icon='GREASEPENCIL').erase = False
        row.operator("object.sts_quad_draw_guides", text="Erase", icon='X').erase = True
        if not annotation.CAN_WRITE:
            box.label(text="Detecting needs Blender 5.2+", icon='INFO')
        ann = context.scene.annotation
        if ann is not None:
            for name in (ops.RIDGE, ops.VALLEY, ops.GUIDE):
                layer = ann.layers.get(name)
                if layer is not None:
                    r = box.row(align=True).split(factor=0.18, align=True)
                    r.prop(layer, "color", text="")
                    r = r.row(align=True)
                    r.label(text=name)
                    r.prop(layer, "annotation_hide", text="", emboss=False,
                           icon='HIDE_ON' if layer.annotation_hide else 'HIDE_OFF')
                    r.operator("object.sts_quad_clear_guides", text="", icon='TRASH', emboss=False).layer = name
            if ann.layers.get(ops.RIDGE) is not None or ann.layers.get(ops.VALLEY) is not None:
                box.operator("object.sts_quad_clear_guides", text="Clear Detected Lines", icon='TRASH').layer = ""
        box.label(text="Uses the visible layers", icon='INFO')


classes = (VIEW3D_PT_sts_quad_remesh,)
