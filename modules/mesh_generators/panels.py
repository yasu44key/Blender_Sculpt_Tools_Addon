"""N-panel UI.

Generate tab
  Mesh Generators   Lattice Grid, Hexagonal Grid, Random Grid, Leaf Venation
"""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_mesh_generators(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Mesh Generators"
    bl_category = tabs.GENERATE

    def draw(self, _context):
        layout = self.layout
        layout.label(text="Adjust with F9 after adding", icon='INFO')
        col = layout.column(align=True)
        for op, icon in ops.GENERATORS:
            col.operator(op.bl_idname, icon=icon)


classes = (VIEW3D_PT_sts_mesh_generators,)
