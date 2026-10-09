"""Panel Raise operator — a grooved raised panel on the selected faces, bmesh.

Replaces: panel_raise_addon.py (docs/old/)

Fixes over the old version: every setting is an operator property (F9),
nothing on the Scene; the names match what they do (the old "Groove Width"
was really the outer margin); built with bmesh instead of chained bpy.ops;
panel_height is measured from the ORIGINAL surface (0 = flush, negative =
recessed), not from the groove floor.
"""

import bmesh
import bpy
from mathutils import Matrix, Vector


def _avg_normal(faces):
    """Area-weighted average normal of a face group."""
    n = Vector((0.0, 0.0, 0.0))
    for f in faces:
        n += f.normal * f.calc_area()
    if n.length < 1e-12:
        return faces[0].normal.copy()
    n.normalize()
    return n


def _inset(bm, faces, thickness, individual):
    """Inset and return the inner faces — the faces passed in stay inside
    (the return value of inset_* is the outer band, not the inner face)."""
    faces = [f for f in faces if f.is_valid]
    if not faces or thickness <= 1e-12:
        return faces
    if individual:
        bmesh.ops.inset_individual(bm, faces=faces, thickness=thickness,
                                   depth=0.0, use_even_offset=True)
    else:
        bmesh.ops.inset_region(bm, faces=faces, thickness=thickness,
                               depth=0.0, use_even_offset=True)
    return [f for f in faces if f.is_valid]


def _push(bm, faces, amount, individual):
    """Extrude `faces` along their normal by `amount`, move the new verts,
    then delete the originals (and the edges only they used) so nothing is left inside.

    Returns the new cap faces. amount 0 -> no extrusion: the faces stay.
    """
    faces = [f for f in faces if f.is_valid]
    if not faces or abs(amount) < 1e-12:
        return faces
    groups = [[f] for f in faces] if individual else [faces]
    caps = []
    for group in groups:
        normal = _avg_normal(group)
        ret = bmesh.ops.extrude_face_region(bm, geom=group)
        verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
        new = set(verts)
        # the copies of the faces have only new verts; the side walls share old ones
        # (comparing normals would miss caps on a curved selection)
        caps += [g for g in ret["geom"]
                 if isinstance(g, bmesh.types.BMFace) and all(v in new for v in g.verts)]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(normal * amount), verts=verts)
        # 'FACES' also drops the edges between the old faces (FACES_ONLY left them loose)
        bmesh.ops.delete(bm, geom=group, context='FACES')
    return caps


def _bevel_top(bm, top, width, segments):
    """Bevel only the border edges of the panel top.

    Bevel rebuilds the faces it touches, so the top faces are found again
    afterwards: same plane, not part of the bevel band, closest to the old
    center.
    """
    # element sets, not .index: indices are stale right after extrude / bevel
    top_set = set(top)
    edges, seen = [], set()
    for f in top:
        for e in f.edges:
            if e in seen:
                continue
            seen.add(e)
            if sum(1 for lf in e.link_faces if lf in top_set) == 1:
                edges.append(e)
    if not edges:
        return top

    info = [(f.calc_center_median().copy(), f.normal.copy()) for f in top]
    geom = edges + list({v for e in edges for v in e.verts})
    ret = bmesh.ops.bevel(bm, geom=geom, offset=width, offset_type='OFFSET',
                          segments=segments, profile=0.5, affect='EDGES',
                          clamp_overlap=True)
    band = set(ret["faces"])

    result = []
    for center, normal in info:
        best, best_d = None, 1e9
        for f in bm.faces:
            if f in band or f.normal.dot(normal) < 0.99:
                continue
            c = f.calc_center_median()
            if abs((c - center).dot(normal)) > 1e-4:
                continue
            d = (c - center).length_squared
            if d < best_d:
                best, best_d = f, d
        if best is not None:
            result.append(best)
    return result


def build_panel(bm, faces, p):
    """margin inset -> groove floor -> panel inset -> panel lift -> bevel."""
    inner = _inset(bm, faces, p.margin, p.individual)
    floor = _push(bm, inner, -p.groove_depth, p.individual)
    base = _inset(bm, floor, p.groove_width, p.individual)
    top = _push(bm, base, p.groove_depth + p.panel_height, p.individual)
    if p.bevel_width > 1e-12 and top:
        top = _bevel_top(bm, top, p.bevel_width, p.bevel_segments)
    return top


class MESH_OT_sts_panel_raise(bpy.types.Operator):
    """Raise a grooved panel on the selected faces: margin, groove, panel, bevel; adjust with F9"""
    bl_idname = "mesh.sts_panel_raise"
    bl_label = "Panel Raise"
    bl_options = {'REGISTER', 'UNDO'}

    margin: bpy.props.FloatProperty(
        name="Margin",
        description="Flat band kept between the edge of the selection and the groove",
        unit='LENGTH', default=0.05, min=0.0, soft_max=1.0, precision=4,
    )
    groove_width: bpy.props.FloatProperty(
        name="Groove Width",
        description="Width of the recessed groove",
        unit='LENGTH', default=0.03, min=0.0, soft_max=1.0, precision=4,
    )
    groove_depth: bpy.props.FloatProperty(
        name="Groove Depth",
        description="How far below the original surface the groove floor sits",
        unit='LENGTH', default=0.02, min=0.0, soft_max=1.0, precision=4,
    )
    panel_height: bpy.props.FloatProperty(
        name="Panel Height",
        description="Panel top above the ORIGINAL surface (0 = flush, negative = recessed)",
        unit='LENGTH', default=0.01, soft_min=-1.0, soft_max=1.0, precision=4,
    )
    bevel_width: bpy.props.FloatProperty(
        name="Bevel Width",
        description="Bevel size on the panel top's border (0 = none)",
        unit='LENGTH', default=0.01, min=0.0, soft_max=1.0, precision=4,
    )
    bevel_segments: bpy.props.IntProperty(
        name="Bevel Segments",
        description="Cuts across the bevel (1 = flat chamfer)",
        default=2, min=1, max=8,
    )
    individual: bpy.props.BoolProperty(
        name="Each Face",
        description="One panel per selected face; off = the whole selection as one panel",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        targets = []
        for obj in context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                faces = [f for f in bm.faces if f.select]
                if faces:
                    targets.append((obj, bm, faces))
        if not targets:
            self.report({'WARNING'}, "Select the faces to raise a panel on")
            return {'CANCELLED'}

        for obj, bm, faces in targets:
            top = build_panel(bm, faces, self)
            for f in bm.faces:
                f.select_set(False)
            for f in top:
                if f.is_valid:
                    f.select_set(True)
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


classes = (
    MESH_OT_sts_panel_raise,
)
