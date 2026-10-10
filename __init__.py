"""Sculpt Tools Suite — a collection of sculpt / modeling tools.

Each tool lives in ``modules/<name>/`` and can be switched on or off
individually from Preferences > Add-ons > Sculpt Tools Suite.
"""

import importlib

import bpy

from bpy.app.translations import pgettext_iface as iface

from .core import i18n, tabs

JA = {
    "Modules (unchecked modules are not loaded)": "モジュール（チェックを外したものは読み込まれません）",
}

# Order here = order in the preferences list.
MODULES = (
    "bezier_draw",
    "language_switch",
    "edge_creation",
    "voxel_remesh",
    "face_set_tools",
    "mesh_tools",
    "metaball_brush",
    "object_brush",
    "sujibori",
    "align_tools",
    "tessellation",
    "shapes",
    "wave_surface",
    "smooth_normals",
    "wear",
    "panel_raise",
    "annotation_convert",
    "nurbs_grid",
    "point_smooth",
    "strip_draw",
    "quick_buttons",
    "mesh_generators",
    "thickness_guard",
    "retopo_assistant",
    "quad_remesh",
)

_loaded = {}     # name -> imported module
_active = set()  # names of currently registered modules


def _module(name):
    if name not in _loaded:
        _loaded[name] = importlib.import_module(f".modules.{name}", __package__)
    return _loaded[name]


def enable_module(name):
    if name in _active:
        return
    _module(name).register()
    _active.add(name)


def disable_module(name):
    if name not in _active:
        return
    _module(name).unregister()
    _active.discard(name)


def _toggle_update(name):
    def update(self, _context):
        if getattr(self, "use_" + name):
            enable_module(name)
        else:
            disable_module(name)
    return update


class STS_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, _context):
        layout = self.layout
        layout.label(text="Modules (unchecked modules are not loaded)")
        col = layout.column(align=True)
        for name in MODULES:
            meta = _module(name).META
            row = col.row(align=True)
            row.prop(self, "use_" + name, text=meta["label"])
            sub = row.row()
            sub.alignment = 'RIGHT'
            sub.label(text=" / ".join(iface(t) for t in meta["tabs"]), icon='WINDOW', translate=False)


# One enable/disable checkbox per module, generated from each module's META.
for _name in MODULES:
    _meta = _module(_name).META
    STS_AddonPreferences.__annotations__["use_" + _name] = bpy.props.BoolProperty(
        name=_meta["label"],
        description=_meta["description"],
        default=_meta.get("default", True),
        update=_toggle_update(_name),
    )


def _prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def register():
    bpy.utils.register_class(STS_AddonPreferences)
    i18n.add(JA)
    i18n.add(tabs.JA)
    for name in MODULES:
        i18n.add(_module(name).JA)
    i18n.register(__package__)

    prefs = _prefs()
    for name in MODULES:
        if prefs is None or getattr(prefs, "use_" + name):
            enable_module(name)


def unregister():
    for name in reversed(MODULES):
        disable_module(name)
    i18n.unregister(__package__)
    bpy.utils.unregister_class(STS_AddonPreferences)
