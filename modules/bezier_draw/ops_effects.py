"""Shape effects for Bezier curves.

Every effect works in both modes:
  Edit Mode   -> selected control points
  Object Mode -> all points of the active curve
"""

import math

import bpy
from mathutils import Vector

from ...core import curve_utils as cu


class _CurveEffect:
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return cu.poll_curve_object_or_edit(context)

    def execute(self, context):
        sets = cu.target_point_sets(context)
        if not sets:
            self.report({'WARNING'}, "No Bezier points selected")
            return {'CANCELLED'}
        for spline, idx in sets:
            self.apply(spline.bezier_points, idx)
        context.object.data.update_tag()
        return {'FINISHED'}


class CURVE_OT_sts_spiral(_CurveEffect, bpy.types.Operator):
    """Arrange the points into a spiral around their center"""
    bl_idname = "curve.sts_spiral"
    bl_label = "Spiral"

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[('Z', "Z", "Spiral in the XY plane"),
               ('Y', "Y", "Spiral in the XZ plane"),
               ('X', "X", "Spiral in the YZ plane")],
        default='Z',
    )
    parameter: bpy.props.EnumProperty(
        name="Progress By",
        items=[('INDEX', "Point Order", "Angle advances along the point order (works on flat curves)"),
               ('AXIS', "Axis Position", "Angle follows each point's height on the axis")],
        default='INDEX',
    )
    turns: bpy.props.FloatProperty(name="Turns", default=1.0, min=0.0)
    base_angle: bpy.props.FloatProperty(name="Start Angle", default=0.0, subtype='ANGLE')
    radius: bpy.props.FloatProperty(name="Radius Multiplier", default=1.0, min=0.0)
    radius_mode: bpy.props.EnumProperty(
        name="Radius Profile",
        items=[('LIN', "Linear", "Min to Max"),
               ('TRI', "3-Point Linear", "Values at start / middle / end"),
               ('TRI_SMOOTH', "3-Point Smooth", "Values at start / middle / end, smooth")],
        default='LIN',
    )
    r_min: bpy.props.FloatProperty(name="Min", default=0.0)
    r_max: bpy.props.FloatProperty(name="Max", default=1.0)
    r_start: bpy.props.FloatProperty(name="Start", default=0.0)
    r_mid: bpy.props.FloatProperty(name="Middle", default=1.0)
    r_end: bpy.props.FloatProperty(name="End", default=0.0)
    handle_scale: bpy.props.FloatProperty(name="Handle Scale", default=1.0, min=0.0)

    def _radius_at(self, t):
        if self.radius_mode == 'LIN':
            r = self.r_min + (self.r_max - self.r_min) * t
        elif self.radius_mode == 'TRI':
            r = cu.three_point_linear(t, self.r_start, self.r_mid, self.r_end)
        else:
            r = cu.three_point_smooth(t, self.r_start, self.r_mid, self.r_end)
        return r * self.radius

    def apply(self, pts, idx):
        axis_i, pi, pj = {'Z': (2, 0, 1), 'Y': (1, 0, 2), 'X': (0, 1, 2)}[self.axis]
        center = sum((pts[i].co for i in idx), Vector()) / len(idx)
        amin = min(pts[i].co[axis_i] for i in idx)
        amax = max(pts[i].co[axis_i] for i in idx)
        for k, i in enumerate(idx):
            p = pts[i]
            if self.parameter == 'AXIS':
                t = cu.norm01(p.co[axis_i], amin, amax)
            else:
                t = cu.param_t(k, len(idx))
            ang = self.base_angle + t * self.turns * math.tau
            r = self._radius_at(t)
            co = p.co.copy()
            co[pi] = center[pi] + r * math.cos(ang)
            co[pj] = center[pj] + r * math.sin(ang)
            cu.set_point_co(p, co, self.handle_scale)

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column(align=True)
        col.prop(self, "axis")
        col.prop(self, "parameter")
        col.prop(self, "turns")
        col.prop(self, "base_angle")
        col = layout.column(align=True)
        col.prop(self, "radius")
        col.prop(self, "radius_mode")
        if self.radius_mode == 'LIN':
            col.prop(self, "r_min")
            col.prop(self, "r_max")
        else:
            col.prop(self, "r_start")
            col.prop(self, "r_mid")
            col.prop(self, "r_end")
        layout.prop(self, "handle_scale")


class CURVE_OT_sts_radius_profile(_CurveEffect, bpy.types.Operator):
    """Set point radius (thickness) along the curve with a profile"""
    bl_idname = "curve.sts_radius_profile"
    bl_label = "Radius Profile"

    mode: bpy.props.EnumProperty(name="Change Pattern", items=cu.PROFILE_ITEMS, default='LINEAR')
    min_value: bpy.props.FloatProperty(name="Min", default=0.5, min=0.0)
    max_value: bpy.props.FloatProperty(name="Max", default=2.0, min=0.0)
    cycles: bpy.props.FloatProperty(name="Wave Count", default=1.0, min=0.1)

    def apply(self, pts, idx):
        n = len(idx)
        for k, i in enumerate(idx):
            pts[i].radius = cu.profile_value(
                self.mode, cu.param_t(k, n), self.min_value, self.max_value, self.cycles)


class CURVE_OT_sts_tilt_step(_CurveEffect, bpy.types.Operator):
    """Twist the curve: each point is tilted a little more than the previous one"""
    bl_idname = "curve.sts_tilt_step"
    bl_label = "Twist"

    base_angle: bpy.props.FloatProperty(name="Start Angle", default=0.0, subtype='ANGLE')
    angle_step: bpy.props.FloatProperty(
        name="Step per Point", default=math.pi / 16, subtype='ANGLE')

    def apply(self, pts, idx):
        for k, i in enumerate(idx):
            pts[i].tilt = self.base_angle + self.angle_step * k


class CURVE_OT_sts_smooth_handles(_CurveEffect, bpy.types.Operator):
    """Set handle type, and optionally even out tilt and radius"""
    bl_idname = "curve.sts_smooth_handles"
    bl_label = "Smooth / Handles"

    unify_tilt: bpy.props.BoolProperty(name="Average Tilt", default=False)
    unify_radius: bpy.props.BoolProperty(name="Average Radius", default=False)
    set_handles: bpy.props.BoolProperty(name="Set Handle Type", default=True)
    handle_mode: bpy.props.EnumProperty(
        name="Handle Type",
        items=[('AUTO', "Auto", "Automatic handles; tilt is smoothed with neighbours"),
               ('VECTOR', "Vector", "Handles point at the neighbouring points"),
               ('ALIGNED', "Aligned", "Keep lengths, align with the neighbours' direction"),
               ('FREE', "Free", "Free handles without moving them")],
        default='AUTO',
    )
    handle_scale: bpy.props.FloatProperty(name="Handle Scale", default=1.0, min=0.0)

    @staticmethod
    def _tangent(pts, i):
        n = len(pts)
        a = pts[i - 1].co if i > 0 else pts[i].co
        b = pts[i + 1].co if i < n - 1 else pts[i].co
        v = b - a
        return v.normalized() if v.length_squared > 1e-12 else None

    def apply(self, pts, idx):
        n = len(pts)
        if self.unify_tilt:
            avg = sum(pts[i].tilt for i in idx) / len(idx)
            for i in idx:
                pts[i].tilt = avg
        if self.unify_radius:
            avg = sum(pts[i].radius for i in idx) / len(idx)
            for i in idx:
                pts[i].radius = avg
        if not self.set_handles:
            return

        m = self.handle_mode
        if m == 'AUTO':
            tilts = [p.tilt for p in pts]
            for i in idx:
                pts[i].handle_left_type = pts[i].handle_right_type = 'AUTO'
                nb = tilts[max(0, i - 1):min(n, i + 2)]
                pts[i].tilt = sum(nb) / len(nb)
        elif m == 'VECTOR':
            for i in idx:
                pts[i].handle_left_type = pts[i].handle_right_type = 'VECTOR'
        elif m == 'ALIGNED':
            for i in idx:
                p = pts[i]
                tan = self._tangent(pts, i)
                if tan is None:
                    continue
                len_l = (p.handle_left - p.co).length
                len_r = (p.handle_right - p.co).length
                p.handle_left_type = p.handle_right_type = 'FREE'
                p.handle_left = p.co - tan * len_l
                p.handle_right = p.co + tan * len_r
                p.handle_left_type = p.handle_right_type = 'ALIGNED'
        elif m == 'FREE':
            for i in idx:
                p = pts[i]
                hl, hr = p.handle_left.copy(), p.handle_right.copy()
                p.handle_left_type = p.handle_right_type = 'FREE'
                p.handle_left, p.handle_right = hl, hr

        if self.handle_scale != 1.0 and m in {'ALIGNED', 'FREE'}:
            for i in idx:
                p = pts[i]
                p.handle_left = p.co + (p.handle_left - p.co) * self.handle_scale
                p.handle_right = p.co + (p.handle_right - p.co) * self.handle_scale

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "unify_tilt")
        layout.prop(self, "unify_radius")
        layout.prop(self, "set_handles")
        col = layout.column()
        col.enabled = self.set_handles
        col.prop(self, "handle_mode")
        sub = col.column()
        sub.enabled = self.handle_mode in {'ALIGNED', 'FREE'}
        sub.prop(self, "handle_scale")


classes = (
    CURVE_OT_sts_spiral,
    CURVE_OT_sts_radius_profile,
    CURVE_OT_sts_tilt_step,
    CURVE_OT_sts_smooth_handles,
)
