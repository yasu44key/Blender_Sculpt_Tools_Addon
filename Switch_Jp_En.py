bl_info = {
    "name": "Language Switcher with Toggles",
    "author": "Yoshiki Yasunaga ＆ ChatGPT",
    "version": (1, 1, 0),
    "blender": (3, 6, 0),
    "location": "Preferences > Add-ons > Language Switcher",
    "description": "Switch Blender interface between Japanese and English with toggle options",
    "warning": "",
    "doc_url": "",
    "category": "System",
}

import bpy

# プロパティグループの定義（トグルオプション用）
class LanguageSwitcherProperties(bpy.types.PropertyGroup):
    toggle_interface: bpy.props.BoolProperty(
        name="Interface",
        description="Enable/Disable interface translation",
        default=True,
    )
    toggle_tooltips: bpy.props.BoolProperty(
        name="Tooltips",
        description="Enable/Disable tooltips translation",
        default=True,
    )
    toggle_reports: bpy.props.BoolProperty(
        name="Reports",
        description="Enable/Disable report translation",
        default=True,
    )
    toggle_new_data: bpy.props.BoolProperty(
        name="New Data",
        description="Enable/Disable new data name translation",
        default=False,
    )

# オペレーター: 言語切り替え
class SwitchLanguageOperator(bpy.types.Operator):
    """Switch Blender language between Japanese and English with toggles"""
    bl_idname = "wm.switch_language"
    bl_label = "Switch Language"
    bl_options = {'REGISTER', 'UNDO'}

    language: bpy.props.StringProperty(default="")

    def execute(self, context):
        if self.language not in {"ja_JP", "en_US"}:
            self.report({'ERROR'}, "Unsupported language")
            return {'CANCELLED'}

        # 言語設定を切り替え
        bpy.context.preferences.view.language = self.language
        props = context.scene.language_switcher_props

        bpy.context.preferences.view.use_translate_interface = props.toggle_interface
        bpy.context.preferences.view.use_translate_tooltips = props.toggle_tooltips
        bpy.context.preferences.view.use_translate_new_dataname = props.toggle_new_data

        # ツールチップやレポート翻訳の有効化（レポート翻訳はシステムに依存）
        if hasattr(bpy.context.preferences.view, "use_translate_tooltips"):
            bpy.context.preferences.view.use_translate_tooltips = props.toggle_tooltips
        if hasattr(bpy.context.preferences.view, "use_translate_new_dataname"):
            bpy.context.preferences.view.use_translate_new_dataname = props.toggle_new_data

        self.report(
            {'INFO'},
            f"Language switched to {'Japanese' if self.language == 'ja_JP' else 'English'}"
        )
        return {'FINISHED'}

# UIパネル: 言語切り替え
class LanguageSwitcherPanel(bpy.types.Panel):
    """UI Panel for Language Switching with toggles"""
    bl_label = "Language Switcher"
    bl_idname = "VIEW3D_PT_language_switcher"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sculpt Tools"

    def draw(self, context):
        layout = self.layout
        props = context.scene.language_switcher_props

        layout.label(text="Language Settings:")
        layout.prop(props, "toggle_interface", text="Interface Translation")
        layout.prop(props, "toggle_tooltips", text="Tooltips Translation")
        layout.prop(props, "toggle_reports", text="Report Translation")
        layout.prop(props, "toggle_new_data", text="New Data Translation")

        # 日本語切り替えボタン
        layout.operator(
            SwitchLanguageOperator.bl_idname,
            text="Switch to Japanese"
        ).language = "ja_JP"

        # 英語切り替えボタン
        layout.operator(
            SwitchLanguageOperator.bl_idname,
            text="Switch to English"
        ).language = "en_US"

# 登録と解除
classes = [
    LanguageSwitcherProperties,
    SwitchLanguageOperator,
    LanguageSwitcherPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.language_switcher_props = bpy.props.PointerProperty(type=LanguageSwitcherProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.language_switcher_props

if __name__ == "__main__":
    register()
