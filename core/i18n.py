"""Japanese UI translation.

UI strings in the code are English. Each module provides a ``JA`` dict
``{"English text": "日本語"}``; they are registered with Blender's own
translation system, so the UI follows Preferences > Interface > Language.
"""

import bpy

_table = {}

# Blender looks up button / operator text in these translation contexts.
_CONTEXTS = ("*", "Operator")


def add(ja):
    _table.update(ja)


def register(package):
    ja = {}
    for msg, text in _table.items():
        for ctx in _CONTEXTS:
            ja[(ctx, msg)] = text
    bpy.app.translations.register(package, {"ja_JP": ja})


def unregister(package):
    bpy.app.translations.unregister(package)
