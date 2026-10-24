"""While drawing a strip: after each pen stroke, even out its points and fit the Target.
(Also: strips saved with an older node group are moved onto the current one on load.)

Curve points in Edit Mode cannot be changed from Python, so a finished stroke (a new Draw
operator in the window manager's history) schedules a timer that steps out to Object Mode,
rebuilds the new spline at Point Spacing, and steps back in. One undo step per stroke follows.
"""

import bpy
from bpy.app.handlers import persistent

from . import points, strip, surface

_last = {"op": None}


def _new_stroke(context):
    ops = context.window_manager.operators
    if not ops or ops[-1].bl_idname != 'CURVE_OT_draw':
        return False
    key = ops[-1].as_pointer()
    if key == _last["op"]:
        return False
    _last["op"] = key
    return True


@persistent
def _on_depsgraph(_scene, _depsgraph):
    context = bpy.context
    if context.mode != 'EDIT_CURVE' or strip.get(context.object) is None:
        return
    if _new_stroke(context) and not bpy.app.timers.is_registered(_after_stroke):
        bpy.app.timers.register(_after_stroke, first_interval=0.0)


def even_last_stroke(context, obj):
    """Object Mode work for the newest stroke (the last spline): drop pen taps, even it, fit Target."""
    s = context.scene.sts_strip_draw
    points.drop_stray(obj.data)
    if s.spacing > 0.0 and len(obj.data.splines):
        last = obj.data.splines[-1]
        if last.type == 'POLY' and len(last.points) > 1:
            pts = points.resample(points.read(last), s.spacing, last.use_cyclic_u)
            points.write(obj.data, last, pts)
    return surface.fit_target(context, obj, strip.get(obj), strip)


def _after_stroke():
    context = bpy.context
    obj = context.object
    if context.mode != 'EDIT_CURVE' or strip.get(obj) is None:
        return None
    bpy.ops.object.mode_set(mode='OBJECT')
    try:
        even_last_stroke(context, obj)
    finally:
        bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.ed.undo_push(message="Even Stroke")
    return None


@persistent
def _on_load(_filepath):
    strip.upgrade_old()


def _upgrade_once():
    try:
        strip.upgrade_old()
    except AttributeError:
        pass        # bpy.data not reachable yet
    return None


def register():
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    bpy.app.timers.register(_upgrade_once, first_interval=0.0)    # the file open when enabling


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if bpy.app.timers.is_registered(_upgrade_once):
        bpy.app.timers.unregister(_upgrade_once)
    if bpy.app.timers.is_registered(_after_stroke):
        bpy.app.timers.unregister(_after_stroke)
