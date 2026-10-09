"""N-panel UI.

Generate tab
  Shapes    Spindle, Egg / Capsule, Gear, Star, Platonic Solid
"""

import bpy

from ...core import tabs
from . import ops


class VIEW3D_PT_sts_shapes(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Shapes"
    bl_category = tabs.GENERATE

    def draw(self, _context):
        layout = self.layout
        layout.label(text="Adjust with F9 after adding", icon='INFO')
        col = layout.column(align=True)
        for op, icon in ops.SHAPES:
            col.operator(op.bl_idname, icon=icon)


classes = (VIEW3D_PT_sts_shapes,)
