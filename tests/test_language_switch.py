"""Functional tests for modules/language_switch. Run through tests/run_tests.sh."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, prefs, run, submodule  # noqa: E402

VIEW = bpy.context.preferences.view
FLAGS = ("use_translate_interface", "use_translate_tooltips",
         "use_translate_reports", "use_translate_new_dataname")


def _save():
    return (VIEW.language,) + tuple(getattr(VIEW, f) for f in FLAGS)


def _restore(state):
    VIEW.language = state[0]
    for f, v in zip(FLAGS, state[1:]):
        setattr(VIEW, f, v)


def test_registered():
    check("module listed in MODULES", "language_switch" in sys.modules[package()].MODULES)
    for name in ("WM_OT_sts_switch_language", "WM_OT_sts_toggle_language",
                 "VIEW3D_PT_sts_language_switch"):
        check(f"{name} registered", hasattr(bpy.types, name))
    tabs = submodule("core.tabs")
    panel = getattr(bpy.types, "VIEW3D_PT_sts_language_switch", None)
    check("panel is in the Utility tab", panel is not None and panel.bl_category == tabs.UTILITY)
    check("META tabs is ('Utility',)", submodule("modules.language_switch").META["tabs"] == ("Utility",))


def test_no_scene_state():
    """Settings live in Blender's preferences, not in the .blend file."""
    p = prefs()
    p.use_language_switch = False
    scene_before = set(bpy.types.Scene.bl_rna.properties.keys())
    wm_before = set(bpy.types.WindowManager.bl_rna.properties.keys())
    p.use_language_switch = True
    check("no Scene property added",
          set(bpy.types.Scene.bl_rna.properties.keys()) == scene_before)
    check("no WindowManager property added",
          set(bpy.types.WindowManager.bl_rna.properties.keys()) == wm_before)
    check("old scene property name not used", not hasattr(bpy.types.Scene, "language_switcher_props"))


def test_no_undo():
    for name in ("WM_OT_sts_switch_language", "WM_OT_sts_toggle_language"):
        cls = getattr(bpy.types, name)
        check(f"{name} has no UNDO (preferences are not undoable)",
              'UNDO' not in getattr(cls, "bl_options", set()))


def test_switch():
    state = _save()
    try:
        VIEW.language = 'en_US'
        r = bpy.ops.wm.sts_switch_language(language='ja_JP')
        check("switch to Japanese", r == {'FINISHED'} and VIEW.language == 'ja_JP', VIEW.language)
        r = bpy.ops.wm.sts_switch_language(language='en_US')
        check("switch to English", r == {'FINISHED'} and VIEW.language == 'en_US', VIEW.language)
        try:
            bpy.ops.wm.sts_switch_language(language='fr_FR')
            check("unknown language rejected", False, "no error")
        except TypeError:
            check("unknown language rejected", True)
    finally:
        _restore(state)


def test_switch_keeps_user_flags():
    """The old add-on overwrote these from its own copies; now they are the user's."""
    state = _save()
    try:
        VIEW.language = 'en_US'
        values = (True, False, False, True)
        for f, v in zip(FLAGS, values):
            setattr(VIEW, f, v)
        bpy.ops.wm.sts_switch_language(language='ja_JP')
        got = tuple(getattr(VIEW, f) for f in FLAGS)
        check("translation flags untouched by switching", got == values, str(got))
    finally:
        _restore(state)


def test_toggle():
    state = _save()
    try:
        VIEW.language = 'en_US'
        r = bpy.ops.wm.sts_toggle_language()
        check("toggle English -> Japanese", r == {'FINISHED'} and VIEW.language == 'ja_JP', VIEW.language)
        bpy.ops.wm.sts_toggle_language()
        check("toggle Japanese -> English", VIEW.language == 'en_US', VIEW.language)
        VIEW.language = 'fr_FR'
        bpy.ops.wm.sts_toggle_language()
        check("toggle from another language -> Japanese", VIEW.language == 'ja_JP', VIEW.language)
    finally:
        _restore(state)


run([
    test_registered,
    test_no_scene_state,
    test_no_undo,
    test_switch,
    test_switch_keeps_user_flags,
    test_toggle,
])
