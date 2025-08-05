
bl_info = {
    "name": "Edge Creation Tool",
    "description": "Interactive creation of edges in the 3D view with snapping.",
    "author": "Yoshiki Yasunaga & ChatGPT",
    "version": (1, 5),
    "blender": (4, 4, 0),
    "location": "View3D > Add > Mesh",
    "category": "Mesh"
}

import bpy
import bmesh
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from mathutils import Vector

class OBJECT_OT_create_edge(bpy.types.Operator):
    """Create Edge by Mouse Clicks with Snap Support"""
    bl_idname = "mesh.create_edge_tool"
    bl_label = "Create Edge Tool"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'

    def modal(self, context, event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
            region = context.region
            rv3d = context.region_data

            origin_3d = region_2d_to_origin_3d(region, rv3d, mouse_pos)
            direction_3d = region_2d_to_vector_3d(region, rv3d, mouse_pos)

            result, location, normal, index, object, matrix = context.scene.ray_cast(
                context.view_layer.depsgraph, origin_3d, direction_3d)

            coord = location if result else origin_3d + direction_3d * 10

            if not self.mesh:
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.select_all(action='DESELECT')
                self.mesh = bpy.data.meshes.new("EdgeMesh")
                self.obj = bpy.data.objects.new("EdgeObject", self.mesh)
                bpy.context.collection.objects.link(self.obj)
                self.bm = bmesh.new()

            if self.bm.is_valid:
                new_vert = self.bm.verts.new(coord)
                self.verts.append(new_vert)

                if self.prev_vert:
                    self.bm.edges.new((self.prev_vert, new_vert))
                self.prev_vert = new_vert

                self.bm.to_mesh(self.mesh)
                self.mesh.update()

        elif event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.mesh = None
        self.obj = None
        self.bm = None
        self.prev_vert = None
        self.verts = []

        if context.area.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}

    def finish(self):
        if self.bm:
            if self.mesh:
                self.bm.to_mesh(self.mesh)
                self.mesh.update()
            self.bm.free()
            self.bm = None

        if self.obj:
            bpy.context.view_layer.objects.active = self.obj
            self.obj.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

    def cancel(self, context):
        self.finish()

class OBJECT_OT_fill_face(bpy.types.Operator):
    """Fill Face"""
    bl_idname = "mesh.fill_face"
    bl_label = "Fill Face"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.object and context.object.type == 'MESH':
            bpy.ops.mesh.edge_face_add()
        return {'FINISHED'}

class OBJECT_OT_toggle_edit_mode(bpy.types.Operator):
    """Toggle Edit Mode"""
    bl_idname = "object.toggle_edit_mode"
    bl_label = "Toggle Object/Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.object and context.object.type == 'MESH':
            if context.object.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}

class VIEW3D_PT_edge_creation_panel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Edge Creation Tool (ESC or RightClick to End)"
    bl_idname = "VIEW3D_PT_edge_creation_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt Tools'

    def draw(self, context):
        layout = self.layout
        layout.operator("mesh.create_edge_tool", text="Start Drawing")
        layout.operator("mesh.fill_face", text="Fill Face")
        layout.operator("object.toggle_edit_mode", text="Toggle Object/Edit Mode")

def register():
    bpy.utils.register_class(OBJECT_OT_create_edge)
    bpy.utils.register_class(OBJECT_OT_fill_face)
    bpy.utils.register_class(OBJECT_OT_toggle_edit_mode)
    bpy.utils.register_class(VIEW3D_PT_edge_creation_panel)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_create_edge)
    bpy.utils.unregister_class(OBJECT_OT_fill_face)
    bpy.utils.unregister_class(OBJECT_OT_toggle_edit_mode)
    bpy.utils.unregister_class(VIEW3D_PT_edge_creation_panel)

if __name__ == "__main__":
    register()
