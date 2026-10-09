"""GUI test for the Thickness Guard Brush: paint a stroke and finish (kept), paint and Esc (undone),
start from Sculpt Mode (restored).

Run: bash tests/run_gui_tests.sh
"""
import os
import traceback

import bmesh
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


def ev(t, v, x=None, y=None):
    win = bpy.context.window_manager.windows[0]
    if x is None:
        win.event_simulate(type=t, value=v)
    else:
        win.event_simulate(type=t, value=v, x=x, y=y)


def gap(x, y):
    o = state["plate"]
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    near = [p for p in pts if abs(p.x - x) < 0.07 and abs(p.y - y) < 0.07]
    return max(p.z for p in near) - min(p.z for p in near)


def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(2.0, 2.0, 0.05), verts=r["verts"])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=15, use_grid_fill=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Plate")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("Plate", me)
    bpy.context.scene.collection.objects.link(o)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    state["plate"] = o
    win, area, region = war()
    rv3d = region.data
    rv3d.view_perspective = 'ORTHO'
    rv3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 4.0
    s = bpy.context.scene.sts_thickness_brush
    s.min_thickness, s.radius, s.strength = 0.1, 0.3, 1.0


def _invoke():
    win, area, region = war()
    with bpy.context.temp_override(window=win, area=area, region=region):
        return bpy.ops.object.sts_thickness_guard_brush('INVOKE_DEFAULT')


def _stroke():
    pts = [(-0.6 + 1.2 * i / 12, 0.0, 0.025) for i in range(13)]
    x, y = to_screen(pts[0])
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    for p in pts[1:]:
        x, y = to_screen(p)
        ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def s_paint_and_finish():
    r = _invoke()
    check("invoke: running", r == {'RUNNING_MODAL'}, str(r))
    _stroke()
    ev('RET', 'PRESS')
    ev('RET', 'RELEASE')


def s_check_kept():
    check("stroke thickened the plate along the path", gap(0, 0) > 0.09, str(gap(0, 0)))
    check("away from the stroke untouched", abs(gap(0, 0.8) - 0.05) < 1e-6, str(gap(0, 0.8)))
    state["after"] = [v.co.copy() for v in state["plate"].data.vertices]
    s = bpy.context.scene.sts_thickness_brush
    s.min_thickness = 0.2


def s_paint_and_cancel():
    _invoke()
    _stroke()
    ev('ESC', 'PRESS')
    ev('ESC', 'RELEASE')


def s_check_cancelled():
    now = [v.co for v in state["plate"].data.vertices]
    check("Esc: the whole session is undone", all((a - b).length < 1e-7 for a, b in zip(state["after"], now)))
    bpy.ops.object.mode_set(mode='SCULPT')
    r = _invoke()
    check("from Sculpt Mode: runs", r == {'RUNNING_MODAL'}, str(r))
    ev('RET', 'PRESS')
    ev('RET', 'RELEASE')


def s_check_mode():
    check("back in Sculpt Mode afterwards", bpy.context.mode == 'SCULPT', bpy.context.mode)


STEPS = [s_setup, s_paint_and_finish, s_check_kept, s_paint_and_cancel, s_check_cancelled, s_check_mode]


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
