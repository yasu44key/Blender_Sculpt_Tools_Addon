"""Wear operator — edge chips near sharp edges + surface erosion, one shot.

Replaces: aging_toolkit.py (docs/old/)

Fixes over the old version: inset_individual returns the rim ring, not the
inner face — only the original face passed to inset (which becomes the inner
face) is pushed, so grid points shared with neighbours stay put; no preview
copies, modifiers untouched; all settings are operator properties (F9),
nothing on the Scene; chip / erosion sizes are ratios of each face's own size
(sqrt of its area) so damage scales with the object; the weight guard is a
face-count cap checked before anything changes, not a wall-clock timeout;
gravity compares world-space normals to -Z; the open-border crumble is named
for what it does; the dead detect_sharp_vert_indices is gone.
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector

MAX_WORK = 500_000  # faces x (subdivisions + 1)^2 allowed before refusing


def has_sharp_edge(bm, sharp_angle):
    """Any edge whose two faces meet at/over the angle, or a non-manifold edge."""
    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            return True
        f0, f1 = edge.link_faces
        if f0.normal.angle(f1.normal) >= sharp_angle:
            return True
    return False


def build_influence(bm, sharp_angle, edge_width):
    """{face index: weight}. Faces touching a sharp edge start at 1.0 and
    spread face-adjacent for edge_width hops (1 - hop / (edge_width + 1))."""
    influence = {}
    frontier = set()
    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            sharp = True
        else:
            f0, f1 = edge.link_faces
            sharp = f0.normal.angle(f1.normal) >= sharp_angle
        if sharp:
            for face in edge.link_faces:
                if face.index not in influence:
                    influence[face.index] = 1.0
                    frontier.add(face.index)

    face_by_index = {face.index: face for face in bm.faces}
    for hop in range(1, edge_width + 1):
        if not frontier:
            break
        weight = 1.0 - hop / (edge_width + 1)
        next_frontier = set()
        for fidx in frontier:
            face = face_by_index.get(fidx)
            if face is None:
                continue
            for edge in face.edges:
                for adj in edge.link_faces:
                    if adj.index not in influence:
                        influence[adj.index] = weight
                        next_frontier.add(adj.index)
        frontier = next_frontier
    return influence


def inset_and_push(bm, face, depth_factor, randomness, rng):
    """Inset one face, then sink only the verts of its inner face.

    inset_individual returns the rim ring; the face passed in becomes the
    inner face. The old version pushed the returned ring, which moved the
    grid points shared with the neighbouring faces and broke the shape.
    """
    if not face.is_valid:
        return
    s = math.sqrt(max(face.calc_area(), 1e-12))
    try:
        bmesh.ops.inset_individual(
            bm, faces=[face],
            thickness=s * rng.uniform(0.1, 0.3),
            depth=0.0,
            use_even_offset=True,
        )
    except Exception:
        return
    if not face.is_valid:
        return
    d = s * depth_factor * rng.uniform(0.4, 1.0 + randomness)
    normal = face.normal.copy()
    for v in face.verts:
        jitter = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)))
        v.co += -normal * d + jitter * (d * randomness * 0.3)


def crumble(bm, strength, rng):
    """Nudge some verts along open borders (edges with a single face)."""
    border_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if not border_edges:
        return
    avg_len = sum(e.calc_length() for e in border_edges) / len(border_edges)
    verts = sorted({v for e in border_edges for v in e.verts}, key=lambda v: v.index)
    for v in verts:
        if rng.random() < 0.6:
            jitter = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-0.5, 0.2)))
            if jitter.length > 1e-9:
                jitter.normalize()
            v.co += jitter * (avg_len * strength * rng.uniform(0.3, 1.0))


class OBJECT_OT_sts_wear(bpy.types.Operator):
    """Chip faces near sharp edges and erode the rest, sized to each face; adjust with F9"""
    bl_idname = "object.sts_wear"
    bl_label = "Wear"
    bl_options = {'REGISTER', 'UNDO'}

    subdivisions: bpy.props.IntProperty(
        name="Subdivisions",
        description="Cuts added to every edge before wearing",
        default=3, min=0, max=10,
    )
    seed: bpy.props.IntProperty(
        name="Seed",
        description="Random seed, restarted for every mesh so the selection order does not matter",
        default=0,
    )
    randomness: bpy.props.FloatProperty(
        name="Randomness",
        description="Extra jitter of the pushed-in verts",
        subtype='FACTOR', default=0.3, min=0.0, max=1.0,
    )
    edge_damage: bpy.props.BoolProperty(
        name="Edge Damage",
        description="Chip faces touching and near sharp edges",
        default=True,
    )
    sharp_angle: bpy.props.FloatProperty(
        name="Sharp Angle",
        description="Edge angle counted as sharp",
        subtype='ANGLE', default=math.radians(30), min=0.0, max=math.radians(180),
    )
    edge_width: bpy.props.IntProperty(
        name="Damage Band",
        description="Face rings of edge damage that reach away from a sharp edge",
        default=2, min=0, max=10,
    )
    chip_rate: bpy.props.FloatProperty(
        name="Chip Rate",
        description="Chance per weighted face",
        subtype='FACTOR', default=0.4, min=0.0, max=1.0,
    )
    chip_depth: bpy.props.FloatProperty(
        name="Chip Depth",
        description="Push-in depth as a fraction of the face's own size",
        subtype='FACTOR', default=0.15, min=0.0, max=1.0,
    )
    erosion: bpy.props.BoolProperty(
        name="Erosion",
        description="Wear plain faces at random",
        default=True,
    )
    erosion_rate: bpy.props.FloatProperty(
        name="Erosion Rate",
        description="Base chance per plain face",
        subtype='FACTOR', default=0.05, min=0.0, max=1.0,
    )
    erosion_depth: bpy.props.FloatProperty(
        name="Erosion Depth",
        description="Push-in depth as a fraction of the face's own size",
        subtype='FACTOR', default=0.15, min=0.0, max=1.0,
    )
    gravity_bias: bpy.props.FloatProperty(
        name="Gravity Bias",
        description="Extra erosion on faces pointing down in world space",
        subtype='FACTOR', default=0.15, min=0.0, max=1.0,
    )
    crumble: bpy.props.BoolProperty(
        name="Crumble Open Borders",
        description="Nudge vertices along open borders (edges with a single face)",
        default=False,
    )
    crumble_strength: bpy.props.FloatProperty(
        name="Crumble Strength",
        description="Nudge size relative to the border edge length",
        subtype='FACTOR', default=0.3, min=0.0, max=1.0,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        context.view_layer.update()

        # Selected meshes; shared mesh data is worn once (first object gives the world rotation).
        targets = {}
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.data not in targets:
                targets[obj.data] = obj
        if not targets:
            self.report({'WARNING'}, "Select at least one mesh")
            return {'CANCELLED'}
        if not (self.edge_damage or self.erosion or self.crumble):
            self.report({'WARNING'}, "Nothing enabled: turn on Edge Damage, Erosion or Crumble")
            return {'CANCELLED'}

        # Refusals: checked before anything changes.
        for me, obj in targets.items():
            if me.shape_keys is not None:
                self.report({'WARNING'}, f"{obj.name}: shape keys — apply them first")
                return {'CANCELLED'}
            work = len(me.polygons) * (self.subdivisions + 1) ** 2
            if work > MAX_WORK:
                self.report({'WARNING'},
                            f"{obj.name}: {work:,} faces after subdividing (limit {MAX_WORK:,}) — lower Subdivisions")
                return {'CANCELLED'}
        if self.edge_damage and not self.erosion and not self.crumble:
            for me in targets:
                bm = bmesh.new()
                bm.from_mesh(me)
                sharp = has_sharp_edge(bm, self.sharp_angle)
                bm.free()
                if not sharp:
                    self.report({'WARNING'},
                                "Edge Damage only, but no edge is sharper than Sharp Angle")
                    return {'CANCELLED'}

        for me, obj in targets.items():
            self.wear_mesh(me, obj)
        return {'FINISHED'}

    def wear_mesh(self, me, obj):
        rng = random.Random(self.seed)  # restart per mesh: selection order does not matter
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        if self.subdivisions > 0:
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=self.subdivisions, use_grid_fill=True)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

        influence = build_influence(bm, self.sharp_angle, self.edge_width) if self.edge_damage else {}
        rot = obj.matrix_world.to_3x3()  # world direction of a local normal
        down = Vector((0.0, 0.0, -1.0))

        # Decide in face order (no random draws while iterating a set).
        hit = []
        for face in bm.faces:
            weight = influence.get(face.index, 0.0)
            if weight > 0.0:
                if rng.random() < self.chip_rate * weight:
                    hit.append((face, self.chip_depth * weight))
            elif self.erosion:
                downness = max(0.0, (rot @ face.normal).dot(down))
                prob = min(self.erosion_rate + downness * self.gravity_bias * 0.2, 0.98)
                if rng.random() < prob:
                    hit.append((face, self.erosion_depth))

        for face, depth_factor in hit:
            inset_and_push(bm, face, depth_factor, self.randomness, rng)

        if self.crumble:
            crumble(bm, self.crumble_strength, rng)

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
        me.update()


classes = (
    OBJECT_OT_sts_wear,
)
