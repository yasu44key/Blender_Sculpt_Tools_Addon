"""Align Tools operators — four operators replacing the ten AlignScripts.

Replaces: AlignScripts/Align_Edge_To_Axis.py, Align_Object_To_Multi_Select_Face.py,
Align_Object_To_Selected_Face.py, Align_Object_Z_Axis_To_Selected_Faces.py,
Origin_To_Bottom.py, Origin_To_Offset_From_Bottom.py, Snap_To_Ground.py,
Snap_To_Surface_Advanced.py, Snap_To_Under_Object.py, Transport_Transform_To_Cursor.py

Fixes over the old versions: rotations multiply matrix_world instead of
overwriting rotation_euler; origins come from world-space vertices (not
local dimensions) and move the mesh backwards so the object stays put;
non-meshes in the selection are skipped; the drop checks contact from both
sides so bumps are not missed; the cursor match keeps the scale.
"""

import bmesh
import bpy
from mathutils import Matrix, Vector

from ...core import view3d

AXIS_ITEMS = (
    ('POS_X', "+X", ""),
    ('NEG_X', "-X", ""),
    ('POS_Y', "+Y", ""),
    ('NEG_Y', "-Y", ""),
    ('POS_Z', "+Z", ""),
    ('NEG_Z', "-Z", ""),
)

AXIS_VECTORS = {
    'POS_X': Vector((1.0, 0.0, 0.0)),
    'NEG_X': Vector((-1.0, 0.0, 0.0)),
    'POS_Y': Vector((0.0, 1.0, 0.0)),
    'NEG_Y': Vector((0.0, -1.0, 0.0)),
    'POS_Z': Vector((0.0, 0.0, 1.0)),
    'NEG_Z': Vector((0.0, 0.0, -1.0)),
}


# ---------------------------------------------------------------- align to axis

class OBJECT_OT_sts_align_to_axis(bpy.types.Operator):
    """Align the selected faces' average normal (or one edge) to a world axis"""
    bl_idname = "object.sts_align_to_axis"
    bl_label = "Align to Axis"
    bl_options = {'REGISTER', 'UNDO'}

    source: bpy.props.EnumProperty(
        name="Align Source",
        description="What to align: the average normal of the selected faces, or one selected edge",
        items=(
            ('FACES', "Faces", "Average normal of the selected faces"),
            ('EDGE', "Edge", "Direction of exactly one selected edge"),
        ),
        default='FACES',
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        description="World axis to align to",
        items=AXIS_ITEMS,
        default='NEG_Z',
    )
    pivot: bpy.props.EnumProperty(
        name="Rotation Pivot",
        description="Rotate around the object origin or around the center of the selection",
        items=(
            ('ORIGIN', "Origin", "Object origin"),
            ('SELECTION', "Selection", "Center of the selection"),
        ),
        default='ORIGIN',
    )
    apply_rotation: bpy.props.BoolProperty(
        name="Apply Rotation",
        description="Bake the rotation into the mesh and zero the object rotation (location and scale stay)",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode == 'EDIT'

    def execute(self, context):
        obj = context.active_object
        # Entering Edit Mode leaves matrix_world stale (it can read without the
        # object's rotation); refresh it before computing in world space.
        context.view_layer.update()
        bm = bmesh.from_edit_mesh(obj.data)
        mw = obj.matrix_world
        axis = AXIS_VECTORS[self.axis]

        if self.source == 'FACES':
            sel = [f for f in bm.faces if f.select]
            if not sel:
                self.report({'WARNING'}, "Select the faces to align")
                return {'CANCELLED'}
            m3n = mw.to_3x3().inverted().transposed()
            n = Vector()
            for f in sel:
                n += (m3n @ f.normal).normalized()
            if n.length < 1e-8:
                self.report({'WARNING'}, "The selected faces have no average direction")
                return {'CANCELLED'}
            n.normalize()
            center = sum((f.calc_center_median() for f in sel), Vector()) / len(sel)
        else:
            sel = [e for e in bm.edges if e.select]
            if len(sel) != 1:
                self.report({'WARNING'}, "Select exactly one edge to align")
                return {'CANCELLED'}
            e = sel[0]
            n = (mw @ e.verts[1].co) - (mw @ e.verts[0].co)
            if n.length < 1e-8:
                self.report({'WARNING'}, "The selected edge has no length")
                return {'CANCELLED'}
            n.normalize()
            if n.dot(axis) < 0.0:      # an edge has two directions: take the one nearer the axis
                n = -n
            center = (e.verts[0].co + e.verts[1].co) / 2.0

        rot = n.rotation_difference(axis).to_matrix().to_4x4()
        pivot = (mw @ center) if self.pivot == 'SELECTION' else mw.translation
        mw_new = Matrix.Translation(pivot) @ rot @ Matrix.Translation(-pivot) @ mw

        if self.apply_rotation:
            loc, quat, scale = mw_new.decompose()
            S = Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0))
            try:
                bake = S.inverted() @ quat.to_matrix().to_4x4() @ S
            except ValueError:
                self.report({'WARNING'}, "Cannot bake the rotation (degenerate scale)")
                return {'CANCELLED'}
            bmesh.ops.transform(bm, matrix=bake, verts=bm.verts)
            bmesh.update_edit_mesh(obj.data)
            obj.matrix_world = Matrix.Translation(loc) @ S
        else:
            obj.matrix_world = mw_new

        return {'FINISHED'}


# ---------------------------------------------------------------- origin to bottom

class OBJECT_OT_sts_origin_to_bottom(bpy.types.Operator):
    """Move each selected mesh's origin to the bottom of its world-space bounds,
    shifting the mesh the other way so the object does not move"""
    bl_idname = "object.sts_origin_to_bottom"
    bl_label = "Origin to Bottom"
    bl_options = {'REGISTER', 'UNDO'}

    offset_ratio: bpy.props.FloatProperty(
        name="Bottom Offset Ratio",
        description="Raise the origin this fraction of the object's height above the bottom",
        default=0.0, min=0.0, max=1.0,
    )

    @classmethod
    def poll(cls, context):
        # Edit Mode keeps its own copy of the mesh; edits made here would be lost.
        return context.mode == 'OBJECT'

    def execute(self, context):
        meshes = [o for o in context.selected_objects if o.type == 'MESH' and o.data.vertices]
        if not meshes:
            self.report({'WARNING'}, "Select meshes to move the origin of")
            return {'CANCELLED'}
        shared = [o for o in meshes if o.data.users > 1]
        if shared:
            # Shifting shared mesh data would move every other user of it.
            self.report({'WARNING'}, "Skipped objects sharing mesh data: "
                        + ", ".join(o.name for o in shared))
            meshes = [o for o in meshes if o not in shared]
        for obj in meshes:
            mw = obj.matrix_world
            try:
                lin_inv = mw.to_3x3().inverted()
            except ValueError:
                continue
            wv = [mw @ v.co for v in obj.data.vertices]
            xs = [p.x for p in wv]
            ys = [p.y for p in wv]
            zs = [p.z for p in wv]
            target = Vector((
                (min(xs) + max(xs)) / 2.0,
                (min(ys) + max(ys)) / 2.0,
                min(zs) + (max(zs) - min(zs)) * self.offset_ratio,
            ))
            delta = target - mw.translation
            shift = lin_inv @ delta
            for v in obj.data.vertices:
                v.co -= shift
            obj.matrix_world = Matrix.Translation(delta) @ mw
        return {'FINISHED'}


# ---------------------------------------------------------------- drop to surface

class OBJECT_OT_sts_drop_to_surface(bpy.types.Operator):
    """Move each selected mesh along a direction until it touches a surface
    or the ground plane through the world origin"""
    bl_idname = "object.sts_drop_to_surface"
    bl_label = "Drop to Surface"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name="Drop Direction",
        description="Direction to move the object",
        items=AXIS_ITEMS,
        default='NEG_Z',
    )
    target: bpy.props.EnumProperty(
        name="Snap Target",
        description="Stop at other objects' surfaces, or at the world plane through the origin",
        items=(
            ('SURFACE', "Surface", "Other objects' surfaces"),
            ('GROUND', "Ground", "World plane through the origin, perpendicular to the direction"),
        ),
        default='SURFACE',
    )
    offset: bpy.props.FloatProperty(
        name="Contact Offset",
        description="Stop this far before contact",
        default=0.0, unit='LENGTH',
    )
    align_rotation: bpy.props.BoolProperty(
        name="Align Rotation",
        description="Rotate the object so its up matches the hit surface normal, then measure the contact again",
        default=False,
    )

    def execute(self, context):
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not meshes:
            self.report({'WARNING'}, "Select meshes to drop")
            return {'CANCELLED'}
        dir_vec = AXIS_VECTORS[self.direction]
        scene = context.scene
        depsgraph = context.evaluated_depsgraph_get()

        for obj in meshes:
            contact = self._contact(obj, dir_vec, scene, depsgraph, meshes)
            if contact is None:
                continue
            dist, normal = contact
            if self.align_rotation and normal is not None:
                mw = obj.matrix_world
                up = (mw.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
                rot = up.rotation_difference(normal).to_matrix().to_4x4()
                pivot = mw.translation
                obj.matrix_world = Matrix.Translation(pivot) @ rot @ Matrix.Translation(-pivot) @ mw
                contact = self._contact(obj, dir_vec, scene, depsgraph, meshes)
                if contact is None:
                    continue
                dist = contact[0]
            move = dist - self.offset
            if abs(move) > 1e-9:
                obj.matrix_world = Matrix.Translation(dir_vec * move) @ obj.matrix_world
        return {'FINISHED'}

    def _contact(self, obj, dir_vec, scene, depsgraph, selected):
        """Nearest contact distance along dir_vec and its world normal, or None.

        Checked from both sides: rays from this object's vertices along the
        direction, and rays from the other meshes' vertices back against this
        object (a small bump under the middle would be missed by the first).
        """
        mw = obj.matrix_world
        if self.target == 'GROUND':
            best = None
            for v in obj.data.vertices:
                t = -(mw @ v.co).dot(dir_vec)
                if best is None or t < best:
                    best = t
            if best is None:
                return None
            return best, -dir_vec

        best = None  # (distance, world normal or None, ray origin for the normal)
        for v in obj.data.vertices:
            w = mw @ v.co
            co, hit = view3d.surface_point(scene, depsgraph, w, dir_vec, fallback=w, exclude=selected)
            if not hit:
                continue
            d = (co - w).dot(dir_vec)
            if d < -1e-6 or (best is not None and d >= best[0]):
                continue
            best = (d, None, w)

        inv = mw.inverted()
        lin_inv = mw.to_3x3().inverted()
        dir_local = (lin_inv @ (-dir_vec)).normalized()
        # Only vertices inside this object's shadow along the direction can be
        # hit; checking them first keeps heavy sculpts in the scene cheap.
        lo, hi = _shadow_bounds(obj, dir_vec)
        for other in scene.objects:
            if (other is obj or other in selected or other.type != 'MESH'
                    or not other.data.vertices or not other.visible_get()):
                continue
            omw = other.matrix_world
            for v in other.data.vertices:
                w = omw @ v.co
                if not _in_shadow(w, dir_vec, lo, hi):
                    continue
                res, loc, nrm, _index = obj.ray_cast(inv @ w, dir_local)
                if not res:
                    continue
                d = (w - mw @ loc).dot(dir_vec)
                if d < -1e-6 or (best is not None and d >= best[0]):
                    continue
                best = (d, (lin_inv.transposed() @ nrm).normalized(), None)

        if best is None:
            return None
        dist, normal, origin_w = best
        if normal is None and self.align_rotation:
            normal = self._surface_normal(scene, depsgraph, origin_w, dir_vec, selected)
        return dist, normal

    def _surface_normal(self, scene, depsgraph, origin, direction, exclude):
        """World normal of the first non-excluded hit along direction (same walk as surface_point)."""
        loc = Vector(origin)
        step = direction * 1e-4
        for _ in range(32):
            hit, co, normal, _index, obj, _matrix = scene.ray_cast(depsgraph, loc, direction)
            if not hit:
                return None
            if obj in exclude:
                loc = co + step
                continue
            return normal.normalized()
        return None


def _perp_axes(dir_vec):
    """The two world axes perpendicular to an axis-aligned direction."""
    return [i for i in range(3) if abs(dir_vec[i]) < 0.5]


def _shadow_bounds(obj, dir_vec):
    axes = _perp_axes(dir_vec)
    mw = obj.matrix_world
    pts = [mw @ Vector(c) for c in obj.bound_box]
    lo = [min(p[i] for p in pts) for i in axes]
    hi = [max(p[i] for p in pts) for i in axes]
    return lo, hi


def _in_shadow(w, dir_vec, lo, hi, eps=1e-6):
    for k, i in enumerate(_perp_axes(dir_vec)):
        if w[i] < lo[k] - eps or w[i] > hi[k] + eps:
            return False
    return True


# ---------------------------------------------------------------- match cursor

class OBJECT_OT_sts_match_cursor(bpy.types.Operator):
    """Give the selected objects the 3D cursor's location and rotation, keeping their scale"""
    bl_idname = "object.sts_match_cursor"
    bl_label = "Match Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    use_location: bpy.props.BoolProperty(
        name="Use Cursor Location",
        description="Move the objects to the 3D cursor",
        default=True,
    )
    use_rotation: bpy.props.BoolProperty(
        name="Use Cursor Rotation",
        description="Rotate the objects like the 3D cursor",
        default=True,
    )

    def execute(self, context):
        objs = context.selected_objects
        if not objs:
            self.report({'WARNING'}, "Select objects to match the cursor")
            return {'CANCELLED'}
        cursor = context.scene.cursor
        for obj in objs:
            loc, rot, scale = obj.matrix_world.decompose()
            new_loc = Vector(cursor.location) if self.use_location else loc
            new_rot = cursor.rotation_euler.to_matrix() if self.use_rotation else rot.to_matrix()
            obj.matrix_world = (Matrix.Translation(new_loc) @ new_rot.to_4x4()
                                @ Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0)))
        return {'FINISHED'}


classes = (
    OBJECT_OT_sts_align_to_axis,
    OBJECT_OT_sts_origin_to_bottom,
    OBJECT_OT_sts_drop_to_surface,
    OBJECT_OT_sts_match_cursor,
)
