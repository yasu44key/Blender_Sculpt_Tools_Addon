"""GUI acceptance test for object.sts_object_brush (event simulation).

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


def ev(t, v, x, y, ctrl=False, shift=False):
    bpy.context.window_manager.windows[0].event_simulate(type=t, value=v, x=x, y=y, ctrl=ctrl, shift=shift)


def drag(a, b, steps=20):
    x0, y0 = to_screen(a)
    x1, y1 = to_screen(b)
    ev('MOUSEMOVE', 'NOTHING', x0, y0)
    ev('LEFTMOUSE', 'PRESS', x0, y0)
    for i in range(1, steps + 1):
        ev('MOUSEMOVE', 'NOTHING', x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps)
    ev('LEFTMOUSE', 'RELEASE', x1, y1)


def placed():
    col = bpy.data.collections.get("Brush_Output")
    return list(col.objects) if col else []


def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_plane_add(size=50.0, location=(0, 0, 0))
    bpy.ops.mesh.primitive_cube_add(size=0.2, location=(8, 8, 5))
    src = bpy.context.object
    src.name = "BrushSource"
    win, area, region = war()
    area.spaces[0].show_region_ui = True
    rv3d = region.data
    rv3d.view_perspective = 'ORTHO'
    rv3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 10.0
    s = bpy.context.scene.sts_object_brush
    s.source = 'OBJECT'
    s.brush_object = src
    s.brush_mode = 'STROKE'
    s.spacing = 0.5
    s.use_pressure = False
    s.align_to_normal = True
    with bpy.context.temp_override(window=win, area=area, region=region):
        r = bpy.ops.object.sts_object_brush('INVOKE_DEFAULT')
    check("invoke starts modal", r == {'RUNNING_MODAL'}, str(r))


def s_stroke1():
    drag((-4.5, -3.0, 0), (-1.0, -3.0, 0))


def s_after1():
    p = placed()
    check("stroke placed several copies", len(p) >= 4, str(len(p)))
    zs = [abs(o.matrix_world.translation.z) for o in p]
    check("copies on the surface (z=0)", p and max(zs) < 1e-3, str(zs[:4]))
    gaps = sorted((p[i + 1].location - p[i].location).length for i in range(len(p) - 1)) if len(p) > 1 else [0]
    check("spacing respected", gaps[0] >= 0.5 - 1e-3, str(gaps[:3]))
    state["n1"] = len(p)
    drag((-4.5, 0.0, 0), (-1.0, 0.0, 0))


def s_after2():
    state["n2"] = len(placed())
    check("second stroke adds more", state["n2"] > state["n1"], f"{state['n1']} -> {state['n2']}")
    x, y = to_screen((-2, 2, 0))
    ev('Z', 'PRESS', x, y, ctrl=True)
    ev('Z', 'RELEASE', x, y, ctrl=True)


def s_after_undo():
    check("Ctrl+Z removes the last stroke", len(placed()) == state["n1"], f"{len(placed())} vs {state['n1']}")
    bpy.context.scene.sts_object_brush.brush_mode = 'GRID'
    bpy.context.scene.sts_object_brush.grid_size = 1.0
    drag((-4.6, 2.3, 0), (-1.4, 2.3, 0))


def s_after_grid():
    new = placed()[state["n1"]:]
    xy_ok = all(abs(o.location.x - round(o.location.x)) < 1e-4 and abs(o.location.y - round(o.location.y)) < 1e-4
                for o in new)
    check("grid stroke placed copies", len(new) >= 2, str(len(new)))
    check("grid: X and Y on the grid", new and xy_ok, str([tuple(round(c, 3) for c in o.location) for o in new][:3]))
    check("grid: height stays on the surface", new and max(abs(o.location.z) for o in new) < 1e-3)
    state["n3"] = len(placed())
    _w, area, _r = war()
    ui = next(r for r in area.regions if r.type == 'UI')
    x, y = ui.x + ui.width // 2, ui.y + 8
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def s_after_sidebar():
    check("click on the sidebar paints nothing", len(placed()) == state["n3"])
    x, y = to_screen((-2, 2, 0))
    ev('ESC', 'PRESS', x, y)
    ev('ESC', 'RELEASE', x, y)


def s_after_esc():
    check("Esc ends the brush and keeps the copies", len(placed()) == state["n3"])
    undone = [o for o in bpy.data.objects if o.users_collection == () and o.name != "BrushSource"]
    check("undone copies are deleted on exit (no orphans)", not undone, str([o.name for o in undone][:3]))


steps = [s_setup, s_stroke1, s_after1, s_after2, s_after_undo, s_after_grid, s_after_sidebar, s_after_esc]


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
