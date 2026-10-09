"""Join selected objects into one mesh and voxel-remesh it.

Face sets survive because the remesh is done with object.voxel_remesh()
and use_remesh_preserve_attributes (a Remesh *modifier* apply drops them).
Originals are never edited: the new mesh is built from their evaluated
geometry, then the originals are hidden (or deleted when asked).
"""

import bpy
from bpy.app.translations import pgettext_iface as iface
from mathutils import Vector

CONVERTIBLE = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}
MOD_NAME = "STS Voxel Remesh"
WARN_DIVISIONS = 400


# ---------------------------------------------------------------- helpers

def world_bounds(objects):
    pts = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    if not pts:
        return Vector(), Vector()
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def estimate_divisions(objects, voxel_size):
    """Voxels along the longest side of all objects together."""
    lo, hi = world_bounds(objects)
    longest = max(hi - lo) if objects else 0.0
    return longest / voxel_size if voxel_size > 0 else 0.0


def auto_dyntopo_resolution(voxel_size):
    """Constant-detail resolution whose edge length is about 2 voxels."""
    return 1.0 / (voxel_size * 2.0)


def find_voxel_modifier(obj):
    for m in obj.modifiers:
        if m.type == 'REMESH' and m.mode == 'VOXEL':
            return m
    return None


def assign_face_set(mesh, face_set_id):
    attr = mesh.attributes.get(".sculpt_face_set")
    if attr is None:
        attr = mesh.attributes.new(".sculpt_face_set", 'INT', 'FACE')
    attr.data.foreach_set("value", [face_set_id] * len(mesh.polygons))


def remesh_keep_attributes(obj, voxel_size, adaptivity):
    """Voxel remesh `obj` (must be active, Object Mode) keeping face sets / mask."""
    me = obj.data
    me.remesh_voxel_size = voxel_size
    me.remesh_voxel_adaptivity = adaptivity
    me.use_remesh_fix_poles = True
    me.use_remesh_preserve_attributes = True
    return bpy.ops.object.voxel_remesh()


def mesh_copy_of(obj, depsgraph, apply_modifiers):
    """A new mesh datablock with obj's geometry, in obj's local space."""
    if obj.type == 'MESH' and not apply_modifiers:
        return obj.data.copy()
    return bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))


def select_only(context, obj):
    for o in context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


# ---------------------------------------------------------------- operators

class OBJECT_OT_sts_voxel_join_remesh(bpy.types.Operator):
    """Join the selected objects into one mesh and voxel-remesh it.
    Each source object becomes its own face set; the originals are kept hidden"""
    bl_idname = "object.sts_voxel_join_remesh"
    bl_label = "Join & Remesh"
    bl_options = {'REGISTER', 'UNDO'}

    voxel_size: bpy.props.FloatProperty(
        name="Voxel Size", default=0.01, min=0.0005, max=1.0, precision=4, step=0.1, unit='LENGTH',
        description="Size of one voxel (smaller = denser and slower)")
    adaptivity: bpy.props.FloatProperty(
        name="Adaptivity", default=0.0, min=0.0, max=1.0,
        description="Reduce polygons on flat areas")
    apply_modifiers: bpy.props.BoolProperty(
        name="Use Modifier Results", default=True,
        description="Take each object's geometry with its modifiers applied (the originals are not changed)")
    keep_originals: bpy.props.BoolProperty(
        name="Keep Originals", default=True,
        description="Keep the source objects (hidden). Off = delete them")
    face_set_per_object: bpy.props.BoolProperty(
        name="Face Set per Object", default=True,
        description="Give each source object its own face set")
    remesh_mode: bpy.props.EnumProperty(
        name="Remesh",
        items=[('APPLY', "Apply Now", "Remesh the joined mesh now (face sets kept)"),
               ('MODIFIER', "As Modifier", "Add a Voxel Remesh modifier to tune first; "
                                           "apply it later with Apply Remesh")],
        default='APPLY')
    final_mode: bpy.props.EnumProperty(
        name="Then",
        items=[('OBJECT', "Object Mode", "Stay in Object Mode with the result selected"),
               ('SCULPT', "Sculpt Mode", "Go to Sculpt Mode on the result")],
        default='OBJECT')
    use_dyntopo: bpy.props.BoolProperty(
        name="Dyntopo", default=False,
        description="Turn on Dynamic Topology in Sculpt Mode")
    dyntopo_detail_type: bpy.props.EnumProperty(
        name="Detailing",
        items=[('CONSTANT', "Constant Detail", "Same detail everywhere"),
               ('BRUSH', "Brush Detail", "Detail relative to the brush size"),
               ('RELATIVE', "Relative Detail", "Detail relative to the view"),
               ('MANUAL', "Manual Detail", "Only by Detail Flood Fill")],
        default='CONSTANT')
    dyntopo_auto_resolution: bpy.props.BoolProperty(
        name="Resolution from Voxel Size", default=True,
        description="Constant detail matches the voxel size (edge = 2 voxels)")
    dyntopo_resolution: bpy.props.FloatProperty(
        name="Resolution", default=50.0, min=0.1, max=10000.0)
    dyntopo_detail_size: bpy.props.FloatProperty(
        name="Detail Size", default=12.0, min=0.5, max=100.0, subtype='PIXEL')
    dyntopo_detail_percent: bpy.props.FloatProperty(
        name="Detail Percentage", default=25.0, min=0.5, max=100.0, subtype='PERCENTAGE')
    dyntopo_refine: bpy.props.EnumProperty(
        name="Refine Method",
        items=[('SUBDIVIDE', "Subdivide Edges", ""),
               ('COLLAPSE', "Collapse Edges", ""),
               ('SUBDIVIDE_COLLAPSE', "Subdivide Collapse", "")],
        default='SUBDIVIDE_COLLAPSE')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(
            o.type in CONVERTIBLE for o in context.selected_objects)

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sources = [o for o in context.selected_objects if o.type in CONVERTIBLE]
        div = estimate_divisions(sources, self.voxel_size)
        col = layout.column(align=True)
        col.prop(self, "voxel_size")
        col.prop(self, "adaptivity")
        if div > WARN_DIVISIONS:
            box = layout.box()
            box.alert = True
            box.label(text="Voxel size is very small for this size", icon='ERROR')
            box.label(text=iface("Voxels on the longest side") + f": {int(div)}  "
                      + iface("(under 400 is safe)"), translate=False)
        else:
            layout.label(text=iface("Voxels on the longest side") + f": {int(div)}",
                         icon='INFO', translate=False)

        col = layout.column(heading="Sources")
        col.prop(self, "keep_originals")
        col.prop(self, "apply_modifiers")
        col.prop(self, "face_set_per_object")
        layout.prop(self, "remesh_mode", expand=True)
        layout.prop(self, "final_mode", expand=True)

        if self.final_mode == 'SCULPT':
            layout.prop(self, "use_dyntopo")
            if self.use_dyntopo:
                box = layout.box()
                box.prop(self, "dyntopo_detail_type")
                if self.dyntopo_detail_type == 'CONSTANT':
                    box.prop(self, "dyntopo_auto_resolution")
                    row = box.row()
                    if self.dyntopo_auto_resolution:
                        row.enabled = False
                        row.label(text=f"{auto_dyntopo_resolution(self.voxel_size):.1f}",
                                  translate=False)
                    else:
                        row.prop(self, "dyntopo_resolution")
                elif self.dyntopo_detail_type == 'BRUSH':
                    box.prop(self, "dyntopo_detail_size")
                elif self.dyntopo_detail_type == 'RELATIVE':
                    box.prop(self, "dyntopo_detail_percent")
                box.prop(self, "dyntopo_refine")

    def execute(self, context):
        sources = [o for o in context.selected_objects if o.type in CONVERTIBLE]
        skipped = [o.name for o in context.selected_objects if o.type not in CONVERTIBLE]
        if skipped:
            self.report({'WARNING'}, "Skipped (not geometry): " + ", ".join(skipped))
        if not sources:
            self.report({'WARNING'}, "No mesh, curve, surface, metaball or text selected")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        first = context.active_object if context.active_object in sources else sources[0]
        ordered = [first] + [o for o in sources if o is not first]

        # Build a fresh mesh object per source; the sources stay untouched.
        parts = []
        for i, src in enumerate(ordered):
            me = mesh_copy_of(src, depsgraph, self.apply_modifiers)
            if len(me.polygons) == 0:
                bpy.data.meshes.remove(me)
                continue
            if self.face_set_per_object:
                assign_face_set(me, i + 1)
            part = bpy.data.objects.new(src.name + "_part", me)
            part.matrix_world = src.matrix_world
            context.collection.objects.link(part)
            parts.append(part)
        if not parts:
            self.report({'WARNING'}, "The selected objects have no faces")
            return {'CANCELLED'}

        for o in context.selected_objects:
            o.select_set(False)
        for p in parts:
            p.select_set(True)
        context.view_layer.objects.active = parts[0]
        if len(parts) > 1:
            bpy.ops.object.join()
        result = context.view_layer.objects.active
        result.name = first.name + "_Remesh"
        result.data.name = result.name

        if self.keep_originals:
            for src in sources:
                src.hide_set(True)
        else:
            for src in sources:
                bpy.data.objects.remove(src, do_unlink=True)

        select_only(context, result)
        if self.remesh_mode == 'APPLY':
            remesh_keep_attributes(result, self.voxel_size, self.adaptivity)
        else:
            mod = result.modifiers.new(MOD_NAME, 'REMESH')
            mod.mode = 'VOXEL'
            mod.voxel_size = self.voxel_size
            mod.adaptivity = self.adaptivity
            result.data.remesh_voxel_size = self.voxel_size
            result.data.remesh_voxel_adaptivity = self.adaptivity

        if self.final_mode == 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')
            if self.use_dyntopo:
                self._setup_dyntopo(context)

        self.report({'INFO'}, f"Joined {len(parts)} object(s) into {result.name}")
        return {'FINISHED'}

    def _setup_dyntopo(self, context):
        if self.remesh_mode == 'MODIFIER':
            # Dyntopo works on the real mesh, so the modifier must be applied first.
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.sts_voxel_apply_remesh()
            bpy.ops.object.mode_set(mode='SCULPT')
        if not context.object.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        sculpt = context.scene.tool_settings.sculpt
        sculpt.detail_type_method = self.dyntopo_detail_type
        sculpt.detail_refine_method = self.dyntopo_refine
        if self.dyntopo_detail_type == 'CONSTANT':
            sculpt.constant_detail_resolution = (
                auto_dyntopo_resolution(self.voxel_size) if self.dyntopo_auto_resolution
                else self.dyntopo_resolution)
        elif self.dyntopo_detail_type == 'BRUSH':
            sculpt.detail_size = self.dyntopo_detail_size
        elif self.dyntopo_detail_type == 'RELATIVE':
            sculpt.detail_percent = self.dyntopo_detail_percent


class OBJECT_OT_sts_voxel_apply_remesh(bpy.types.Operator):
    """Remesh the active mesh keeping face sets and mask.
    Uses the Voxel Remesh modifier's values if it has one (and removes it), otherwise the mesh's own.
    In Sculpt Mode with Dyntopo on, Dyntopo is switched off for the remesh and back on afterwards"""
    bl_idname = "object.sts_voxel_apply_remesh"
    bl_label = "Apply Remesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.mode in {'OBJECT', 'SCULPT'}

    def execute(self, context):
        obj = context.active_object
        mode = obj.mode
        # Dyntopo keeps its own BMesh; remeshing under it would be thrown away.
        dyntopo = mode == 'SCULPT' and obj.use_dynamic_topology_sculpting
        if dyntopo:
            bpy.ops.sculpt.dynamic_topology_toggle()
        if mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        mod = find_voxel_modifier(obj)
        if mod is not None:
            size, adapt = mod.voxel_size, mod.adaptivity
            obj.modifiers.remove(mod)
        else:
            size, adapt = obj.data.remesh_voxel_size, obj.data.remesh_voxel_adaptivity
        remesh_keep_attributes(obj, size, adapt)
        if mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=mode)
        if dyntopo and not obj.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        self.report({'INFO'}, f"Remeshed with voxel size {size:.4f}")
        return {'FINISHED'}


classes = (
    OBJECT_OT_sts_voxel_join_remesh,
    OBJECT_OT_sts_voxel_apply_remesh,
)
