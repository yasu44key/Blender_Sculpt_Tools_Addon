"""Smooth Normals operators: put the live modifier on meshes / take it off."""

import bpy

from . import normals


def _meshes(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


class OBJECT_OT_sts_smooth_normals_add(bpy.types.Operator):
    """Smooth the shading normals of the selected meshes where the active vertex group is painted
(the whole mesh if there is no group). The shape does not change"""
    bl_idname = "object.sts_smooth_normals_add"
    bl_label = "Add Smooth Normals"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        objs = _meshes(context)
        if not objs:
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}
        for o in objs:
            fresh = normals.get(o) is None
            mod = normals.add(o)
            if fresh and o.vertex_groups.active is not None:
                normals.set_input(mod, "Vertex Group", o.vertex_groups.active.name)
        return {'FINISHED'}


class OBJECT_OT_sts_smooth_normals_remove(bpy.types.Operator):
    """Remove the smooth normals modifier from the selected meshes"""
    bl_idname = "object.sts_smooth_normals_remove"
    bl_label = "Remove Smooth Normals"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        done = 0
        for o in _meshes(context):
            mod = normals.get(o)
            if mod is not None:
                o.modifiers.remove(mod)
                done += 1
        if not done:
            self.report({'WARNING'}, "No smooth normals on the selected meshes")
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_OT_sts_smooth_normals_from_mask(bpy.types.Operator):
    """Use the sculpt mask as the weights: copy it into the vertex group "Sculpt Mask"
(press again after painting the mask)"""
    bl_idname = "object.sts_smooth_normals_from_mask"
    bl_label = "From Sculpt Mask"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.mode in {'OBJECT', 'SCULPT'}

    def execute(self, context):
        obj = context.active_object
        if context.mode == 'SCULPT':
            obj.update_from_editmode()
        vg = normals.mask_to_group(obj)
        if vg is None:
            self.report({'WARNING'}, "This mesh has no sculpt mask")
            return {'CANCELLED'}
        mod = normals.get(obj) or normals.add(obj)
        normals.set_input(mod, "Vertex Group", vg.name)
        return {'FINISHED'}


classes = (
    OBJECT_OT_sts_smooth_normals_add,
    OBJECT_OT_sts_smooth_normals_remove,
    OBJECT_OT_sts_smooth_normals_from_mask,
)
