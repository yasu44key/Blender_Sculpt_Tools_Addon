"""Sujibori operators and per-object settings."""

import bpy

from . import logic

METHOD_ITEMS = (
    ('LIVE', "Live (Geometry Nodes)", "Grooves follow the lines as you edit them"),
    ('BOOLEAN', "Boolean (Snapshot)", "Cutters are rebuilt when you press Update Grooves"),
)

SOLVER_ITEMS = (
    ('MANIFOLD', "Manifold", "Fast; needs closed (manifold) meshes"),
    ('EXACT', "Exact", "Slow but handles any mesh"),
    ('FLOAT', "Float", "Fast, simple; can fail on overlapping geometry"),
)


def _on_change(self, context):
    target = self.id_data
    if not logic.is_set_up(target):
        return
    if self.method == 'LIVE':
        logic.sync(context, target)
    else:
        mod = target.modifiers.get(logic.BOOL_MOD)
        if mod is None:
            logic.sync(context, target)
        else:
            mod.solver = self.solver   # width needs Update Grooves (cutters are a snapshot)


def _on_method(self, context):
    if logic.is_set_up(self.id_data):
        logic.sync(context, self.id_data)


class SujiboriSettings(bpy.types.PropertyGroup):
    """Stored on the target mesh. Collections are pointers, so renaming never breaks them."""

    method: bpy.props.EnumProperty(
        name="Method",
        items=METHOD_ITEMS, default='LIVE', update=_on_method)
    width: bpy.props.FloatProperty(
        name="Groove Width", default=0.01, min=0.0001, soft_max=0.2, unit='LENGTH', precision=4,
        description="Width of the groove; the depth is half the width", update=_on_change)
    solver: bpy.props.EnumProperty(name="Solver", items=SOLVER_ITEMS, default='MANIFOLD', update=_on_change)
    lines: bpy.props.PointerProperty(name="Lines", type=bpy.types.Collection)
    cutters: bpy.props.PointerProperty(name="Cutters", type=bpy.types.Collection)
    node_group: bpy.props.PointerProperty(name="Node Group", type=bpy.types.NodeTree)


def _target(context):
    obj = context.active_object
    return obj if obj is not None and obj.type == 'MESH' else None


class OBJECT_OT_sts_sujibori_setup(bpy.types.Operator):
    """Prepare the active mesh for panel lines: a line collection and the groove modifier"""
    bl_idname = "object.sts_sujibori_setup"
    bl_label = "Set Up Panel Lines"
    bl_options = {'REGISTER', 'UNDO'}

    method: bpy.props.EnumProperty(items=METHOD_ITEMS, name="Method", default='LIVE')

    @classmethod
    def poll(cls, context):
        return _target(context) is not None and context.mode == 'OBJECT'

    def execute(self, context):
        target = _target(context)
        target.sts_sujibori.method = self.method
        logic.sync(context, target)
        return {'FINISHED'}


class OBJECT_OT_sts_sujibori_add_lines(bpy.types.Operator):
    """Move the selected curves into the active mesh's panel lines"""
    bl_idname = "object.sts_sujibori_add_lines"
    bl_label = "Add Selected Curves"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        t = _target(context)
        return (t is not None and t.sts_sujibori.lines is not None and context.mode == 'OBJECT'
                and any(o.type == 'CURVE' for o in context.selected_objects))

    def execute(self, context):
        target = _target(context)
        s = target.sts_sujibori
        added = 0
        for o in context.selected_objects:
            if o.type != 'CURVE' or o.name in s.lines.objects:
                continue
            for c in list(o.users_collection):
                c.objects.unlink(o)
            s.lines.objects.link(o)
            logic.make_line(o)
            added += 1
        if s.method == 'BOOLEAN':
            logic.build_cutters(context, target, s)
        self.report({'INFO'}, f"Added {added} line(s)")
        return {'FINISHED'}


class OBJECT_OT_sts_sujibori_remove_line(bpy.types.Operator):
    """Take this curve out of the panel lines (the curve itself is kept)"""
    bl_idname = "object.sts_sujibori_remove_line"
    bl_label = "Remove Line"
    bl_options = {'REGISTER', 'UNDO'}

    line: bpy.props.StringProperty(name="Line")

    @classmethod
    def poll(cls, context):
        t = _target(context)
        return t is not None and t.sts_sujibori.lines is not None

    def execute(self, context):
        target = _target(context)
        s = target.sts_sujibori
        obj = s.lines.objects.get(self.line)
        if obj is None:
            return {'CANCELLED'}
        s.lines.objects.unlink(obj)
        if not obj.users_collection:
            context.scene.collection.objects.link(obj)
        if s.method == 'BOOLEAN':
            logic.build_cutters(context, target, s)
        return {'FINISHED'}


class OBJECT_OT_sts_sujibori_update(bpy.types.Operator):
    """Rebuild the Boolean cutters from the current lines (Boolean method)"""
    bl_idname = "object.sts_sujibori_update"
    bl_label = "Update Grooves"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        t = _target(context)
        return t is not None and logic.is_set_up(t) and context.mode == 'OBJECT'

    def execute(self, context):
        target = _target(context)
        s = target.sts_sujibori
        if s.method == 'LIVE':
            logic.sync(context, target)
            return {'FINISHED'}
        n = logic.build_cutters(context, target, s)
        self.report({'INFO'}, f"{n} cutter(s) built")
        return {'FINISHED'}


class OBJECT_OT_sts_sujibori_draw_line(bpy.types.Operator):
    """Draw a new panel line on the surface (Bezier Draw into this mesh's line collection)"""
    bl_idname = "object.sts_sujibori_draw_line"
    bl_label = "Draw Line"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        t = _target(context)
        return (t is not None and t.sts_sujibori.lines is not None and context.mode == 'OBJECT'
                and hasattr(bpy.types, "CURVE_OT_sts_draw_start"))

    def execute(self, context):
        s = _target(context).sts_sujibori
        lc = logic._find_layer_collection(context.view_layer.layer_collection, s.lines)
        if lc is not None:
            context.view_layer.active_layer_collection = lc
        ds = context.scene.sts_bezier_draw
        old_depth = ds.depth_mode
        ds.depth_mode = 'SURFACE'
        try:
            result = bpy.ops.curve.sts_draw_start()
        finally:
            ds.depth_mode = old_depth          # the user's Bezier Draw settings stay as they were
        if context.object is not None and context.object.type == 'CURVE':
            logic.make_line(context.object)    # thickness comes from Groove Width
        return result


class OBJECT_OT_sts_sujibori_remove(bpy.types.Operator):
    """Remove the grooves from this mesh (the line curves are kept)"""
    bl_idname = "object.sts_sujibori_remove"
    bl_label = "Remove Panel Lines"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        t = _target(context)
        return t is not None and logic.is_set_up(t) and context.mode == 'OBJECT'

    def execute(self, context):
        logic.teardown(_target(context))
        return {'FINISHED'}


classes = (
    SujiboriSettings,
    OBJECT_OT_sts_sujibori_setup,
    OBJECT_OT_sts_sujibori_add_lines,
    OBJECT_OT_sts_sujibori_remove_line,
    OBJECT_OT_sts_sujibori_update,
    OBJECT_OT_sts_sujibori_draw_line,
    OBJECT_OT_sts_sujibori_remove,
)
