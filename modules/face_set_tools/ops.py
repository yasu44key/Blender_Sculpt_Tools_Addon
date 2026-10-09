"""The Face Set to Mask operator and its scene settings.

Replaces: CFS2.py, FaceToMaskTest43.py (SCULPT_OT_face_set_to_mask*)

Smooth Face Set replaces ★archive/SmoothNomal/smooth_faceset_*.py (which did
not load: a syntax error and a misspelled BVHTree).

FaceSetDeformer_fixed.py is not replaced: its job is what Blender's built-in
Mesh Filter (Smooth / Inflate, mask-aware) already does, so the panel just
links to those.
"""

import bpy

from ...core import view3d
from . import logic

MODE_ITEMS = (
    ('REPLACE', "Replace", "Mask the face set, clear the rest"),
    ('ADD', "Add", "Mask the face set, keep the rest"),
    ('SUBTRACT', "Subtract", "Unmask the face set, keep the rest"),
)

HELP_LINES = (
    "Click a face set",
    "Esc / right-click: cancel",
)


class FaceSetToolsSettings(bpy.types.PropertyGroup):
    """Settings for the next Face Set to Mask call."""

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=MODE_ITEMS,
        default='REPLACE',
    )
    invert: bpy.props.BoolProperty(
        name="Invert", default=False,
        description="Mask everything except the face set",
    )


class _PickFaceSet:
    """Shared by the face-set operators: a face_set number, or click one."""

    @classmethod
    def poll(cls, context):
        return (context.mode == 'SCULPT' and context.active_object is not None
                and context.active_object.type == 'MESH')

    def invoke(self, context, _event):
        if self.face_set > 0:
            return self.execute(context)
        if bpy.app.background or context.area is None:
            self.report({'WARNING'}, "No 3D view to click in: set a Face Set number")
            return {'CANCELLED'}
        self._header(context, True)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _header(self, context, show):
        if context.area:
            context.area.header_text_set("   ".join(HELP_LINES) if show else None)

    def _check(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "No active mesh object")
            return None
        if self.face_set <= 0 or self.face_set not in logic.face_set_ids(obj.data):
            self.report({'WARNING'}, f"No face set {self.face_set} on this mesh")
            return None
        return obj

    def modal(self, context, event):
        if event.value != 'PRESS':
            return {'PASS_THROUGH'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._header(context, False)
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE':
            region = view3d.window_region_under_mouse(context.area, event.mouse_x, event.mouse_y)
            if region is None:
                return {'PASS_THROUGH'}  # over the sidebar / header
            origin, direction = view3d.mouse_ray(region, event.mouse_x, event.mouse_y)
            face_set = logic.face_set_under_ray(context.active_object, origin, direction)
            if face_set is None:
                return {'RUNNING_MODAL'}  # keep waiting
            self.face_set = face_set
            self._header(context, False)
            return self.execute(context)
        return {'PASS_THROUGH'}

    def cancel(self, context):
        self._header(context, False)


class SCULPT_OT_sts_face_set_to_mask(_PickFaceSet, bpy.types.Operator):
    """Mask the vertices of a face set: set its number, or click one in the 3D view"""
    bl_idname = "sculpt.sts_face_set_to_mask"
    bl_label = "Face Set to Mask"
    bl_options = {'REGISTER', 'UNDO'}

    face_set: bpy.props.IntProperty(
        name="Face Set", default=0, min=0,
        description="Face-set number to mask (0 = click one in the 3D view)",
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=MODE_ITEMS,
        default='REPLACE',
    )
    invert: bpy.props.BoolProperty(
        name="Invert", default=False,
        description="Mask everything except the face set",
    )

    def execute(self, context):
        obj = self._check(context)
        if obj is None:
            return {'CANCELLED'}
        # Writing mesh attributes in Sculpt Mode does not always reach the
        # viewport: switch to Object Mode, write, switch back.
        bpy.ops.object.mode_set(mode='OBJECT')
        logic.apply_mask(obj.data, {self.face_set}, mode=self.mode, invert=self.invert)
        bpy.ops.object.mode_set(mode='SCULPT')
        return {'FINISHED'}


class SCULPT_OT_sts_face_set_smooth(_PickFaceSet, bpy.types.Operator):
    """Smooth the shape of one face set: set its number, or click one in the 3D view.
Its outline (shared with other face sets) stays put"""
    bl_idname = "sculpt.sts_face_set_smooth"
    bl_label = "Smooth Face Set"
    bl_options = {'REGISTER', 'UNDO'}

    face_set: bpy.props.IntProperty(
        name="Face Set", default=0, min=0,
        description="Face-set number to smooth (0 = click one in the 3D view)",
    )
    strength: bpy.props.FloatProperty(
        name="Strength", default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    iterations: bpy.props.IntProperty(name="Iterations", default=10, min=1, max=200)
    keep_border: bpy.props.BoolProperty(
        name="Keep Outline", default=True,
        description="Keep the vertices shared with other face sets (and the mesh border)")

    def execute(self, context):
        obj = self._check(context)
        if obj is None:
            return {'CANCELLED'}
        mode = obj.mode
        if mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        logic.smooth_face_set(obj.data, {self.face_set}, self.iterations, self.strength, self.keep_border)
        if mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=mode)
        return {'FINISHED'}


classes = (
    FaceSetToolsSettings,
    SCULPT_OT_sts_face_set_to_mask,
    SCULPT_OT_sts_face_set_smooth,
)
