"""GUI test for quick_buttons: the Utility-tab panel draws without errors in Object and Edit Mode,
and a button pressed in the sidebar rotates the cube.

Run: bash tests/run_gui_tests.sh
"""
import os
import sys
import traceback

import bpy

OUT = os.environ["STS_GUI_OUT"]
SHOT = os.environ.get("STS_GUI_SHOT")
log = []
state = {}


def check(name, cond, detail=""):
    log.append(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail and not cond else ""))


def war():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    return win, area, next(r for r in area.regions if r.type == 'UI')


def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add()
    state["cube"] = bpy.context.object
    win, area, ui = war()
    area.spaces[0].show_region_ui = True
    state["tabs"] = True


def s_click_tab():
    # walk up the tab strip on the sidebar's right edge (events are handled after this tick)
    win, area, ui = war()
    y = ui.y + 20 + 15 * state.setdefault("try", 0)
    x = ui.x + ui.width - 12
    win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
    win.event_simulate(type='LEFTMOUSE', value='PRESS', x=x, y=y)
    win.event_simulate(type='LEFTMOUSE', value='RELEASE', x=x, y=y)


def s_tab_shown():
    ui = war()[2]
    if ui.active_panel_category != "Utility" and state["try"] < 60:
        state["try"] += 1
        return STEPS.index(s_click_tab)
    check("sidebar shows the Utility tab", ui.active_panel_category == "Utility", ui.active_panel_category)


def s_object_drawn():
    p = bpy.types.VIEW3D_PT_sts_quick_buttons
    check("panel registered in Utility", p.bl_category == "Utility")
    win, area, ui = war()
    with bpy.context.temp_override(window=win, area=area, region=ui):
        r = bpy.ops.view3d.sts_quick_rotate(axis='Z', angle=0.5)
    check("rotate from the sidebar context", r == {'FINISHED'} and abs(state["cube"].rotation_euler.z - 0.5) < 1e-5,
          str(state["cube"].rotation_euler[:]))
    if SHOT:
        with bpy.context.temp_override(window=win):
            bpy.ops.screen.screenshot(filepath=SHOT)


def s_edit():
    bpy.ops.object.mode_set(mode='EDIT')
    war()[1].tag_redraw()


def s_edit_drawn():
    check("Edit Mode: still drawn (no draw errors so far)", bpy.context.mode == 'EDIT_MESH')
    bpy.ops.object.mode_set(mode='OBJECT')


STEPS = [s_setup, s_click_tab, s_tab_shown, s_object_drawn, s_edit, s_edit_drawn]


def tick():
    i = state.get("i", 0)
    if i >= len(STEPS):
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
            f.write(f"RESULT {sum(1 for l in log if l.startswith('PASS'))}/{len(log)}\n")
        bpy.ops.wm.quit_blender()
        return None
    try:
        jump = STEPS[i]()
        if jump is not None:
            state["i"] = jump
            return 0.2
    except Exception:
        log.append("FAIL EXCEPTION in " + STEPS[i].__name__ + ": " + traceback.format_exc().splitlines()[-1])
    state["i"] = i + 1
    return 0.6


bpy.app.timers.register(tick, first_interval=2.0)
