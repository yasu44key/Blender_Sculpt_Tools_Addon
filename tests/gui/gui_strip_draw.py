"""GUI test for strip_draw: start a strip, drag a stroke with Blender's curve Draw tool, finish.

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
    _w, _a, r = war()
    p = location_3d_to_region_2d(r, r.data, mathutils.Vector(co))
    return int(r.x + p.x), int(r.y + p.y)


def ev(t, v, x, y):
    bpy.context.window_manager.windows[0].event_simulate(type=t, value=v, x=x, y=y)


def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
    state["sphere"] = bpy.context.object
    win, area, region = war()
    rv3d = region.data
    rv3d.view_perspective = 'ORTHO'
    rv3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 4.0
    s = bpy.context.scene.sts_strip_draw
    s.target = None
    s.width, s.offset, s.thickness, s.style = 0.1, 0.0, 0.0, 'RIBBON'
    with bpy.context.temp_override(window=win, area=area, region=region):
        r = bpy.ops.curve.sts_strip_start()
    check("start: finished, Edit Mode, Draw tool", r == {'FINISHED'} and bpy.context.mode == 'EDIT_CURVE', str(r))


def s_draw():
    pts = [(-0.6 + 1.2 * i / 20, 0.0, 1.0) for i in range(21)]
    x, y = to_screen(pts[0])
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    for p in pts[1:]:
        x, y = to_screen(p)
        ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def s_finish():
    win, area, region = war()
    with bpy.context.temp_override(window=win, area=area, region=region):
        r = bpy.ops.curve.sts_strip_finish()
    check("finish: back to Object Mode", r == {'FINISHED'} and bpy.context.mode == 'OBJECT', str(r))


def s_check():
    strips = [o for o in bpy.data.objects if o.type == 'CURVE']
    check("one strip with a drawn stroke", len(strips) == 1 and len(strips[0].data.splines) == 1,
          str([(o.name, len(o.data.splines)) for o in strips]))
    if not strips:
        return
    o = strips[0]
    dg = bpy.context.evaluated_depsgraph_get()
    ev_ = o.evaluated_get(dg)
    me = ev_.to_mesh()
    rr = [(o.matrix_world @ v.co).length for v in me.vertices]
    ev_.to_mesh_clear()
    check("the band lies on the sphere (drawn on the surface)", rr and all(abs(r - 1.0) < 0.02 for r in rr),
          f"{min(rr) if rr else None}..{max(rr) if rr else None}")


STEPS = [s_setup, s_draw, s_finish, s_check]


def tick():
    i = state.get("i", 0)
    if i >= len(STEPS):
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
            f.write(f"RESULT {sum(1 for l in log if l.startswith('PASS'))}/{len(log)}\n")
        bpy.ops.wm.quit_blender()
        return None
    try:
        STEPS[i]()
    except Exception:
        log.append("FAIL EXCEPTION in " + STEPS[i].__name__ + ": " + traceback.format_exc().splitlines()[-1])
    state["i"] = i + 1
    return 0.6


bpy.app.timers.register(tick, first_interval=2.0)
