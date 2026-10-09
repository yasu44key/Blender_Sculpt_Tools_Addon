"""Checks every module must pass (docs/CONVENTIONS.md). Run through tests/run_tests.sh."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, prefs, run, submodule  # noqa: E402


def _modules():
    return sys.modules[package()].MODULES


def _classes_of(name, base):
    prefix = f"{package()}.modules.{name}"
    return [c for c in base.__subclasses__() if c.__module__.startswith(prefix)]


def test_meta():
    for name in _modules():
        mod = submodule("modules." + name)
        meta = getattr(mod, "META", {})
        check(f"[{name}] META has label/description/tabs",
              all(k in meta for k in ("label", "description", "tabs")), str(meta))
        check(f"[{name}] has JA dict", isinstance(getattr(mod, "JA", None), dict))


def test_toggle_each_module():
    p = prefs()
    for name in _modules():
        ops = _classes_of(name, bpy.types.Operator)
        panels = _classes_of(name, bpy.types.Panel)
        names = [c.__name__ for c in ops + panels]
        check(f"[{name}] registers operators or panels", names, "none found")
        setattr(p, "use_" + name, False)
        left = [n for n in names if hasattr(bpy.types, n)]
        check(f"[{name}] toggle off unregisters everything", not left, str(left))
        setattr(p, "use_" + name, True)
        missing = [n for n in names if not hasattr(bpy.types, n)]
        check(f"[{name}] toggle on registers again", not missing, str(missing))


def test_naming():
    for name in _modules():
        for c in _classes_of(name, bpy.types.Operator):
            idname = c.bl_idname
            check(f"[{name}] operator idname uses sts_ ({idname})",
                  "." in idname and idname.split(".", 1)[1].startswith("sts_"))
        for c in _classes_of(name, bpy.types.Panel):
            check(f"[{name}] panel class name VIEW3D_PT_sts_* ({c.__name__})",
                  c.__name__.startswith("VIEW3D_PT_sts_") or c.__name__.startswith("PROPERTIES_PT_sts_"))


def test_panel_tabs():
    tabs = submodule("core.tabs")
    allowed = {v for k, v in vars(tabs).items() if k.isupper() and isinstance(v, str)}
    for name in _modules():
        meta_tabs = set(submodule("modules." + name).META["tabs"])
        for c in _classes_of(name, bpy.types.Panel):
            cat = getattr(c, "bl_category", None)
            check(f"[{name}] {c.__name__} tab from core/tabs.py", cat in allowed, str(cat))
            check(f"[{name}] {c.__name__} tab listed in META", cat in meta_tabs, str(cat))


def test_translation():
    """Every JA entry must actually show. Blender's own dictionary wins over
    add-on entries, so a colliding English text must be reworded (or the
    entry dropped when Blender's translation is fine)."""
    view = bpy.context.preferences.view
    old = (view.language, view.use_translate_interface)
    try:
        view.language = 'ja_JP'
        view.use_translate_interface = True
        tab_ja = submodule("core.tabs").JA
        bad = [f"{m!r} -> {bpy.app.translations.pgettext_iface(m)!r}" for m, t in tab_ja.items()
               if bpy.app.translations.pgettext_iface(m) != t]
        check("[core] tab JA entries take effect", not bad, "; ".join(bad))
        for name in _modules():
            ja = submodule("modules." + name).JA
            op_labels = {c.bl_label for c in _classes_of(name, bpy.types.Operator)}
            bad = []
            for msg, text in ja.items():
                ctx = "Operator" if msg in op_labels else "*"
                got = bpy.app.translations.pgettext_iface(msg, ctx)
                if got != text:
                    bad.append(f"{msg!r} -> {got!r} (want {text!r})")
            check(f"[{name}] all JA entries take effect", not bad, "; ".join(bad))
    finally:
        view.language, view.use_translate_interface = old


def test_icons():
    """Every icon='...' in a module exists in this Blender (a bad name breaks the whole panel draw)."""
    import re
    known = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())
    root = os.path.dirname(submodule("modules").__file__)
    for name in _modules():
        bad = set()
        for dirpath, _dirs, files in os.walk(os.path.join(root, name)):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                        bad |= set(re.findall(r"icon\s*=\s*'([A-Z0-9_]+)'", fh.read())) - known
        check(f"[{name}] icon names exist", not bad, ", ".join(sorted(bad)))


run([
    test_meta,
    test_toggle_each_module,
    test_naming,
    test_panel_tabs,
    test_translation,
    test_icons,
])
