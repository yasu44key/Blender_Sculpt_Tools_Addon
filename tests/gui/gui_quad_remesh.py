"""GUI test for quad_remesh: the modal path (background worker, progress, cancel) that the
headless tests cannot reach because they run with blocking=True.

  run -> RUNNING_MODAL, the job is visible to the panel, Blender stays responsive, result made
  Cancel button -> worker killed, nothing made;  Esc -> same

Run: bash tests/run_gui_tests.sh   (needs QRemeshify installed in the normal 5.2 profile)
"""
import os
import time
import traceback

import bpy

OUT = os.environ["STS_GUI_OUT"]
ENGINE = os.path.join(os.environ.get("APPDATA", ""),
                      r"Blender Foundation\Blender\5.2\extensions\user_default\qremeshify\lib")
os.environ["STS_QUADWILD_DIR"] = ENGINE
log = []
state = {}


def check(name, cond, detail=""):
    log.append(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail and not cond else ""))


def ops_mod():
    import importlib
    pkg = next(n for n in bpy.context.preferences.addons.keys() if n.endswith("sculpt_tools_suite"))
    return importlib.import_module(pkg + ".modules.quad_remesh.ops")


def wa():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    return win, area, next(r for r in area.regions if r.type == 'WINDOW')


def egg():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32)
    o = bpy.context.object
    o.name = "Egg"
    for v in o.data.vertices:
        v.co.z *= 1.5
    return o


def start(target):
    win, area, reg = wa()
    with bpy.context.temp_override(window=win, area=area, region=reg):
        return bpy.ops.object.sts_quad_remesh('EXEC_DEFAULT', target_faces=target)


def s_setup():
    check("engine present", os.path.isfile(os.path.join(ENGINE, "lib_quadwild.dll")), ENGINE)
    state["egg"] = egg()
    wa()[1].spaces[0].show_region_ui = True


def s_start():
    state["t0"] = time.time()
    r = start(1200)
    check("run: RUNNING_MODAL (not blocking)", r == {'RUNNING_MODAL'}, str(r))
    check("run: job visible to the panel", ops_mod().running())
    state["ticks"] = 0


def s_wait():
    state["ticks"] += 1     # this callback running at all = the UI is not frozen
    if ops_mod().running() and time.time() - state["t0"] < 60:
        return STEPS.index(s_wait)
    q = bpy.data.objects.get("Egg_Quad")
    check("run: result made", q is not None)
    check("run: UI kept ticking while the worker ran", state["ticks"] >= 3, str(state["ticks"]))
    if q is not None:
        check("run: all quads", all(len(p.vertices) == 4 for p in q.data.polygons))
        bpy.data.objects.remove(q)


def s_cancel_start():
    bpy.context.view_layer.objects.active = state["egg"]
    state["egg"].select_set(True)
    r = start(20000)
    check("cancel run started", r == {'RUNNING_MODAL'}, str(r))
    state["job"] = ops_mod().RUN["job"]


def s_cancel_press():
    win, area, reg = wa()
    with bpy.context.temp_override(window=win, area=area, region=reg):
        r = bpy.ops.object.sts_quad_cancel()
    check("cancel button: FINISHED", r == {'FINISHED'})


def s_cancel_check():
    job = state["job"]
    check("cancel button: worker killed", job.proc.poll() is not None)
    check("cancel button: nothing made", bpy.data.objects.get("Egg_Quad") is None)
    check("cancel button: job cleared", not ops_mod().running())


def s_esc_start():
    bpy.context.view_layer.objects.active = state["egg"]
    r = start(20000)
    check("esc run started", r == {'RUNNING_MODAL'}, str(r))
    state["job"] = ops_mod().RUN["job"]


def s_esc_press():
    win, area, reg = wa()
    x, y = area.x + area.width // 2, area.y + area.height // 2
    win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
    win.event_simulate(type='ESC', value='PRESS', x=x, y=y)
    win.event_simulate(type='ESC', value='RELEASE', x=x, y=y)


def s_esc_check():
    job = state["job"]
    check("esc: worker killed", job.proc.poll() is not None)
    check("esc: nothing made", bpy.data.objects.get("Egg_Quad") is None)
    check("esc: job cleared", not ops_mod().running())


def s_draw_tools():
    win, area, reg = wa()
    with bpy.context.temp_override(window=win, area=area, region=reg):
        r1 = bpy.ops.object.sts_quad_draw_guides(erase=False)
        tool1 = bpy.context.workspace.tools.from_space_view3d_mode('OBJECT').idname
        r2 = bpy.ops.object.sts_quad_draw_guides(erase=True)
        tool2 = bpy.context.workspace.tools.from_space_view3d_mode('OBJECT').idname
    ann = bpy.context.scene.annotation
    check("draw: annotate tool, layer STS Guide active, placed on the surface",
          r1 == {'FINISHED'} and tool1 == "builtin.annotate" and ann is not None
          and ann.layers[ann.layers.active_index].info == "STS Guide"
          and bpy.context.scene.tool_settings.annotation_stroke_placement_view3d == 'SURFACE', f"{r1} {tool1}")
    check("erase: annotation eraser", r2 == {'FINISHED'} and tool2 == "builtin.annotate_eraser", f"{r2} {tool2}")
    with bpy.context.temp_override(window=win, area=area, region=reg):
        bpy.ops.wm.tool_set_by_id(name="builtin.select_box")


STEPS = [s_setup, s_draw_tools, s_start, s_wait, s_cancel_start, s_cancel_press, s_cancel_check,
         s_esc_start, s_esc_press, s_esc_check]


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
            return 0.5
    except Exception:
        log.append("FAIL EXCEPTION in " + STEPS[i].__name__ + ": " + traceback.format_exc().splitlines()[-1])
    state["i"] = i + 1
    return 0.8


bpy.app.timers.register(tick, first_interval=2.0)
