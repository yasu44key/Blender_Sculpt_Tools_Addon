"""Thickness Guard Brush: drag over a mesh; walls thinner than the minimum are pushed out
(the same rule as Fix Thin Walls, but only under the brush, with a soft falloff).

Replaces: ★archive/min_thickness_guard/thickness_guard_brush.py
(that one measured with a neighbour search instead of the ray used everywhere else,
printed every vertex to the console and ended after a single stroke).
"""

import math

import bmesh
import bpy
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

EPS = 1e-6


class ThicknessBrushSettings(bpy.types.PropertyGroup):
    min_thickness: bpy.props.FloatProperty(
        name="Min Thickness", default=0.001, min=0.00001, soft_max=0.05, unit='LENGTH',
        description="Walls thinner than this are pushed out under the brush")
    radius: bpy.props.FloatProperty(
        name="Radius", default=0.01, min=0.00001, soft_max=1.0, unit='LENGTH',
        description="Brush radius on the surface (mouse wheel or [ ] while painting)")
    strength: bpy.props.FloatProperty(
        name="Strength", default=0.5, min=0.0, max=1.0, subtype='FACTOR',
        description="Share of the missing thickness added per dab")


def _scale(obj):
    """Mean scale of the object (local lengths x this = world lengths)."""
    s = obj.matrix_world.to_scale()
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-12)


class Session:
    """A mesh being painted: bmesh + search trees in the object's local space."""

    def __init__(self, obj):
        self.obj = obj
        self.bm = bmesh.new()
        self.bm.from_mesh(obj.data)
        self.bm.verts.ensure_lookup_table()
        self.original = [v.co.copy() for v in self.bm.verts]
        self.kd = KDTree(len(self.bm.verts))
        for v in self.bm.verts:
            self.kd.insert(v.co, v.index)
        self.kd.balance()
        self._tree()

    def _tree(self):
        self.bm.normal_update()
        self.tree = BVHTree.FromBMesh(self.bm)

    def hit(self, origin_world, direction_world):
        """First surface point under a world ray, in local space (or None)."""
        inv = self.obj.matrix_world.inverted()
        o = inv @ origin_world
        d = (inv.to_3x3() @ direction_world).normalized()
        loc, _n, _i, _d = self.tree.ray_cast(o, d)
        return loc

    def dab(self, center_local, radius_world, min_world, strength):
        """Push thin vertices within the radius; returns how many moved."""
        k = _scale(self.obj)
        radius, min_t = radius_world / k, min_world / k
        moves = []
        # the KD tree holds the stroke-start positions; pushes are tiny next to the radius
        for _co, i, _d in self.kd.find_range(center_local, radius * 1.5):
            v = self.bm.verts[i]
            dist = (v.co - center_local).length
            if dist > radius or v.normal.length < 1e-12:
                continue
            n = v.normal.normalized()
            loc, _nor, _idx, t = self.tree.ray_cast(v.co - n * EPS, -n, min_t)
            if loc is None:
                continue
            t += EPS
            if t >= min_t:
                continue
            x = dist / radius
            falloff = 1.0 - x * x * (3.0 - 2.0 * x)
            moves.append((v, n * ((min_t - t) * 0.5 * falloff * strength)))
        for v, m in moves:
            v.co += m
        if moves:
            self._tree()
            self.bm.to_mesh(self.obj.data)
            self.obj.data.update()
        return len(moves)

    def restore(self):
        for v, co in zip(self.bm.verts, self.original):
            v.co = co
        self.bm.to_mesh(self.obj.data)
        self.obj.data.update()

    def free(self):
        self.bm.free()


def guard_at(obj, center_world, radius, min_thickness, strength=1.0):
    """One dab at a world position (scripts / tests). Object Mode."""
    s = Session(obj)
    try:
        return s.dab(obj.matrix_world.inverted() @ Vector(center_world), radius, min_thickness, strength)
    finally:
        s.free()


def _draw_circle(op, _context):
    if op.center_2d is None:
        return
    cx, cy = op.center_2d
    r = max(op.radius_px, 3.0)
    pts = [(cx + r * math.cos(math.tau * i / 48), cy + r * math.sin(math.tau * i / 48)) for i in range(48)]
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": pts})
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", (1.0, 0.85, 0.1, 0.9) if op.painting else (1.0, 1.0, 1.0, 0.7))
    batch.draw(shader)
    gpu.state.blend_set('NONE')


class OBJECT_OT_sts_thickness_guard_brush(bpy.types.Operator):
    """Paint over thin walls to push them out to the minimum thickness.
LMB drag: paint / wheel or [ ]: radius / Enter or right-click: done / Esc: undo all"""
    bl_idname = "object.sts_thickness_guard_brush"
    bl_label = "Thickness Guard Brush"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH' and context.mode in {'OBJECT', 'SCULPT'}
                and context.area is not None and context.area.type == 'VIEW_3D')

    def invoke(self, context, _event):
        self.mode = context.mode
        if self.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.session = Session(context.active_object)
        self.painting = False
        self.center_2d = None
        self.radius_px = 0.0
        self.handle = bpy.types.SpaceView3D.draw_handler_add(_draw_circle, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window.cursor_modal_set('PAINT_BRUSH')
        context.area.header_text_set("LMB drag: paint   Wheel / [ ]: radius   Enter / RMB: done   Esc: undo all")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _end(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
        context.window.cursor_modal_restore()
        context.area.header_text_set(None)
        self.session.free()
        if self.mode == 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')
        context.area.tag_redraw()

    def _window_region(self, context, event):
        for r in context.area.regions:
            if r.type == 'WINDOW' and r.x <= event.mouse_x < r.x + r.width and r.y <= event.mouse_y < r.y + r.height:
                return r
        return None

    def _apply(self, context, event, paint):
        s = context.scene.sts_thickness_brush
        region = self._window_region(context, event)
        if region is None:
            self.center_2d = None
            return
        rv3d = region.data
        xy = (event.mouse_x - region.x, event.mouse_y - region.y)
        self.center_2d = xy                   # the circle is drawn in the WINDOW region
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        loc = self.session.hit(origin, direction)
        if loc is None:
            self.radius_px = 0.0
            return
        world = self.session.obj.matrix_world @ loc
        side = rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
        a = view3d_utils.location_3d_to_region_2d(region, rv3d, world)
        b = view3d_utils.location_3d_to_region_2d(region, rv3d, world + side * s.radius)
        self.radius_px = (b - a).length if a is not None and b is not None else 0.0
        if paint:
            self.session.dab(loc, s.radius, s.min_thickness, s.strength)

    def modal(self, context, event):
        context.area.tag_redraw()
        s = context.scene.sts_thickness_brush
        if event.type == 'ESC' and event.value == 'PRESS':
            self.session.restore()
            self._end(context)
            return {'CANCELLED'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'FINISHED'}
        if event.type in {'WHEELUPMOUSE', 'RIGHT_BRACKET'} and event.value == 'PRESS':
            s.radius *= 1.1
            self._apply(context, event, False)
            return {'RUNNING_MODAL'}
        if event.type in {'WHEELDOWNMOUSE', 'LEFT_BRACKET'} and event.value == 'PRESS':
            s.radius /= 1.1
            self._apply(context, event, False)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                if self._window_region(context, event) is None:
                    return {'PASS_THROUGH'}     # sidebar / header clicks still work
                self.painting = True
                self._apply(context, event, True)
            elif event.value == 'RELEASE':
                self.painting = False
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE':
            self._apply(context, event, self.painting)
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'} or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}             # orbit / pan while painting
        return {'RUNNING_MODAL'}


classes = (
    ThicknessBrushSettings,
    OBJECT_OT_sts_thickness_guard_brush,
)
