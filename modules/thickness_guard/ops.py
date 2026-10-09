"""The four Thickness Guard operators (no mouse).

Replaces: MinThicknessGuard (docs/old/min_thickness_guard.py)

Settings live on the operators (F9-adjustable, unit='LENGTH'), not on the
Scene. Mesh data is written in Object Mode; the original mode is restored
(Edit Mode keeps its vertex selection, Sculpt Mode its session).
"""

import bmesh
import bpy

from . import logic


def _to_object(context):
    """Switch to Object Mode for mesh-data writes; return the mode to restore."""
    prev = context.mode
    if prev != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    return prev


def _restore(context, prev):
    if prev == 'EDIT_MESH':
        bpy.ops.object.mode_set(mode='EDIT')
    elif prev != 'OBJECT':
        bpy.ops.object.mode_set(mode=prev)


class _MeshOnly:
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'


class OBJECT_OT_sts_thickness_bake(_MeshOnly, bpy.types.Operator):
    """Measure every vertex's wall thickness (a ray goes inward along -normal)
    into the point attribute sts_thickness"""
    bl_idname = "object.sts_thickness_bake"
    bl_label = "Bake Thickness"
    bl_options = {'REGISTER', 'UNDO'}

    max_distance: bpy.props.FloatProperty(
        name="Max Distance", default=1.0, min=0.0, soft_max=100.0, unit='LENGTH',
        description="Rays that find nothing within this distance count as this value",
    )

    def execute(self, context):
        obj = context.active_object
        prev = _to_object(context)
        count = len(logic.bake(obj, self.max_distance))
        _restore(context, prev)
        self.report({'INFO'}, f"Thickness baked for {count} vertices")
        return {'FINISHED'}


class OBJECT_OT_sts_thickness_select(_MeshOnly, bpy.types.Operator):
    """Edit Mode: select the thin vertices. Object / Sculpt Mode: write the
    vertex group Thin. Bakes first when there is no sts_thickness"""
    bl_idname = "object.sts_thickness_select"
    bl_label = "Select Thin"
    bl_options = {'REGISTER', 'UNDO'}

    min_thickness: bpy.props.FloatProperty(
        name="Min Thickness", default=0.002, min=0.0, soft_max=1.0, unit='LENGTH',
        description="Vertices thinner than this are thin",
    )

    def execute(self, context):
        obj = context.active_object
        prev = context.mode
        if prev != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        values = logic.ensure_thickness(obj)
        thin = set(logic.thin_indices(values, self.min_thickness))
        if prev == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(obj.data)
            for v in bm.verts:
                v.select = v.index in thin
            bmesh.update_edit_mesh(obj.data)
        else:
            logic.write_thin_group(obj, sorted(thin))
            if prev != 'OBJECT':
                bpy.ops.object.mode_set(mode=prev)
        self.report({'INFO'}, f"Thin vertices: {len(thin)}")
        return {'FINISHED'}


class OBJECT_OT_sts_thickness_fix(_MeshOnly, bpy.types.Operator):
    """Re-measure, then push every thin vertex outward along its normal by
    half the missing thickness; thick parts are not touched"""
    bl_idname = "object.sts_thickness_fix"
    bl_label = "Fix Thin"
    bl_options = {'REGISTER', 'UNDO'}

    min_thickness: bpy.props.FloatProperty(
        name="Min Thickness", default=0.002, min=0.0, soft_max=1.0, unit='LENGTH',
        description="Push thin vertices until the wall is at least this thick",
    )

    def execute(self, context):
        obj = context.active_object
        prev = _to_object(context)
        moved = logic.fix(obj, self.min_thickness)
        _restore(context, prev)
        if moved:
            self.report({'INFO'}, f"Moved {moved} thin vertices")
        else:
            self.report({'INFO'}, "Nothing thinner than the minimum")
        return {'FINISHED'}


class OBJECT_OT_sts_thickness_to_mask(_MeshOnly, bpy.types.Operator):
    """Write the sculpt mask from the thickness: 0 at or below thin_distance,
    1 at or above thick_distance, linear between (invert flips it)"""
    bl_idname = "object.sts_thickness_to_mask"
    bl_label = "Thickness to Mask"
    bl_options = {'REGISTER', 'UNDO'}

    thin_distance: bpy.props.FloatProperty(
        name="Thin Distance", default=0.001, min=0.0, soft_max=1.0, unit='LENGTH',
        description="Thickness at or below this gets mask 0",
    )
    thick_distance: bpy.props.FloatProperty(
        name="Thick Distance", default=0.005, min=0.0, soft_max=10.0, unit='LENGTH',
        description="Thickness at or above this gets mask 1",
    )
    invert: bpy.props.BoolProperty(
        name="Invert", default=False,
        description="Flip the mask",
    )

    def execute(self, context):
        obj = context.active_object
        prev = _to_object(context)
        values = logic.ensure_thickness(obj)
        logic.to_mask(obj, values, self.thin_distance, self.thick_distance, self.invert)
        _restore(context, prev)
        self.report({'INFO'}, "Sculpt mask written from thickness")
        return {'FINISHED'}


classes = (
    OBJECT_OT_sts_thickness_bake,
    OBJECT_OT_sts_thickness_select,
    OBJECT_OT_sts_thickness_fix,
    OBJECT_OT_sts_thickness_to_mask,
)
