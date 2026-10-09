"""GUI check for voxel_remesh in Sculpt Mode with Dyntopo (sculpt operators crash in background).

Run: bash tests/run_gui_tests.sh   (opens a Blender window for a few seconds)
"""
import os
import traceback

import bpy

OUT = os.environ["STS_GUI_OUT"]
log = []
state = {}


def check(name, cond, detail=""):
    log.append(("PASS " if cond else "FAIL ") + name + (f"  -- {detail}" if detail and not cond else ""))


def ctx():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return dict(window=win, area=area, region=region)


def s_setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=16, ring_count=8)
    o = bpy.context.object
    o.data.remesh_voxel_size = 0.08
    state["obj"] = o
    state["verts"] = len(o.data.vertices)
    with bpy.context.temp_override(**ctx()):
        bpy.ops.object.mode_set(mode='SCULPT')
        bpy.ops.sculpt.dynamic_topology_toggle()
    check("Dyntopo on before", o.use_dynamic_topology_sculpting)


def s_remesh():
    with bpy.context.temp_override(**ctx()):
        r = bpy.ops.object.sts_voxel_apply_remesh()
    check("apply remesh in Sculpt Mode: finished", r == {'FINISHED'}, str(r))


def s_check():
    o = state["obj"]
    check("still in Sculpt Mode", o.mode == 'SCULPT', o.mode)
    check("Dyntopo back on", o.use_dynamic_topology_sculpting)
    with bpy.context.temp_override(**ctx()):
        bpy.ops.sculpt.dynamic_topology_toggle()
        bpy.ops.object.mode_set(mode='OBJECT')
    n = len(o.data.vertices)
    check("the mesh was remeshed (vertex count changed, no Dyntopo leftover)", n != state["verts"] and n > 500,
          f"{state['verts']} -> {n}")


STEPS = [s_setup, s_remesh, s_check]


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
    return 0.5


bpy.app.timers.register(tick, first_interval=2.0)
