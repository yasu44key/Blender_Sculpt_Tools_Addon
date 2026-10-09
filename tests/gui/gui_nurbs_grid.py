"""GUI acceptance test for surface.sts_nurbs_grid_draw (event simulation).

Run: bash tests/run_gui_tests.sh   (opens a Blender window for ~20 s)
Writes RESULT lines to $STS_GUI_OUT.

The operator is started with the SIDEBAR as context.region (like the panel
button), so mouse positions must be taken from the 3D View's WINDOW region.
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


def sidebar():
    _w, area, _r = war()
    return next(r for r in area.regions if r.type == 'UI')


def ev(t, v, x, y, **mods):
    bpy.context.window_manager.windows[0].event_simulate(type=t, value=v, x=x, y=y, **mods)


def to_screen(co):
    _w, _a, r = war()
    p = location_3d_to_region_2d(r, r.data, mathutils.Vector(co))
    return int(r.x + p.x), int(r.y + p.y)


def click(co, **mods):
    x, y = to_screen(co)
    ev('MOUSEMOVE', 'NOTHING', x, y, **mods)
    ev('LEFTMOUSE', 'PRESS', x, y, **mods)
    ev('LEFTMOUSE', 'RELEASE', x, y, **mods)


def key(k, **mods):
    x, y = to_screen((0, 0, 0))
    ev(k, 'PRESS', x, y, **mods)
    ev(k, 'RELEASE', x, y, **mods)


def surfaces():
    return [o for o in bpy.data.objects if o.type == 'SURFACE']


def start(**settings):
    s = bpy.context.scene.sts_nurbs_grid
    s.u_count = settings.get("u_count", 4)
    s.use_drag = False
    s.snap = settings.get("snap", 'NONE')
    s.weight = 1.0
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    win, area, _region = war()
    with bpy.context.temp_override(window=win, area=area, region=sidebar()):   # like the panel button
        return bpy.ops.surface.sts_nurbs_grid_draw('INVOKE_DEFAULT')


def row(y, z=0.0, n=4):
    return [(-3.0 + i * 1.5, y, z) for i in range(n)]


# ------------------------------------------------------------------ steps

def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_plane_add(size=50.0, location=(0, 0, 0))
    state["plane"] = bpy.context.object
    win, area, region = war()
    area.spaces[0].show_region_ui = True
    rv3d = region.data
    rv3d.view_perspective = 'ORTHO'
    rv3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))   # top view, looking down
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 12.0


def s_draw_two_rows():
    check("start from the sidebar: running", start() == {'RUNNING_MODAL'})
    for co in row(-1.0) + row(1.0):
        click(co)


def s_finish_two_rows():
    key('RET')


def s_check_two_rows():
    ss = surfaces()
    check("enter: one surface made", len(ss) == 1, str(len(ss)))
    if not ss:
        return
    sp = ss[0].data.splines[0]
    check("4 x 2 points", sp.point_count_u == 4 and sp.point_count_v == 2,
          f"{sp.point_count_u} x {sp.point_count_v}")
    want = sorted((x, y) for x, y, _z in row(-1.0) + row(1.0))
    have = sorted((p.co[0], p.co[1]) for p in sp.points)
    off = max(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(have, want))
    check("points where clicked (sidebar start uses the 3D view's coordinates)", off < 0.05,
          f"{off} {have}")
    check("points on the plane surface", all(abs(p.co[2]) < 1e-4 for p in sp.points))
    dg = bpy.context.evaluated_depsgraph_get()
    me = ss[0].evaluated_get(dg).to_mesh()
    nz = sum(p.normal.z * p.area for p in me.polygons)
    ss[0].evaluated_get(dg).to_mesh_clear()
    check("surface faces the viewer (up, seen from above)", nz > 0, str(nz))
    state["count"] = len(surfaces())


def s_sidebar_click_ignored():
    check("start again", start() == {'RUNNING_MODAL'})
    sb = sidebar()
    x, y = sb.x + sb.width // 2, sb.y + sb.height // 2
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)
    for co in row(-1.0, n=4):
        click(co)
    key('BACK_SPACE')          # undo the 4th point
    click(row(-1.0)[3])        # place it again
    for co in row(1.0):
        click(co)


def s_sidebar_finish():
    key('RET')


def s_sidebar_check():
    ss = surfaces()
    check("a click on the sidebar adds no point; Backspace removes one (still 4 x 2)",
          len(ss) == state["count"] + 1 and ss[-1].data.splines[0].point_count_u == 4
          and len(ss[-1].data.splines[0].points) == 8,
          f"{len(ss)} {[len(s.data.splines[0].points) for s in ss]}")
    state["count"] = len(ss)


def s_u_count_and_weight():
    check("start (U 3)", start(u_count=3) == {'RUNNING_MODAL'})
    key('UP_ARROW')            # 3 -> 4 before the first row is done
    x, y = to_screen((0, 0, 0))
    ev('MOUSEMOVE', 'NOTHING', x, y, ctrl=True)
    ev('WHEELUPMOUSE', 'PRESS', x, y, ctrl=True)
    ev('WHEELUPMOUSE', 'PRESS', x, y, ctrl=True)   # weight 1.0 -> 1.2
    ev('MOUSEMOVE', 'NOTHING', x + 1, y)
    for co in row(-1.0):
        click(co)
    key('UP_ARROW')            # ignored: the first row is complete
    for co in row(1.0):
        click(co)


def s_u_finish():
    key('RET')


def s_u_check():
    ss = surfaces()
    ok = len(ss) == state["count"] + 1
    check("U changed before the first row, fixed after it (4 x 2)",
          ok and ss[-1].data.splines[0].point_count_u == 4 and ss[-1].data.splines[0].point_count_v == 2,
          f"{len(ss)} {[(s.data.splines[0].point_count_u, s.data.splines[0].point_count_v) for s in ss]}")
    if ok:
        ws = {round(p.co[3], 3) for p in ss[-1].data.splines[0].points}
        check("Ctrl+wheel sets the weight of the next points (1.2)", ws == {1.2}, str(ws))
    state["count"] = len(ss)


def s_grid_snap():
    bpy.context.scene.cursor.location = (0, 0, 0)
    check("start (grid snap)", start(snap='GRID') == {'RUNNING_MODAL'})
    # keep x <= 1.5: the sidebar covers the right side of the view (clicks there are ignored)
    for co in [(-3.7, -1.2, 0), (-2.1, -0.9, 0), (-0.7, -1.1, 0), (0.8, -0.8, 0),
               (-4.2, 0.8, 0), (-1.9, 1.3, 0), (-0.2, 1.1, 0), (1.1, 0.7, 0)]:
        click(co)


def s_grid_finish():
    key('RET')


def s_grid_check():
    ss = surfaces()
    ok = len(ss) == state["count"] + 1
    step = war()[1].spaces[0].overlay.grid_scale
    cos = [tuple(round(c, 3) for c in p.co[:3]) for p in ss[-1].data.splines[0].points] if ok else []
    on = ok and all(abs(c / step - round(c / step)) < 1e-4 for p in cos for c in p)
    check("grid snap: points on the 3D view's grid", on, f"step {step} {cos}")
    state["count"] = len(ss)


def s_vertex_snap():
    # a raised grid mesh: vertices every 1.0 at z = 0.5; Ctrl+click a little off each vertex
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=3, y_subdivisions=3, size=3.0, location=(-2.0, 0.0, 0.5))
    state["snapgrid"] = bpy.context.object
    bpy.context.view_layer.objects.active = None
    check("start (vertex snap)", start() == {'RUNNING_MODAL'})
    state["want"] = []
    for y in (-0.5, 0.5):
        for x in (-3.5, -2.5, -1.5, -0.5):
            state["want"].append((x, y, 0.5))
            # a little off the vertex, toward the inside of the grid (the ray must hit the grid)
            click((x + (0.12 if x < -2.0 else -0.12), y * 0.8, 0.5), ctrl=True)


def s_vertex_finish():
    key('RET')


def s_vertex_check():
    ss = surfaces()
    ok = len(ss) == state["count"] + 1
    have = sorted(tuple(round(c, 4) for c in p.co[:3]) for p in ss[-1].data.splines[0].points) if ok else []
    check("Ctrl: snaps to the mesh vertices under the mouse", ok and have == sorted(state["want"]), str(have))
    state["count"] = len(ss)
    bpy.data.objects.remove(state["snapgrid"])


def s_cancel():
    check("start (cancel)", start() == {'RUNNING_MODAL'})
    for co in row(-1.0):
        click(co)
    key('ESC')


def s_cancel_check():
    check("Esc: nothing made", len(surfaces()) == state["count"])


STEPS = [s_setup, s_draw_two_rows, s_finish_two_rows, s_check_two_rows,
         s_sidebar_click_ignored, s_sidebar_finish, s_sidebar_check,
         s_u_count_and_weight, s_u_finish, s_u_check,
         s_grid_snap, s_grid_finish, s_grid_check,
         s_vertex_snap, s_vertex_finish, s_vertex_check,
         s_cancel, s_cancel_check]


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
    return 0.4


bpy.app.timers.register(tick, first_interval=2.0)
