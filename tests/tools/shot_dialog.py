import os
import traceback

import bpy

OUT = os.environ["STS_SHOT_DIR"]
state = {"i": 0}


def area3d():
    w = bpy.context.window_manager.windows[0]
    a = next(a for a in w.screen.areas if a.type == 'VIEW_3D')
    return w, a, next(r for r in a.regions if r.type == 'WINDOW')


def setup():
    v = bpy.context.preferences.view
    v.language = 'ja_JP'
    v.use_translate_interface = True
    v.ui_scale = 0.9
    pkg = next(m for m in bpy.context.preferences.addons.keys() if m.endswith("sculpt_tools_suite"))
    ps = [c for c in bpy.types.Panel.__subclasses__() if c.__module__.startswith(pkg)]
    for c in ps:
        if c.bl_category == "Sculpt":
            bpy.utils.unregister_class(c)
            c.bl_category = "Item"
            c.bl_order = -10
            bpy.utils.register_class(c)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    w, a, r = area3d()
    with bpy.context.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(1, 0, 0))
        bpy.ops.object.select_all(action='SELECT')
    a.spaces[0].show_region_ui = True


def shot(name):
    w, a, r = area3d()
    with bpy.context.temp_override(window=w, area=a):
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name))


def _tick():
    i = state["i"]
    state["i"] += 1
    if i == 0:
        setup()
    elif i == 1:
        shot("voxel_panel.png")
    elif i == 2:
        w, a, r = area3d()
        with bpy.context.temp_override(window=w, area=a, region=r):
            bpy.ops.object.sts_voxel_join_remesh('INVOKE_DEFAULT', voxel_size=0.001)
    elif i == 3:
        shot("voxel_dialog.png")
    else:
        bpy.ops.wm.quit_blender()
        return None
    return 1.0


def tick():
    try:
        return _tick()
    except Exception:
        open(os.path.join(OUT, "error.txt"), "w").write(traceback.format_exc())
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=2.0)
