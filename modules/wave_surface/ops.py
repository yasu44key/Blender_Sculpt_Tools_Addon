"""Wave Surface operators: add a wave grid, put the live surface on meshes, scatter wave centers."""

import random

import bpy

from . import surface


def _meshes(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


class MESH_OT_sts_wave_surface_add(bpy.types.Operator):
    """Add a grid at the 3D cursor with a live wave surface (edit the waves in the Generate tab)"""
    bl_idname = "mesh.sts_wave_surface_add"
    bl_label = "Wave Surface"
    bl_options = {'REGISTER', 'UNDO'}

    size: bpy.props.FloatProperty(
        name="Size", default=10.0, min=0.01, soft_max=100.0, unit='LENGTH', description="Width of the grid")
    resolution: bpy.props.IntProperty(
        name="Resolution", default=100, min=2, max=1000, description="Number of faces along each side")

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.mesh.primitive_grid_add(
            x_subdivisions=self.resolution, y_subdivisions=self.resolution, size=self.size,
            location=context.scene.cursor.location)
        obj = context.active_object
        obj.name = obj.data.name = "Wave Surface"
        for p in obj.data.polygons:
            p.use_smooth = True
        surface.add(obj)
        return {'FINISHED'}


class OBJECT_OT_sts_wave_surface_assign(bpy.types.Operator):
    """Put the live wave surface on the selected meshes"""
    bl_idname = "object.sts_wave_surface_assign"
    bl_label = "Add to Selected"
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
            surface.add(o)
        return {'FINISHED'}


class OBJECT_OT_sts_wave_surface_remove(bpy.types.Operator):
    """Remove the live wave surface from the selected meshes"""
    bl_idname = "object.sts_wave_surface_remove"
    bl_label = "Remove Wave Surface"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        done = 0
        for o in _meshes(context):
            mod = surface.get(o)
            if mod is not None:
                o.modifiers.remove(mod)
                done += 1
        if not done:
            self.report({'WARNING'}, "No wave surface on the selected meshes")
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_OT_sts_wave_surface_scatter(bpy.types.Operator):
    """Move the wave centers to random places (change Seed with F9)"""
    bl_idname = "object.sts_wave_surface_scatter"
    bl_label = "Scatter Centers"
    bl_options = {'REGISTER', 'UNDO'}

    seed: bpy.props.IntProperty(name="Seed", default=0, min=0)
    spread: bpy.props.FloatProperty(
        name="Spread", default=2.5, min=0.0, soft_max=50.0, unit='LENGTH',
        description="Centers land within this distance of the object origin (X and Y)")

    @classmethod
    def poll(cls, context):
        return surface.get(context.active_object) is not None

    def execute(self, context):
        mod = surface.get(context.active_object)
        rng = random.Random(self.seed)
        for k in range(1, surface.WAVES + 1):
            surface.set_input(mod, f"Wave {k} Center X", rng.uniform(-self.spread, self.spread))
            surface.set_input(mod, f"Wave {k} Center Y", rng.uniform(-self.spread, self.spread))
        return {'FINISHED'}


def add_menu(self, _context):
    self.layout.operator(MESH_OT_sts_wave_surface_add.bl_idname, icon='MOD_WAVE')


classes = (
    MESH_OT_sts_wave_surface_add,
    OBJECT_OT_sts_wave_surface_assign,
    OBJECT_OT_sts_wave_surface_remove,
    OBJECT_OT_sts_wave_surface_scatter,
)
