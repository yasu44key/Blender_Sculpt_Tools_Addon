"""GUI acceptance test for mesh.sts_edge_draw (event simulation).

Run: bash tests/run_gui_tests.sh   (opens a Blender window for ~20 s)
Writes RESULT lines to $STS_GUI_OUT.
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


def at(fx, fy):
    _w, _a, r = war()
    return int(r.x + r.width * fx), int(r.y + r.height * fy)


def ev(t, v, x, y):
    bpy.context.window_manager.windows[0].event_simulate(type=t, value=v, x=x, y=y)


def to_screen(co):
    """Window coordinates of a world position (keep points left: the sidebar covers the right)."""
    _w, _a, r = war()
    p = location_3d_to_region_2d(r, r.data, mathutils.Vector(co))
    return int(r.x + p.x), int(r.y + p.y)


def click(co):
    x, y = to_screen(co)
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def key(k):
    x, y = at(0.5, 0.5)
    ev(k, 'PRESS', x, y)
    ev(k, 'RELEASE', x, y)


def new_objects():
    return [o for o in bpy.data.objects if o.name not in state["base"]]


def start(**settings):
    s = bpy.context.scene.sts_edge_creation
    s.target = 'NEW'
    s.depth_mode = settings.get("depth_mode", 'SURFACE')
    s.plane_axis = settings.get("plane_axis", 'XY')
    s.drag_interval = settings.get("drag_interval", 0.5)
    s.fill_on_close = settings.get("fill_on_close", False)
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    win, area, region = war()
    with bpy.context.temp_override(window=win, area=area, region=region):
        return bpy.ops.mesh.sts_edge_draw('INVOKE_DEFAULT')


# ------------------------------------------------------------------ steps

def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_plane_add(size=50.0, location=(0, 0, 0))
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-3.0, 3.0, 1.0))   # a box on the ground
    state["base"] = {o.name for o in bpy.data.objects}
    win, area, region = war()
    area.spaces[0].show_region_ui = True
    rv3d = region.data
    rv3d.view_perspective = 'ORTHO'
    rv3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))   # top view
    rv3d.view_location = (0, 0, 0)
    rv3d.view_distance = 10.0


# 1) click / backspace / navigation / sidebar / C
def a_start():
    r = start()
    check("invoke starts modal", r == {'RUNNING_MODAL'}, str(r))
    click((-3, -2, 0))
    click((-2, -2, 0))
    click((-2, -1, 0))


def a_after_clicks():
    o = new_objects()
    check("3 clicks -> 3 verts", len(o) == 1 and len(o[0].data.vertices) == 3,
          str([len(x.data.vertices) for x in o]))
    if o:
        zs = [abs((o[0].matrix_world @ v.co).z) for v in o[0].data.vertices]
        check("verts snapped onto the ground (z=0)", max(zs) < 1e-3, str(zs))
    key('BACK_SPACE')


def a_after_undo():
    o = new_objects()[0]
    check("Backspace removes last vertex", len(o.data.vertices) == 2)
    x, y = at(0.5, 0.5)
    ev('MIDDLEMOUSE', 'PRESS', x, y)
    ev('MOUSEMOVE', 'NOTHING', x + 40, y)
    ev('MIDDLEMOUSE', 'RELEASE', x + 40, y)
    ev('WHEELUPMOUSE', 'PRESS', x, y)


def a_after_nav():
    o = new_objects()[0]
    check("navigation does not add vertices", len(o.data.vertices) == 2)
    _w, area, _r = war()
    ui = next(r for r in area.regions if r.type == 'UI')
    x, y = ui.x + ui.width // 2, ui.y + 8
    ev('MOUSEMOVE', 'NOTHING', x, y)
    ev('LEFTMOUSE', 'PRESS', x, y)
    ev('LEFTMOUSE', 'RELEASE', x, y)


def a_after_sidebar():
    o = new_objects()[0]
    check("click on the sidebar does not add a vertex", len(o.data.vertices) == 2)
    # restore the view (the middle-mouse drag orbited it)
    _w, _a, region = war()
    region.data.view_rotation = mathutils.Quaternion((1, 0, 0, 0))
    region.data.view_distance = 10.0
    click((-3, -1, 0))
    key('C')


def a_after_close():
    o = new_objects()
    check("C closes loop: 3 verts 3 edges",
          len(o) == 1 and len(o[0].data.vertices) == 3 and len(o[0].data.edges) == 3,
          str([(len(x.data.vertices), len(x.data.edges)) for x in o]))
    check("no face without fill_on_close", len(o) == 1 and len(o[0].data.polygons) == 0)
    check("finished in edit mode", bpy.context.mode == 'EDIT_MESH', bpy.context.mode)
    state["base"] |= {x.name for x in o}


# 2) Esc discards
def b_start():
    start()
    click((-3, 0.5, 0))
    click((-2, 0.5, 0))
    key('ESC')


def b_after_esc():
    check("Esc discards the new object", not new_objects(), str([o.name for o in new_objects()]))
    check("Esc: back in Object Mode", bpy.context.mode == 'OBJECT', bpy.context.mode)


# 3) drag adds points every drag_interval
def c_start():
    start(drag_interval=0.5)
    x0, y0 = to_screen((-4.5, -3.5, 0))
    x1, _ = to_screen((-0.5, -3.5, 0))
    ev('MOUSEMOVE', 'NOTHING', x0, y0)
    ev('LEFTMOUSE', 'PRESS', x0, y0)
    for i in range(1, 21):
        ev('MOUSEMOVE', 'NOTHING', x0 + (x1 - x0) * i // 20, y0)
    ev('LEFTMOUSE', 'RELEASE', x1, y0)


def c_after_drag():
    o = new_objects()
    n = len(o[0].data.vertices) if o else 0
    check("drag adds several points", n >= 4, str(n))
    if o and n >= 2:
        vs = [o[0].matrix_world @ v.co for v in o[0].data.vertices]
        gaps = [(vs[i + 1] - vs[i]).length for i in range(len(vs) - 1)]
        check("drag points at least drag_interval apart", min(gaps) >= 0.5 - 1e-4, str(gaps))
    key('RET')


def c_after_finish():
    o = new_objects()
    check("Enter finishes (object kept)", len(o) == 1 and bpy.context.mode == 'EDIT_MESH',
          f"{len(o)} {bpy.context.mode}")
    state["base"] |= {x.name for x in o}


# 4) PLANE mode ignores surfaces; fill_on_close makes a face
def d_start():
    start(depth_mode='PLANE', plane_axis='XY', fill_on_close=True)
    # the box at (-3, 3) is under these clicks; PLANE must put points at z=0, not on the box top (z=2)
    click((-3.5, 2.5, 0))
    click((-2.5, 2.5, 0))
    click((-2.5, 3.5, 0))
    key('C')


def d_after():
    o = new_objects()
    if not o:
        check("PLANE mode made an object", False)
        return
    zs = [abs((o[0].matrix_world @ v.co).z) for v in o[0].data.vertices]
    check("PLANE XY: points on z=0 even over the box", len(zs) == 3 and max(zs) < 1e-3, str(zs))
    check("fill_on_close: C makes a face", len(o[0].data.polygons) == 1, str(len(o[0].data.polygons)))


steps = [s_setup,
         a_start, a_after_clicks, a_after_undo, a_after_nav, a_after_sidebar, a_after_close,
         b_start, b_after_esc,
         c_start, c_after_drag, c_after_finish,
         d_start, d_after]


def tick():
    try:
        if steps:
            steps.pop(0)()
            return 0.5
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
            f.write(f"RESULT {sum(l.startswith('PASS') for l in log)}/{len(log)} passed\n")
    except Exception:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\nEXCEPTION\n" + traceback.format_exc())
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(tick, first_interval=2.0)
