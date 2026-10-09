"""Hidden GUI test for sculpt.sts_face_set_to_mask (click to pick)."""
import os
import traceback

import bpy
import mathutils

OUT = os.environ["STS_GUI_OUT"]
log = []
state = {}


def check(name, cond, detail=""):
    log.append(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail and not cond else ""))


def war():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    return win, area, next(r for r in area.regions if r.type == 'WINDOW')


def press(x, y, k='LEFTMOUSE'):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
    win.event_simulate(type=k, value='PRESS', x=x, y=y)
    win.event_simulate(type=k, value='RELEASE', x=x, y=y)


def mask_right_left():
    obj = bpy.data.objects[state["obj"]]
    me = obj.data
    a = me.attributes.get(".sculpt_mask")
    if a is None:
        return None, None
    vals = [d.value for d in a.data]
    right = [v for v, vert in zip(vals, me.vertices) if vert.co.x > 1e-6]
    left = [v for v, vert in zip(vals, me.vertices) if vert.co.x < -1e-6]
    return right, left


def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=8, y_subdivisions=8, size=8.0)
    obj = bpy.context.object
    state["obj"] = obj.name
    a = obj.data.attributes.new(".sculpt_face_set", 'INT', 'FACE')
    a.data.foreach_set("value", [2 if p.center.x > 0 else 1 for p in obj.data.polygons])
    win, area, region = war()
    area.spaces[0].show_region_ui = True
    rv3d = region.data
    rv3d.view_perspective = 'ORTHO'
    rv3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 12.0
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.object.mode_set(mode='SCULPT')
    bpy.context.scene.sts_face_set_tools.mode = 'REPLACE'


def s_start():
    win, area, region = war()
    with bpy.context.temp_override(window=win, area=area, region=region):
        r = bpy.ops.sculpt.sts_face_set_to_mask('INVOKE_DEFAULT')
    check("invoke waits for a click", r == {'RUNNING_MODAL'}, str(r))


def s_click_sidebar():
    win, area, region = war()
    ui = next(r for r in area.regions if r.type == 'UI')
    press(ui.x + ui.width // 2, ui.y + 8)


def s_after_sidebar():
    right, left = mask_right_left()
    check("click on the sidebar picks nothing", right is None or not any(right), str(right and right[:3]))
    win, area, region = war()
    press(int(region.x + region.width * 0.62), int(region.y + region.height * 0.5))


def s_after_pick():
    right, left = mask_right_left()
    check("click on the right half masks face set 2",
          right is not None and all(v == 1.0 for v in right) and all(v == 0.0 for v in left),
          f"{right and right[:3]} {left and left[:3]}")
    check("back in Sculpt Mode", bpy.context.mode == 'SCULPT', bpy.context.mode)


steps = [s_setup, s_start, s_click_sidebar, s_after_sidebar, s_after_pick]


def tick():
    try:
        if steps:
            steps.pop(0)()
            return 0.6
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
            f.write(f"RESULT {sum(l.startswith('PASS') for l in log)}/{len(log)} passed\n")
    except Exception:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\nEXCEPTION\n" + traceback.format_exc())
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(tick, first_interval=2.0)
