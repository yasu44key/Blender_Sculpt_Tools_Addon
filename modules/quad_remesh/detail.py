"""Project Detail — bake the source's detail into a Multires on the quad result.

object.sts_quad_project_detail   on a "<name>_Quad" object (its "STS Fit" names the source):
    1. apply "STS Mirror" (Multires has to come first), take off "STS Fit"
    2. Multires subdivided to `levels`
    3. at the top level: snap onto the source, then `rounds` x (relax, snap again)
    4. reshape the Multires to that result and drop the helpers
The result is an ordinary Multires the user can keep sculpting on.

Why the relax rounds: snapping each subdivided vertex to the nearest point of a deep, thin
crease (lip line, nostril rim) sends neighbours to opposite walls and leaves a saw-tooth edge.
Relax + re-snap six times took most of it away on the head scan (10-10).
"""

import bpy
from bpy.props import FloatProperty, IntProperty

from . import ops

MULTIRES = "Multires"
_TEMP = "STS Detail Temp"


def _source_of(obj):
    fit = obj.modifiers.get(ops.FIT)
    return fit.target if fit is not None else None


class OBJECT_OT_sts_quad_project_detail(bpy.types.Operator):
    """Add a Multires and bake the source's detail into it (snap, then relax and snap again)"""
    bl_idname = "object.sts_quad_project_detail"
    bl_label = "Project Detail"
    bl_options = {'REGISTER', 'UNDO'}

    levels: IntProperty(name="Subdivision Levels", description="Multires levels to bake the detail into",
                        default=2, min=1, max=5)
    rounds: IntProperty(name="Relax Rounds", description="Relax and snap again this many times "
                        "(removes the saw-tooth along thin creases; 0 = snap only)",
                        default=6, min=0, max=20)
    relax: FloatProperty(name="Relax Strength", default=0.5, min=0.0, max=1.0, subtype='FACTOR')

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o is not None and o.type == 'MESH' and context.mode == 'OBJECT' and _source_of(o) is not None

    def execute(self, context):
        obj = context.active_object
        src = _source_of(obj)
        allowed = {ops.FIT, ops.MIRROR}
        others = [m for m in obj.modifiers if m.name not in allowed and m.type != 'MULTIRES']
        if others:
            self.report({'WARNING'}, "Apply or remove the other modifiers first: " + ", ".join(m.name for m in others))
            return {'CANCELLED'}
        with context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                   selected_editable_objects=[obj]):
            if obj.modifiers.get(ops.MIRROR) is not None:
                bpy.ops.object.modifier_move_to_index(modifier=ops.MIRROR, index=0)
                bpy.ops.object.modifier_apply(modifier=ops.MIRROR)
            obj.modifiers.remove(obj.modifiers[ops.FIT])
            mr = next((m for m in obj.modifiers if m.type == 'MULTIRES'), None)
            if mr is None:
                mr = obj.modifiers.new(MULTIRES, 'MULTIRES')
            while mr.total_levels < self.levels:
                bpy.ops.object.multires_subdivide(modifier=mr.name, mode='CATMULL_CLARK')
            mr.levels = mr.sculpt_levels = mr.render_levels = mr.total_levels

            # helpers at the top level: snap, then rounds x (relax, snap)
            temps = []

            def snap():
                m = obj.modifiers.new(f"{_TEMP} {len(temps)}", 'SHRINKWRAP')
                m.target = src
                m.wrap_method = 'NEAREST_SURFACEPOINT'
                temps.append(m)
            snap()
            for _ in range(self.rounds):
                m = obj.modifiers.new(f"{_TEMP} {len(temps)}", 'SMOOTH')
                m.factor = self.relax
                m.iterations = 3
                temps.append(m)
                snap()

            dg = context.evaluated_depsgraph_get()
            dg.update()
            baked = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
            for m in temps:
                obj.modifiers.remove(m)
            helper = bpy.data.objects.new(_TEMP, baked)
            context.scene.collection.objects.link(helper)
            helper.matrix_world = obj.matrix_world.copy()
        try:
            with context.temp_override(object=obj, active_object=obj, selected_objects=[obj, helper],
                                       selected_editable_objects=[obj, helper]):
                bpy.ops.object.multires_reshape(modifier=mr.name)
        finally:
            bpy.data.objects.remove(helper)
            bpy.data.meshes.remove(baked)
        self.report({'INFO'}, "Detail projected into %d Multires levels" % mr.total_levels)
        return {'FINISHED'}


classes = (OBJECT_OT_sts_quad_project_detail,)
