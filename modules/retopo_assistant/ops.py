"""Retopo Assistant operators: the live Decimate modifier and ridge protection.

The modifier "STS Decimate" holds its own values (the panel edits it directly —
no Scene copy). Decimate collapses the vertex group FIRST, so protecting the
"Ridge" group means invert_vertex_group on, vertex_group_factor 1 (the old
Retopo Assistant left invert off and removed the ridges first). Mesh data is
written in Object Mode; the original mode (Object / Sculpt) is restored.
"""

import math

import bmesh
import bpy

from ...core import sculpt_mask

MOD_NAME = "STS Decimate"
RIDGE_GROUP = "Ridge"


def get_mod(obj):
    return obj.modifiers.get(MOD_NAME)


def ensure_mod(obj):
    """The Decimate modifier, added as COLLAPSE / ratio 0.5 when missing."""
    mod = get_mod(obj)
    if mod is None:
        mod = obj.modifiers.new(MOD_NAME, 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = 0.5
    return mod


def use_ridge(mod):
    """Protect the Ridge group: invert it so its vertices collapse last."""
    mod.vertex_group = RIDGE_GROUP
    mod.invert_vertex_group = True
    mod.vertex_group_factor = 1.0


def _to_object(context):
    """Switch to Object Mode for mesh-data writes; return the mode to restore."""
    prev = context.mode
    if prev != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    return prev


def _restore(context, prev):
    if prev != 'OBJECT':
        bpy.ops.object.mode_set(mode=prev)


def _angle_weights(obj, angle):
    """1 for vertices on edges bent more than `angle` (or on the mesh border), else 0.

    The bend is the angle between the two face normals: 0 for coplanar faces,
    90 deg for a cube edge, near 180 deg for a thin fin folded back on itself.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    weights = [0.0] * len(obj.data.vertices)
    for e in bm.edges:
        # border / non-manifold edges (no single angle) are always ridges
        bend = e.calc_face_angle(math.pi) if len(e.link_faces) == 2 else math.pi
        if bend > angle:
            for v in e.verts:
                weights[v.index] = 1.0
    bm.free()
    return weights


class _MeshActive:
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.mode in {'OBJECT', 'SCULPT'}


class OBJECT_OT_sts_retopo_add_decimate(_MeshActive, bpy.types.Operator):
    """Add the live Decimate modifier "STS Decimate" (Collapse, ratio 0.5) to the
active mesh; pressing again does not add a second one"""
    bl_idname = "object.sts_retopo_add_decimate"
    bl_label = "Add Decimate"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        prev = _to_object(context)
        ensure_mod(obj)
        _restore(context, prev)
        return {'FINISHED'}


class OBJECT_OT_sts_retopo_ridge_from_mask(_MeshActive, bpy.types.Operator):
    """Copy the sculpt mask into the vertex group "Ridge" (weights = mask) and let
"STS Decimate" protect it; the modifier is added when missing"""
    bl_idname = "object.sts_retopo_ridge_from_mask"
    bl_label = "Ridge from Mask"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        prev = _to_object(context)
        values = sculpt_mask.mask_values(obj.data)
        if values is None or not any(values):
            _restore(context, prev)
            self.report({'WARNING'}, "This mesh has no sculpt mask")
            return {'CANCELLED'}
        sculpt_mask.values_to_group(obj, RIDGE_GROUP, values)
        use_ridge(ensure_mod(obj))
        _restore(context, prev)
        return {'FINISHED'}


class OBJECT_OT_sts_retopo_ridge_from_angle(_MeshActive, bpy.types.Operator):
    """Vertices on edges bent more than the angle (or on the mesh border) get
weight 1 in the vertex group "Ridge", others 0; "STS Decimate" protects it"""
    bl_idname = "object.sts_retopo_ridge_from_angle"
    bl_label = "Ridge from Angle"
    bl_options = {'REGISTER', 'UNDO'}

    angle: bpy.props.FloatProperty(
        name="Angle", subtype='ANGLE', default=math.radians(30.0),
        min=0.0, max=math.pi,
        description="Edges bent more than this are ridges",
    )

    def execute(self, context):
        obj = context.active_object
        prev = _to_object(context)
        sculpt_mask.values_to_group(obj, RIDGE_GROUP, _angle_weights(obj, self.angle))
        use_ridge(ensure_mod(obj))
        _restore(context, prev)
        return {'FINISHED'}


class OBJECT_OT_sts_retopo_apply(_MeshActive, bpy.types.Operator):
    """Apply "STS Decimate" to the mesh (the Ridge group stays)"""
    bl_idname = "object.sts_retopo_apply"
    bl_label = "Apply Decimate"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if get_mod(obj) is None:
            self.report({'WARNING'}, "No decimate modifier on this mesh")
            return {'CANCELLED'}
        prev = _to_object(context)
        bpy.ops.object.modifier_apply(modifier=MOD_NAME)
        _restore(context, prev)
        return {'FINISHED'}


class OBJECT_OT_sts_retopo_remove(_MeshActive, bpy.types.Operator):
    """Remove "STS Decimate" from the mesh (the Ridge group stays)"""
    bl_idname = "object.sts_retopo_remove"
    bl_label = "Remove Decimate"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        mod = get_mod(obj)
        if mod is None:
            self.report({'WARNING'}, "No decimate modifier on this mesh")
            return {'CANCELLED'}
        prev = _to_object(context)
        obj.modifiers.remove(mod)
        _restore(context, prev)
        return {'FINISHED'}


classes = (
    OBJECT_OT_sts_retopo_add_decimate,
    OBJECT_OT_sts_retopo_ridge_from_mask,
    OBJECT_OT_sts_retopo_ridge_from_angle,
    OBJECT_OT_sts_retopo_apply,
    OBJECT_OT_sts_retopo_remove,
)
