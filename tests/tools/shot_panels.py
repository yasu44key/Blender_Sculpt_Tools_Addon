"""GUI screenshot of the add-on panels (run with an isolated user folder)."""
import os
import traceback

import bpy

OUT = os.environ["STS_SHOT_DIR"]
SHOTS = [("OBJECT", "Utility", "en_US"), ("OBJECT", "Utility", "ja_JP")]
state = {"i": 0, "phase": 0}


def area3d():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a
    raise RuntimeError("no 3D view")


def our_panels():
    pkg = next(m for m in bpy.context.preferences.addons.keys() if m.endswith("sculpt_tools_suite"))
    ps = [c for c in bpy.types.Panel.__subclasses__() if c.__module__.startswith(pkg)]
    ps.sort(key=lambda c: bool(getattr(c, "bl_parent_id", "")))
    return ps


def move_panels_to_item(tab):
    """The active N-panel tab cannot be set from Python, so for the
    screenshot the panels of `tab` are re-registered under 'Item'."""
    ps = our_panels()
    for c in reversed(ps):
        bpy.utils.unregister_class(c)
    for c in ps:
        if not hasattr(c, "_orig_cat"):
            c._orig_cat = c.bl_category
        c.bl_category = "Item" if c._orig_cat == tab else c._orig_cat
        c.bl_order = -10
        bpy.utils.register_class(c)


def setup(mode, tab, lang):
    w, a = area3d()
    view = bpy.context.preferences.view
    view.language = lang
    view.use_translate_interface = True
    view.ui_scale = 0.8
    with bpy.context.temp_override(window=w, area=a):
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        if True:
            bpy.ops.curve.sts_lissajous_add()
            if mode == 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
    move_panels_to_item(tab)
    a.spaces[0].show_region_ui = True
    a.tag_redraw()


def _tick():
    i = state["i"]
    if i >= len(SHOTS):
        bpy.ops.wm.quit_blender()
        return None
    if state["phase"] == 0:
        setup(*SHOTS[i])
        state["phase"] = 1
        return 1.0
    w, a = area3d()
    with bpy.context.temp_override(window=w, area=a):
        bpy.ops.screen.screenshot_area(
            filepath=os.path.join(OUT, f"shot{i}_{'_'.join(SHOTS[i])}.png"))
    state["i"] += 1
    state["phase"] = 0
    return 0.3


def tick():
    try:
        return _tick()
    except Exception:
        with open(os.path.join(OUT, "error.txt"), "w") as f:
            f.write(traceback.format_exc())
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=2.0)
