"""Tessellation operators: Tile Faces (exact tiles, one shot), Live Cells (Geometry
Nodes modifier) and Skin Lattice (vertex radii + Skin modifier)."""

import math

import bmesh
import bpy

from . import cells, tile

PATTERN_ITEMS = (
    ('SQUARE', "Square", "Square tiles, Tile Size wide"),
    ('BRICK', "Brick", "Running bond: Tile Size long, shifted every row"),
    ('TRIANGLE', "Triangle", "Equilateral triangles with edges of Tile Size"),
    ('HEXAGON', "Hexagon", "Regular hexagons with edges of Tile Size"),
    ('OCTAGON', "Octagon + Square", "Octagons Tile Size across, with small squares between"),
    ('VORONOI', "Voronoi", "Irregular cells about Tile Size apart"),
)

MAX_TILES = 200000


def _edit_targets(context):
    """Edit Mode: (object, selected faces) for every mesh in Edit Mode."""
    out = []
    for obj in context.objects_in_mode_unique_data:
        if obj.type == 'MESH':
            bm = bmesh.from_edit_mesh(obj.data)
            out.append((obj, bm, [f for f in bm.faces if f.select]))
    return out


class MESH_OT_sts_tile_faces(bpy.types.Operator):
    """Lay a tile pattern of an exact size over the faces (Edit Mode: selected faces, Object Mode: whole mesh).
The pattern runs across face edges, follows bent faces and keeps UVs"""
    bl_idname = "mesh.sts_tile_faces"
    bl_label = "Tile Faces"
    bl_options = {'REGISTER', 'UNDO'}

    pattern: bpy.props.EnumProperty(name="Pattern", items=PATTERN_ITEMS, default='HEXAGON')
    tile_size: bpy.props.FloatProperty(
        name="Tile Size", default=0.2, min=0.0001, soft_max=10.0, unit='LENGTH', precision=4,
        description="Size of one tile in world units (see each pattern for what is measured)")
    brick_ratio: bpy.props.FloatProperty(
        name="Length / Height", default=2.0, min=0.1, soft_max=10.0,
        description="Brick length divided by brick height")
    brick_offset: bpy.props.FloatProperty(
        name="Row Shift", default=0.5, min=0.0, max=1.0, subtype='FACTOR',
        description="How far each row of bricks is shifted, as a fraction of a brick")
    randomness: bpy.props.FloatProperty(
        name="Randomness", default=0.6, min=0.0, max=1.0, subtype='FACTOR',
        description="0 = regular hexagons, 1 = fully irregular cells")
    seed: bpy.props.IntProperty(name="Seed", default=0, min=0, description="Random seed for Voronoi")
    rotation: bpy.props.FloatProperty(
        name="Pattern Rotation", default=0.0, subtype='ANGLE',
        description="Rotate the pattern on the surface")
    offset: bpy.props.FloatVectorProperty(
        name="Pattern Offset", size=2, default=(0.0, 0.0), unit='LENGTH',
        description="Slide the pattern on the surface")
    region_angle: bpy.props.FloatProperty(
        name="Continuous up to", default=math.radians(30.0), min=0.0, max=math.radians(60.0),
        subtype='ANGLE',
        description="Neighbouring faces bent less than this share one continuous pattern; "
                    "past it the pattern starts again (like at the corner of a box)")
    sliver: bpy.props.FloatProperty(
        name="Merge Small Pieces", default=0.1, min=0.0, max=0.5, subtype='FACTOR',
        description="Cut tiles smaller than this fraction of a whole tile join their neighbour (0 = keep all)")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "pattern")
        layout.prop(self, "tile_size")
        if self.pattern == 'BRICK':
            layout.prop(self, "brick_ratio")
            layout.prop(self, "brick_offset")
        elif self.pattern == 'VORONOI':
            layout.prop(self, "randomness")
            layout.prop(self, "seed")
        layout.prop(self, "rotation")
        layout.prop(self, "offset")
        layout.prop(self, "region_angle")
        layout.prop(self, "sliver")

    def _opts(self):
        return {"ratio": self.brick_ratio, "offset": self.brick_offset,
                "randomness": self.randomness, "seed": self.seed}

    def _too_many(self, objs_faces):
        area = 0.0
        for obj, faces in objs_faces:
            mw = obj.matrix_world
            s = mw.to_scale()
            k = abs(s.x * s.y * s.z) ** (2.0 / 3.0)
            area += sum(f.calc_area() for f in faces) * k
        return area / (self.tile_size ** 2) > MAX_TILES

    def execute(self, context):
        opts = self._opts()
        args = dict(angle=self.rotation, offset=tuple(self.offset),
                    region_angle=self.region_angle, sliver=self.sliver)

        if context.mode == 'EDIT_MESH':
            targets = [(o, bm, fs) for o, bm, fs in _edit_targets(context) if fs]
            if not targets:
                self.report({'WARNING'}, "Select the faces to tile")
                return {'CANCELLED'}
            if any(o.data.shape_keys for o, _bm, _fs in targets):
                self.report({'WARNING'}, "Meshes with shape keys are not supported")
                return {'CANCELLED'}
            if self._too_many([(o, fs) for o, _bm, fs in targets]):
                self.report({'WARNING'}, "Too many tiles: make Tile Size larger")
                return {'CANCELLED'}
            total = 0
            for obj, bm, faces in targets:
                new = tile.tile_faces(bm, faces, obj.matrix_world, self.pattern, self.tile_size, opts, **args)
                for f in bm.faces:
                    f.select_set(False)
                for f in new:
                    f.select_set(True)
                bm.select_flush_mode()
                bmesh.update_edit_mesh(obj.data)
                total += len(new)
        else:
            objs = []
            seen = set()
            for o in context.selected_objects or [context.active_object]:
                if o.type == 'MESH' and o.data not in seen and o.data.polygons:
                    seen.add(o.data)
                    objs.append(o)
            if not objs:
                self.report({'WARNING'}, "Select a mesh with faces")
                return {'CANCELLED'}
            if any(o.data.shape_keys for o in objs):
                self.report({'WARNING'}, "Meshes with shape keys are not supported")
                return {'CANCELLED'}
            bms = []
            for o in objs:
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bms.append(bm)
            if self._too_many([(o, bm.faces) for o, bm in zip(objs, bms)]):
                for bm in bms:
                    bm.free()
                self.report({'WARNING'}, "Too many tiles: make Tile Size larger")
                return {'CANCELLED'}
            total = 0
            for obj, bm in zip(objs, bms):
                new = tile.tile_faces(bm, list(bm.faces), obj.matrix_world, self.pattern,
                                      self.tile_size, opts, **args)
                bm.to_mesh(obj.data)
                bm.free()
                obj.data.update()
                total += len(new)

        if total == 0:
            self.report({'WARNING'}, "No tiles were made")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{total} tiles")
        return {'FINISHED'}


# ---------------------------------------------------------------- live cells

def _cell_targets(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


class OBJECT_OT_sts_cells_add(bpy.types.Operator):
    """Add a live cell pattern (Geometry Nodes modifier) to the selected meshes; change it any time"""
    bl_idname = "object.sts_cells_add"
    bl_label = "Add Live Cells"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        objs = _cell_targets(context)
        if not objs:
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}
        for o in objs:
            cells.add(o)
        return {'FINISHED'}


class OBJECT_OT_sts_cells_remove(bpy.types.Operator):
    """Remove the live cell pattern from the selected meshes"""
    bl_idname = "object.sts_cells_remove"
    bl_label = "Remove Live Cells"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        done = 0
        for o in _cell_targets(context):
            mod = cells.get(o)
            if mod is not None:
                o.modifiers.remove(mod)
                done += 1
        if not done:
            self.report({'WARNING'}, "No live cells on the selected meshes")
            return {'CANCELLED'}
        return {'FINISHED'}


# ---------------------------------------------------------------- skin lattice

class MESH_OT_sts_skin_lattice(bpy.types.Operator):
    """Turn the edges into round struts: set the Skin radius of the vertices (Edit Mode: selected)
and add a Skin modifier if there is none"""
    bl_idname = "mesh.sts_skin_lattice"
    bl_label = "Skin Lattice"
    bl_options = {'REGISTER', 'UNDO'}

    radius: bpy.props.FloatProperty(
        name="Strut Radius", default=0.02, min=0.0001, soft_max=1.0, unit='LENGTH', precision=4,
        description="Skin radius written to the vertices")
    add_modifier: bpy.props.BoolProperty(
        name="Add Skin Modifier", default=True,
        description="Add a Skin modifier when the mesh has none")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.mode in {'OBJECT', 'EDIT_MESH'}

    def execute(self, context):
        obj = context.active_object
        edit = context.mode == 'EDIT_MESH'
        if edit:
            bm = bmesh.from_edit_mesh(obj.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
        bm.verts.layers.skin.verify()      # before taking vertex references (see set_skin_radius)
        if edit:
            verts = [v for v in bm.verts if v.select]
        else:
            verts = list(bm.verts)
        if not verts:
            if not edit:
                bm.free()
            self.report({'WARNING'}, "Select the vertices")
            return {'CANCELLED'}

        set_skin_radius(bm, verts, self.radius)

        if edit:
            bmesh.update_edit_mesh(obj.data)
        else:
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
        if self.add_modifier and not any(m.type == 'SKIN' for m in obj.modifiers):
            obj.modifiers.new("STS Skin", 'SKIN')
        return {'FINISHED'}


def set_skin_radius(bm, verts, radius):
    """Write the radius, and leave exactly one root in each connected piece that was
    touched (the Skin modifier needs one; two in a piece make it complain).

    The layer must already exist: adding it would invalidate `verts`."""
    layer = bm.verts.layers.skin.active
    for v in verts:
        v[layer].radius = (radius, radius)
    seen = set()
    for start in verts:
        if start in seen:
            continue
        piece = [start]
        seen.add(start)
        i = 0
        while i < len(piece):
            for e in piece[i].link_edges:
                o = e.other_vert(piece[i])
                if o not in seen:
                    seen.add(o)
                    piece.append(o)
            i += 1
        roots = [v for v in piece if v[layer].use_root]
        if not roots:
            start[layer].use_root = True
        for v in roots[1:]:
            v[layer].use_root = False


classes = (
    MESH_OT_sts_tile_faces,
    OBJECT_OT_sts_cells_add,
    OBJECT_OT_sts_cells_remove,
    MESH_OT_sts_skin_lattice,
)
