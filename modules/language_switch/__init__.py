"""Language Switch — switch the interface between Japanese and English.

Replaces: Switch_Jp_En.py

The settings are Blender's own preferences (Preferences > Interface), so
nothing is stored in the .blend file and the translation toggles stay the
user's.
"""

import bpy

from ...core import tabs

META = {
    "label": "Language Switch",
    "description": "Switch the interface language between Japanese and English",
    "tabs": ("Utility",),
}

JA = {
    "Language Switch": "言語切り替え",
    "Language": "言語",
    "Japanese": "日本語",
    "English": "英語",
    "Switch Language": "言語切り替え",
    "Toggle Language": "言語を切り替える",
}


def _is_japanese(context):
    """True when the interface currently shows Japanese."""
    lang = context.preferences.view.language
    if lang == 'DEFAULT':
        return (bpy.app.translations.locale or "").startswith("ja")
    return lang == 'ja_JP'


class WM_OT_sts_switch_language(bpy.types.Operator):
    """Set the interface language. The translation toggles are left as they are"""
    bl_idname = "wm.sts_switch_language"
    bl_label = "Switch Language"
    bl_options = {'REGISTER'}

    language: bpy.props.EnumProperty(
        name="Language",
        description="Interface language to switch to",
        items=(
            ('ja_JP', "Japanese", "Show the interface in Japanese"),
            ('en_US', "English", "Show the interface in English"),
        ),
    )

    def execute(self, context):
        context.preferences.view.language = self.language
        return {'FINISHED'}


class WM_OT_sts_toggle_language(bpy.types.Operator):
    """Switch between Japanese and English"""
    bl_idname = "wm.sts_toggle_language"
    bl_label = "Toggle Language"
    bl_options = {'REGISTER'}

    def execute(self, context):
        context.preferences.view.language = 'en_US' if _is_japanese(context) else 'ja_JP'
        return {'FINISHED'}


class VIEW3D_PT_sts_language_switch(bpy.types.Panel):
    bl_label = "Language"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.UTILITY

    def draw(self, context):
        layout = self.layout
        view = context.preferences.view
        japanese = _is_japanese(context)

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("wm.sts_switch_language", text="Japanese",
                     depress=japanese).language = 'ja_JP'
        row.operator("wm.sts_switch_language", text="English",
                     depress=not japanese).language = 'en_US'
        layout.operator("wm.sts_toggle_language", icon='ARROW_LEFTRIGHT')

        col = layout.column(align=True)
        col.prop(view, "use_translate_interface")
        col.prop(view, "use_translate_tooltips")
        col.prop(view, "use_translate_reports")
        col.prop(view, "use_translate_new_dataname")


classes = (
    WM_OT_sts_switch_language,
    WM_OT_sts_toggle_language,
    VIEW3D_PT_sts_language_switch,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
