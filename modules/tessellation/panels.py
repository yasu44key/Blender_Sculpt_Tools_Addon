"""Model tab panel for Tessellation."""

import bpy

from ...core import nodes, tabs
from . import cells


class VIEW3D_PT_sts_tessellation(bpy.types.Panel):
    bl_label = "Tessellation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = tabs.MODEL

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            layout.label(text="Select a mesh", icon='INFO')
            return
        edit = context.mode == 'EDIT_MESH'

        box = layout.box()
        box.label(text="Tile Faces", icon='MESH_GRID')
        box.label(text="Target: selected faces" if edit else "Target: whole mesh")
        col = box.column()
        col.scale_y = 1.2
        col.operator("mesh.sts_tile_faces", icon='MOD_TRIANGULATE')
        box.label(text="Adjust with F9 after tiling", icon='INFO')

        box = layout.box()
        box.label(text="Live Cells", icon='GEOMETRY_NODES')
        mod = cells.get(obj)
        if edit:
            box.label(text="Object Mode only", icon='INFO')
        elif mod is None or mod.node_group is None:
            col = box.column()
            col.scale_y = 1.2
            col.operator("object.sts_cells_add", icon='ADD')
        else:
            col = box.column()
            col.use_property_split = True
            col.use_property_decorate = False
            ng = mod.node_group
            for spec in cells.INPUTS:
                name = spec[0]
                if name == "Strut Radius" and not cells.get_input(mod, "Lattice"):
                    continue
                if name in ("Gap", "Cell Thickness") and cells.get_input(mod, "Lattice"):
                    continue
                nodes.draw_modifier_input(col, mod, nodes.socket_identifier(ng, name), name)
            col.prop(mod, "show_viewport", text="Show Cells")
            row = box.row(align=True)
            row.operator("object.modifier_apply", text="Apply (Bake)", icon='CHECKMARK').modifier = mod.name
            row.operator("object.sts_cells_remove", text="Remove", icon='TRASH')

        box = layout.box()
        box.label(text="Skin Lattice", icon='MOD_SKIN')
        box.operator("mesh.sts_skin_lattice", icon='MOD_SKIN')


classes = (
    VIEW3D_PT_sts_tessellation,
)
