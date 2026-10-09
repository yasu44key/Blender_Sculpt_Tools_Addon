"""GUI acceptance test for object.sts_metaball_brush (event simulation).

Run: bash tests/run_gui_tests.sh
"""
import os
import traceback

import bpy
import mathutils
from bpy_extras.view3d_utils import location_3d_to_region_2d

OUT = os.environ["STS_GUI_OUT"]
log = []
state = {}


def check(name, cond, detail=""):
    log.append(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail and not cond else ""))


def war():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    return win, area, next(r for r in area.regions if r.type == 'WINDOW')


def to_screen(co):
    """Window coordinates of a world position (keep points left: the sidebar covers the right)."""
    _w, _a, r = war()
    p = location_3d_to_region_2d(r, r.data, mathutils.Vector(co))
    return int(r.x + p.x), int(r.y + p.y)


def ev(t, v, x, y):
    bpy.context.window_manager.windows[0].event_simulate(type=t, value=v, x=x, y=y)


def strokes():
    return [o for o in bpy.data.objects if o.type == 'META']


def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_plane_add(size=50.0, location=(0, 0, 0))
    win, area, region = war()
    area.spaces[0].show_region_ui = True
    rv3d = region.data
    rv3d.view_perspective = 'ORTHO'
    rv3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 10.0
    bpy.context.scene.cursor.location = (0, 0, 0)
    s = bpy.context.scene.sts_metaball_brush
    s.depth_mode = 'SURFACE'
    s.placement_mode = 'DISTANCE'
    s.distance_px = 20.0
    s.min_size = 0.2
    s.max_size = 0.2
    with bpy.context.temp_override(window=win, area=area, region=region):
        r = bpy.ops.object.sts_metaball_brush('INVOKE_DEFAULT')
    check("invoke starts modal", r == {'RUNNING_MODAL'}, str(r))


def s_drag():
    x0, y0 = to_screen((-4.0, -2.0, 0))
    x1, _ = to_screen((-1.0, -2.0, 0))
    ev('MOUSEMOVE', 'NOTHING', x0, y0)
    ev('LEFTMOUSE', 'PRESS', x0, y0)
    for i in range(1, 21):
        ev('MOUSEMOVE', 'NOTHING', x0 + (x1 - x0) * i // 20, y0)
    ev('LEFTMOUSE', 'RELEASE', x1, y0)


def s_after_drag():
    st = strokes()
    check("one stroke object", len(st) == 1, str(len(st)))
    if st:
        n = len(st[0].data.elements)
        check("drag placed several balls", n >= 4, str(n))
        zs = [abs((st[0].matrix_world @ e.co).z) for e in st[0].data.elements]
        check("balls on the surface (z=0)", max(zs) < 1e-3, str(zs[:4]))
    # quick click in TIME mode: the first ball must be placed at once
    bpy.context.scene.sts_metaball_brush.placement_mode = 'TIME'
    bpy.context.scene.sts_metaball_brush.interval = 1.0
    x, y = to_screen((-3.0, 2.0, 0))
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def s_after_quick_click():
    st = strokes()
    check("second stroke = second object", len(st) == 2, str(len(st)))
    check("no empty stroke objects", all(len(o.data.elements) > 0 for o in st),
          str([len(o.data.elements) for o in st]))
    _w, area, _r = war()
    ui = next(r for r in area.regions if r.type == 'UI')
    x, y = ui.x + ui.width // 2, ui.y + 8
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def s_after_sidebar():
    check("click on the sidebar starts no stroke", len(strokes()) == 2, str(len(strokes())))
    x, y = to_screen((-2.0, 0.0, 0))
    ev('ESC', 'PRESS', x, y)
    ev('ESC', 'RELEASE', x, y)


def s_after_esc():
    check("Esc ends the brush and keeps the strokes", len(strokes()) == 2, str(len(strokes())))
    x, y = to_screen((-2.0, 3.0, 0))
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def s_after_end():
    check("after Esc, clicks no longer paint", len(strokes()) == 2, str(len(strokes())))


steps = [s_setup, s_drag, s_after_drag, s_after_quick_click, s_after_sidebar, s_after_esc, s_after_end]


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
