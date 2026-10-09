"""Tiny test helper for tests that run inside Blender (see run_tests.sh)."""

import importlib
import sys
import traceback

import bpy

_results = []


def package():
    """Full package name of the installed extension (bl_ext.<repo>.sculpt_tools_suite)."""
    for name in bpy.context.preferences.addons.keys():
        if name.endswith("sculpt_tools_suite"):
            return name
    raise RuntimeError("sculpt_tools_suite is not enabled")


def submodule(path):
    return importlib.import_module(package() + "." + path)


def prefs():
    return bpy.context.preferences.addons[package()].preferences


def check(name, cond, detail=""):
    _results.append((name, bool(cond), detail))


def run(tests):
    """Run test functions; each one gets a fresh empty scene."""
    for fn in tests:
        bpy.ops.wm.read_homefile(use_empty=True)
        try:
            fn()
        except Exception:
            check(fn.__name__ + " (exception)", False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    failed = [r for r in _results if not r[1]]
    for name, ok, detail in _results:
        print(("PASS " if ok else "FAIL ") + name + (f"  -- {detail}" if detail and not ok else ""))
    print(f"RESULT {len(_results) - len(failed)}/{len(_results)} passed")
    sys.stdout.flush()
    if failed:
        sys.exit(1)
