bl_info = {
    "name": "Bezier Sculpt Tools (Draw/Effects + Subdivide & Decimate)",
    "blender": (4, 5, 0),
    "category": "Object",
    "author": "Yoshiki Yasunaga & ChatGPT",
    "version": (1, 5, 0),
    "description": "Bezier drawing and curve effect tools (spiral, scale, rotate, smooth/handles) plus Edit-Mode Subdivide & Decimate, unified under the 'Sculpt Tools' tab.",
}

import bpy
import math
from mathutils import Vector

# =========================================================
# Base Draw Operators
# (from BezierDraw14_9_EN; category/tab unified)
# =========================================================

class BezierDrawOperator(bpy.types.Operator):
    """Create a Bezier curve and enable Draw mode"""
    bl_idname = "curve.bezier_draw"
    bl_label = "Start Drawing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.curve.primitive_bezier_curve_add()
        curve = context.object
        curve.name = "DrawnBezier"
        curve.data.dimensions = '3D'
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.delete(type='VERT')
        context.tool_settings.curve_paint_settings.use_pressure_radius = True
        bpy.ops.wm.tool_set_by_id(name="builtin.draw")
        context.scene.tool_settings.curve_paint_settings.depth_mode = 'SURFACE'
        curve.data.bevel_depth = 0.1
        curve.data.bevel_resolution = 4
        curve.data.use_fill_caps = True
        curve.data.bevel_mode = 'ROUND'
        return {'FINISHED'}


class FinalizeBezierOperator(bpy.types.Operator):
    """Finalize the curve drawing"""
    bl_idname = "curve.finalize_bezier"
    bl_label = "Finish Drawing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


# =========================================================
# Edit-Mode Effect Operators
# (spiral with 3-point profiles, scale variation, rotate variation)
# =========================================================

class BEZIER_OT_spiral(bpy.types.Operator):
    """Arrange selected Bezier points into a spiral (Edit Mode) with 3-point radius profiles"""
    bl_idname = "curve.bezier_spiral"
    bl_label = "Spiral Points"
    bl_options = {'REGISTER', 'UNDO'}

    # --- Basic spiral controls ---
    radius: bpy.props.FloatProperty(
        name="Radius Scale", default=1.0, min=0.0,
        description="Overall radius multiplier applied to the offset profile"
    )
    turns: bpy.props.FloatProperty(
        name="Turns", default=1.0, min=0.0,
        description="Number of spiral rotations"
    )
    base_angle: bpy.props.FloatProperty(
        name="Base Angle (rad)", default=0.0,
        description="Initial phase angle of the spiral"
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[('Z','Z','Rotate in XY-plane'),
               ('Y','Y','Rotate in XZ-plane'),
               ('X','X','Rotate in YZ-plane')],
        default='Z',
        description="Axis around which to rotate"
    )

    # --- Handle restore scale ---
    handle_scale: bpy.props.FloatProperty(
        name="Handle Scale", default=1.0, min=0.0,
        description="Scale factor for control handle lengths after repositioning"
    )

    # --- Offset profile (r(t)) controls ---
    spiral_offset_mode: bpy.props.EnumProperty(
        name="Offset Profile",
        items=[
            ('LIN',        "Linear (min→max)",      "Two-point control from min to max"),
            ('TRI',        "3-Point (min–mid–max)", "Three-point linear blend at t=0,0.5,1"),
            ('TRI_SMOOTH', "3-Point Smooth",        "Three-point smooth blend at t=0,0.5,1"),
        ],
        default='LIN'
    )
    # Linear: r(t) = off_min + (off_max - off_min) * t
    spiral_off_min: bpy.props.FloatProperty(name="Offset @min", default=0.0)
    spiral_off_max: bpy.props.FloatProperty(name="Offset @max", default=1.0)
    # 3-Point: r(0)=off0, r(0.5)=off1, r(1)=off2
    spiral_off0: bpy.props.FloatProperty(name="Offset @min (0)",  default=0.0)
    spiral_off1: bpy.props.FloatProperty(name="Offset @mid (0.5)",default=1.0)
    spiral_off2: bpy.props.FloatProperty(name="Offset @max (1)",  default=0.0)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    # ---------- UI ----------
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "axis")
        layout.prop(self, "turns")
        layout.prop(self, "base_angle")
        layout.prop(self, "radius")
        layout.prop(self, "handle_scale")

        layout.separator()
        layout.prop(self, "spiral_offset_mode")
        if self.spiral_offset_mode == 'LIN':
            layout.prop(self, "spiral_off_min")
            layout.prop(self, "spiral_off_max")
        else:
            layout.prop(self, "spiral_off0")
            layout.prop(self, "spiral_off1")
            layout.prop(self, "spiral_off2")

    # ---------- helpers ----------
    def _plane_axes_from_axis(self, axis_key):
        """Return (axis_idx, plane_i, plane_j) for chosen axis."""
        if axis_key == 'Z': return 2, 0, 1
        if axis_key == 'Y': return 1, 0, 2
        return 0, 1, 2  # 'X'

    def _norm01(self, v, vmin, vmax):
        """Normalize to [0,1] with safe guard."""
        if vmax <= vmin + 1e-12:
            return 0.0
        t = (v - vmin) / (vmax - vmin)
        return max(0.0, min(1.0, t))

    def _three_point_linear(self, t, a, b, c):
        """Piecewise linear via (0,a) -> (0.5,b) -> (1,c)."""
        if t <= 0.5:
            u = (t / 0.5)
            return a*(1-u) + b*u
        else:
            u = (t - 0.5) / 0.5
            return b*(1-u) + c*u

    def _smoothstep(self, x):
        """Cubic smoothstep: 3x^2 - 2x^3."""
        return x*x*(3.0 - 2.0*x)

    def _three_point_smooth(self, t, a, b, c):
        """Piecewise smooth via smoothstep on each half."""
        if t <= 0.5:
            u = self._smoothstep(t / 0.5)
            return a*(1-u) + b*u
        else:
            u = self._smoothstep((t - 0.5) / 0.5)
            return b*(1-u) + c*u

    # ---------- main ----------
    def execute(self, context):
        obj = context.object

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue

            # target points = selected only (intuitive edit)
            pts = [p for p in spline.bezier_points if p.select_control_point]
            if not pts:
                continue

            # Save handle offsets before moving points
            offsets = [(p.handle_left - p.co, p.handle_right - p.co) for p in pts]

            axis_idx, pi, pj = self._plane_axes_from_axis(self.axis)

            # Local center = centroid of selected points
            center = Vector((0.0, 0.0, 0.0))
            for q in pts:
                center += q.co
            center /= len(pts)

            # Min/Max on chosen axis among selected points
            amin = min(q.co[axis_idx] for q in pts)
            amax = max(q.co[axis_idx] for q in pts)

            # Build radius profile r(t)
            if self.spiral_offset_mode == 'LIN':
                def r_of_t(t): return self.spiral_off_min + (self.spiral_off_max - self.spiral_off_min) * t
            elif self.spiral_offset_mode == 'TRI':
                def r_of_t(t): return self._three_point_linear(t, self.spiral_off0, self.spiral_off1, self.spiral_off2)
            else:  # 'TRI_SMOOTH'
                def r_of_t(t): return self._three_point_smooth(t, self.spiral_off0, self.spiral_off1, self.spiral_off2)

            # Reposition each selected point
            for i, p in enumerate(pts):
                co = p.co.copy()

                # t: normalized position along axis (min->max of selection)
                t = self._norm01(co[axis_idx], amin, amax)

                # Angle and radius
                ang = self.base_angle + t * self.turns * 2.0 * math.pi
                r   = self.radius * r_of_t(t)

                # Place in the plane orthogonal to chosen axis (axis component preserved)
                new_co = co.copy()
                new_co[pi] = center[pi] + r * math.cos(ang)
                new_co[pj] = center[pj] + r * math.sin(ang)
                # Keep axis_idx component (height/length)
                p.co = new_co

                # Restore handles with scaling
                off_l, off_r = offsets[i]
                p.handle_left  = new_co + off_l * self.handle_scale
                p.handle_right = new_co + off_r * self.handle_scale

        return {'FINISHED'}


class BEZIER_OT_scale_variation(bpy.types.Operator):
    """Apply per-index scale (radius) profiles to selected points"""
    bl_idname = "curve.bezier_scale_variation"
    bl_label = "Scale Variation"
    bl_options = {'REGISTER', 'UNDO'}

    min_scale: bpy.props.FloatProperty(name="Min Scale", default=1.0)
    max_scale: bpy.props.FloatProperty(name="Max Scale", default=2.0)
    cycles: bpy.props.FloatProperty(name="Cycles", default=1.0, min=0.1)

    mode: bpy.props.EnumProperty(
        name="Profile",
        items=[
            ('CONST',  "Constant",      "Keep scale constant"),
            ('LINEAR', "Linear",        "Scale min→max linearly"),
            ('SINE',   "Sine Wave",     "Sinusoidal scale with Cycles"),
            ('QUAD',   "Quadratic",     "Scale following quadratic curve"),
        ],
        default='CONST',
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        obj = context.object
        diff = self.max_scale - self.min_scale

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue
            pts = [p for p in spline.bezier_points if p.select_control_point]
            n = len(pts)
            if n == 0:
                continue

            for i, p in enumerate(pts):
                t = i/(n-1) if n>1 else 0.0
                if self.mode == 'CONST':
                    p.radius = self.min_scale
                elif self.mode == 'LINEAR':
                    p.radius = self.min_scale + diff * t
                elif self.mode == 'SINE':
                    val = 0.5*(1 + math.sin(2*math.pi*self.cycles*t))
                    p.radius = self.min_scale + diff * val
                elif self.mode == 'QUAD':
                    p.radius = self.min_scale + diff * (t*t)

        return {'FINISHED'}


class BEZIER_OT_rotate_variation(bpy.types.Operator):
    """Apply incremental rotation (tilt) to selected Bezier points"""
    bl_idname = "curve.bezier_rotate_variation"
    bl_label = "Rotate Variation"
    bl_options = {'REGISTER', 'UNDO'}

    base_angle: bpy.props.FloatProperty(name="Base Angle (rad)", default=0.0)
    angle_step: bpy.props.FloatProperty(name="Angle Step (rad)", default=0.1)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        obj = context.object
        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue
            pts = [p for p in spline.bezier_points if p.select_control_point]
            for i, p in enumerate(pts):
                p.tilt = self.base_angle + self.angle_step * i
        return {'FINISHED'}


# =========================================================
# Smooth / Handle Operator (Edit Mode)
# (ALIGNED secant direction, FREE position-preserving)
# =========================================================

class BEZIER_OT_smooth_points(bpy.types.Operator):
    """Smooth / normalize selected Bezier points"""
    bl_idname = "curve.bezier_smooth_points"
    bl_label = "Smooth Points"
    bl_options = {'REGISTER', 'UNDO'}

    # --- Checkboxes (1, 2, 3) ---
    do_unify_twist: bpy.props.BoolProperty(
        name="1) Unify Twist (tilt)",
        description="Unify twist (tilt) of selected points by averaging (applies to all points if nothing is selected)",
        default=False
    )
    do_unify_scale: bpy.props.BoolProperty(
        name="2) Unify Scale (radius)",
        description="Unify radius of selected points by averaging (applies to all points if nothing is selected)",
        default=False
    )
    do_handle_edit: bpy.props.BoolProperty(
        name="3) Set Handle Type",
        description="Choose handle type and behavior (①–④)",
        default=False
    )

    # --- Options for 3. (①②③④) ---
    handle_mode: bpy.props.EnumProperty(
        name="Handle Type",
        items=[
            ('AUTO',    "① Auto",    "Average the rotation (tilt) direction from neighbors. Handle placement is automatic"),
            ('VECTOR',  "② Vector",  "Aim handles toward neighboring points; handle length = one-third of distance to neighbor"),
            ('ALIGNED', "③ Aligned", "Keep handle lengths; align handle directions parallel to the secant (next - prev)"),
            ('FREE',    "④ Free",    "Only set handle type to Free (do not change positions)"),
        ],
        default='AUTO'
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Smooth: Select options")
        col.prop(self, "do_unify_twist")
        col.prop(self, "do_unify_scale")
        layout.separator()
        col = layout.column(align=True)
        col.prop(self, "do_handle_edit")
        sub = col.column(align=True)
        sub.enabled = self.do_handle_edit
        sub.prop(self, "handle_mode")

    # ---------- helpers ----------
    def _target_indices(self, pts):
        sel = [i for i, p in enumerate(pts) if p.select_control_point]
        return sel if sel else list(range(len(pts)))

    def _avg_neighbor_dir(self, pts, i):
        v_prev = None
        v_next = None
        co = pts[i].co
        if i > 0:
            d = pts[i-1].co - co
            if d.length_squared > 1e-12:
                v_prev = d.normalized()
        if i < len(pts)-1:
            d = pts[i+1].co - co
            if d.length_squared > 1e-12:
                v_next = d.normalized()
        if v_prev is None and v_next is None:
            return None
        if v_prev is None:
            return v_next
        if v_next is None:
            return v_prev
        v = (v_prev + v_next)
        if v.length_squared > 1e-12:
            return v.normalized()
        return v_prev

    def _distance_to_prev_next(self, pts, i):
        co = pts[i].co
        dprev = (pts[i-1].co - co).length if i > 0 else None
        dnext = (pts[i+1].co - co).length if i < len(pts)-1 else None
        return dprev, dnext

    def _tangent_dir_through_neighbors(self, pts, i):
        """Secant direction through neighbors: (next - prev). Fallback to avg."""
        if 0 < i < len(pts) - 1:
            v = pts[i+1].co - pts[i-1].co
            if v.length_squared > 1e-12:
                return v.normalized()
        return self._avg_neighbor_dir(pts, i)

    # ---------- main ----------
    def execute(self, context):
        obj = context.object

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue

            pts = spline.bezier_points
            if not pts:
                continue

            idxs = self._target_indices(pts)

            # 1) unify tilt
            if self.do_unify_twist and idxs:
                avg_tilt = sum(pts[i].tilt for i in idxs) / float(len(idxs))
                for i in idxs:
                    pts[i].tilt = avg_tilt

            # 2) unify radius
            if self.do_unify_scale and idxs:
                avg_radius = sum(pts[i].radius for i in idxs) / float(len(idxs))
                for i in idxs:
                    pts[i].radius = avg_radius

            # 3) handle mode
            if self.do_handle_edit and idxs:
                mode = self.handle_mode

                if mode == 'AUTO':
                    for i in idxs:
                        p = pts[i]
                        p.handle_left_type  = 'AUTO'
                        p.handle_right_type = 'AUTO'
                    for i in idxs:
                        n_tilts = []
                        if i > 0: n_tilts.append(pts[i-1].tilt)
                        n_tilts.append(pts[i].tilt)
                        if i < len(pts)-1: n_tilts.append(pts[i+1].tilt)
                        if n_tilts:
                            pts[i].tilt = sum(n_tilts)/len(n_tilts)

                elif mode == 'VECTOR':
                    for i in idxs:
                        p = pts[i]
                        p.handle_left_type  = 'VECTOR'
                        p.handle_right_type = 'VECTOR'
                    for i in idxs:
                        p = pts[i]
                        co = p.co
                        dprev, dnext = self._distance_to_prev_next(pts, i)
                        if i > 0:
                            dir_prev = (pts[i-1].co - co).normalized() if dprev and dprev > 1e-12 else None
                            if dir_prev:
                                p.handle_left = co + dir_prev * (dprev / 3.0)
                        if i < len(pts)-1:
                            dir_next = (pts[i+1].co - co).normalized() if dnext and dnext > 1e-12 else None
                            if dir_next:
                                p.handle_right = co + dir_next * (dnext / 3.0)

                elif mode == 'ALIGNED':
                    for i in idxs:
                        p = pts[i]
                        co = p.co
                        tan_dir = self._tangent_dir_through_neighbors(pts, i)
                        if tan_dir is None:
                            continue
                        len_l = (p.handle_left  - co).length
                        len_r = (p.handle_right - co).length
                        p.handle_right = co + tan_dir * len_r
                        p.handle_left  = co - tan_dir * len_l
                        # set type after positions to avoid re-snapping
                        p.handle_left_type  = 'ALIGNED'
                        p.handle_right_type = 'ALIGNED'

                elif mode == 'FREE':
                    for i in idxs:
                        p = pts[i]
                        hl = p.handle_left.copy()
                        hr = p.handle_right.copy()
                        p.handle_left_type  = 'FREE'
                        p.handle_right_type = 'FREE'
                        p.handle_left  = hl
                        p.handle_right = hr

        return {'FINISHED'}


# =========================================================
# Object-Mode Effects (Consolidated)
# =========================================================

class OBJECT_OT_curve_effects(bpy.types.Operator):
    """Apply various effects to all Bezier splines in Object Mode"""
    bl_idname = "curve.scale_variation"
    bl_label = "Scale Variation (Object Mode)"
    bl_options = {'REGISTER', 'UNDO'}

    # --- effect selection ---
    mode: bpy.props.EnumProperty(
        name="Effect Type",
        items=[
            ('CONST',      "Constant",        "Keep scale constant"),
            ('LINEAR',     "Linear",          "Scale min→max linearly"),
            ('SINE',       "Sine Wave",       "Sinusoidal scale with Cycles"),
            ('QUAD',       "Quadratic",       "Scale following quadratic curve"),
            ('TRI_LINEAR', "Triangle Linear", "min→max→min linearly"),
            ('TRI_SMOOTH', "Triangle Smooth", "min→max→min smoothly"),
            ('TWIST',      "Twist",           "Apply twist (tilt) from start to end"),
            ('SPIRAL',     "Spiral",          "Reposition in spiral shape (local center & profiles)"),
        ],
        default='CONST',
    )

    # scale params
    min_scale: bpy.props.FloatProperty(name="Min Scale", default=1.0)
    max_scale: bpy.props.FloatProperty(name="Max Scale", default=2.0)
    cycles: bpy.props.FloatProperty(name="Cycles", default=1.0, min=0.1)

    # twist params
    twist_base: bpy.props.FloatProperty(name="Base Angle (rad)", default=0.0)
    twist_step: bpy.props.FloatProperty(name="Angle Step (rad)", default=math.pi/16)

    # spiral (basic)
    spiral_turns:  bpy.props.FloatProperty(name="Turns", default=1.0, min=0.0)
    spiral_axis: bpy.props.EnumProperty(
        name="Spiral Axis (local)",
        items=[('Z','Z','XY-plane'),('Y','Y','XZ-plane'),('X','X','YZ-plane')],
        default='Z'
    )
    # spiral (advanced)
    spiral_base_angle: bpy.props.FloatProperty(
        name="Base Angle (rad)", default=0.0,
        description="Initial angle offset for the spiral"
    )
    spiral_offset_mode: bpy.props.EnumProperty(
        name="Offset Profile",
        items=[
            ('LIN',        "Linear (min→max)",      "Two-point control from min to max"),
            ('TRI',        "3-Point (min–mid–max)", "Three-point linear blend at t=0,0.5,1"),
            ('TRI_SMOOTH', "3-Point Smooth",        "Three-point smooth blend at t=0,0.5,1"),
        ],
        default='LIN'
    )
    spiral_off_min: bpy.props.FloatProperty(name="Offset @min", default=0.0)
    spiral_off_max: bpy.props.FloatProperty(name="Offset @max", default=1.0)
    spiral_off0: bpy.props.FloatProperty(name="Offset @min (0)",  default=0.0)
    spiral_off1: bpy.props.FloatProperty(name="Offset @mid (0.5)",default=1.0)
    spiral_off2: bpy.props.FloatProperty(name="Offset @max (1)",  default=0.0)

    # ---------- UI ----------
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mode")

        if self.mode in {'CONST','LINEAR','SINE','QUAD','TRI_LINEAR','TRI_SMOOTH'}:
            layout.prop(self, "min_scale")
            layout.prop(self, "max_scale")
            if self.mode == 'SINE':
                layout.prop(self, "cycles")

        if self.mode == 'TWIST':
            layout.prop(self, "twist_base")
            layout.prop(self, "twist_step")

        if self.mode == 'SPIRAL':
            layout.prop(self, "spiral_axis")
            layout.prop(self, "spiral_turns")
            layout.prop(self, "spiral_base_angle")
            layout.prop(self, "spiral_offset_mode")
            if self.spiral_offset_mode == 'LIN':
                layout.prop(self, "spiral_off_min")
                layout.prop(self, "spiral_off_max")
            else:
                layout.prop(self, "spiral_off0")
                layout.prop(self, "spiral_off1")
                layout.prop(self, "spiral_off2")

    # ---------- helpers ----------
    def _plane_axes_from_axis(self, axis_key):
        if axis_key == 'Z':
            return 2, 0, 1
        if axis_key == 'Y':
            return 1, 0, 2
        return 0, 1, 2

    def _norm01(self, v, vmin, vmax):
        if vmax <= vmin + 1e-12:
            return 0.0
        t = (v - vmin) / (vmax - vmin)
        return max(0.0, min(1.0, t))

    def _three_point_linear(self, t, a, b, c):
        if t <= 0.5:
            u = (t / 0.5)
            return a*(1-u) + b*u
        else:
            u = (t - 0.5) / 0.5
            return b*(1-u) + c*u

    def _smoothstep(self, x):
        return x*x*(3.0 - 2.0*x)

    def _three_point_smooth(self, t, a, b, c):
        if t <= 0.5:
            u = self._smoothstep(t / 0.5)
            return a*(1-u) + b*u
        else:
            u = self._smoothstep((t - 0.5) / 0.5)
            return b*(1-u) + c*u

    # ---------- main ----------
    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'CURVE':
            self.report({'ERROR'}, "Active object must be a Curve")
            return {'CANCELLED'}

        diff = self.max_scale - self.min_scale

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue

            pts = spline.bezier_points
            n = len(pts)
            if n == 0:
                continue

            # ----- SPIRAL: apply once per spline -----
            if self.mode == 'SPIRAL':
                axis_idx, pi, pj = self._plane_axes_from_axis(self.spiral_axis)

                sel = [p for p in pts if p.select_control_point]
                target_pts = sel if sel else list(pts)

                # local center of selection
                center = Vector((0.0, 0.0, 0.0))
                for q in target_pts:
                    center += q.co
                center /= len(target_pts)

                # axis min/max over target
                amin = min(q.co[axis_idx] for q in target_pts)
                amax = max(q.co[axis_idx] for q in target_pts)

                # radius profile
                if self.spiral_offset_mode == 'LIN':
                    def r_of_t(t): return self.spiral_off_min + (self.spiral_off_max - self.spiral_off_min) * t
                elif self.spiral_offset_mode == 'TRI':
                    def r_of_t(t): return self._three_point_linear(t, self.spiral_off0, self.spiral_off1, self.spiral_off2)
                else:
                    def r_of_t(t): return self._three_point_smooth(t, self.spiral_off0, self.spiral_off1, self.spiral_off2)

                # place all points
                for p in pts:
                    co = p.co.copy()
                    t = self._norm01(co[axis_idx], amin, amax)
                    ang = self.spiral_base_angle + t * self.spiral_turns * 2.0 * math.pi
                    r   = r_of_t(t)

                    new_co = co.copy()
                    new_co[pi] = center[pi] + r * math.cos(ang)
                    new_co[pj] = center[pj] + r * math.sin(ang)
                    # keep axis component (height/length preserved)
                    p.co = new_co

                continue  # next spline

            # ----- Other modes: per-index iterate -----
            for i, p in enumerate(pts):
                t = i/(n-1) if n>1 else 0.0
                if self.mode == 'CONST':
                    p.radius = self.min_scale
                elif self.mode == 'LINEAR':
                    p.radius = self.min_scale + diff * t
                elif self.mode == 'SINE':
                    val = 0.5*(1 + math.sin(2*math.pi*self.cycles*t))
                    p.radius = self.min_scale + diff * val
                elif self.mode == 'QUAD':
                    p.radius = self.min_scale + diff * (t*t)
                elif self.mode == 'TRI_LINEAR':
                    if t <= 0.5:
                        p.radius = self.min_scale + diff * (t/0.5)
                    else:
                        p.radius = self.max_scale - diff * ((t-0.5)/0.5)
                elif self.mode == 'TRI_SMOOTH':
                    u = (t*2.0) if t<=0.5 else (2.0*(1.0-t))
                    s = u*u*(3.0 - 2.0*u)
                    p.radius = self.min_scale + diff * s
                elif self.mode == 'TWIST':
                    p.tilt = self.twist_base + self.twist_step * t * (n-1)

        return {'FINISHED'}


# =========================================================
# Subdivide & Decimate (Edit Mode)
# (integrated from Curve_Subdivide_&_Decimate_1_0_4)
# =========================================================

# --- Ramer–Douglas–Peucker for index‐based decimation ---
def rdp_indices(points, eps):
    n = len(points)
    if n < 2:
        return list(range(n))
    keep = {0, n - 1}
    def recurse(i, j):
        A, B = points[i], points[j]
        AB = B - A
        denom = AB.length
        if denom == 0.0:
            return
        max_d, idx = 0.0, None
        for k in range(i + 1, j):
            d = (AB.cross(points[k] - A)).length / denom
            if d > max_d:
                max_d, idx = d, k
        if max_d > eps and idx is not None:
            keep.add(idx)
            recurse(i, idx)
            recurse(idx, j)
    recurse(0, n - 1)
    return sorted(keep)


class CURVE_OT_subdivide_curve(bpy.types.Operator):
    """Subdivide selected segments (or whole curve if not enough selected) in Edit Mode"""
    bl_idname = "curve.subdivide_curve"
    bl_label = "Subdivide Curve"
    bl_options = {'REGISTER', 'UNDO'}

    cuts: bpy.props.IntProperty(
        name="Number of Cuts",
        default=1, min=1, max=100,
        description="Number of cuts per segment (max 100)"
    )

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        obj = context.object
        total_sel = 0
        for spline in obj.data.splines:
            if spline.type != 'BEZIER': 
                continue
            total_sel += sum(1 for p in spline.bezier_points if p.select_control_point)

        if total_sel >= 2:
            bpy.ops.curve.subdivide(number_cuts=self.cuts)
        else:
            bpy.ops.curve.select_all(action='SELECT')
            bpy.ops.curve.subdivide(number_cuts=self.cuts)
            bpy.ops.curve.select_all(action='DESELECT')

        return {'FINISHED'}


class CURVE_OT_decimate_curve(bpy.types.Operator):
    """Decimate selected (or whole) curve using RDP in Edit Mode"""
    bl_idname = "curve.decimate_curve"
    bl_label = "Decimate Curve"
    bl_options = {'REGISTER', 'UNDO'}

    error: bpy.props.FloatProperty(
        name="Error Threshold",
        default=0.001,
        min=0.0001,
        max=1.0,
        precision=6,
        step=0.01,
        description="Ramer–Douglas–Peucker tolerance (larger removes more points)"
    )

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        obj = context.object
        data = obj.data

        # 1) Gather spline data & keep indices first
        spline_data = []
        for spline in data.splines:
            if spline.type != 'BEZIER':
                continue

            pts = spline.bezier_points
            coords = [p.co.copy() for p in pts]
            radii = [p.radius for p in pts]
            tilts = [p.tilt for p in pts]
            hl_off = [(p.handle_left - p.co) for p in pts]
            hr_off = [(p.handle_right - p.co) for p in pts]

            # selection indices
            sel_idx = [i for i, p in enumerate(pts) if p.select_control_point]
            contiguous = len(sel_idx) >= 2 and max(sel_idx) - min(sel_idx) == len(sel_idx) - 1

            if contiguous:
                start, end = min(sel_idx), max(sel_idx)
                sub_coords = coords[start:end+1]
                keep_sub = rdp_indices(sub_coords, self.error)
                # map back to full indices
                keep = []
                for i in range(len(coords)):
                    if start <= i <= end:
                        if (i - start) in keep_sub:
                            keep.append(i)
                    else:
                        keep.append(i)
                keep.sort()
            else:
                keep = rdp_indices(coords, self.error)

            spline_data.append((coords, radii, tilts, hl_off, hr_off, keep))

        # 2) remove original Bezier splines
        for spline in [s for s in data.splines if s.type == 'BEZIER']:
            data.splines.remove(spline)

        # 3) rebuild from kept points
        for coords, radii, tilts, hl_off, hr_off, keep in spline_data:
            sp = data.splines.new('BEZIER')
            sp.bezier_points.add(len(keep) - 1)
            for idx_new, idx_old in enumerate(keep):
                bp = sp.bezier_points[idx_new]
                bp.co           = coords[idx_old].copy()
                bp.radius       = radii[idx_old]
                bp.tilt         = tilts[idx_old]
                bp.handle_left  = coords[idx_old] + hl_off[idx_old]
                bp.handle_right = coords[idx_old] + hr_off[idx_old]

        return {'FINISHED'}


# =========================================================
# N-Panel: Sculpt Tools (Edit Mode Panels)
# =========================================================

from bpy.types import Panel, PropertyGroup
from bpy.props import BoolProperty, EnumProperty, PointerProperty

class BezierSmoothSettings(PropertyGroup):
    """UI state holder for Smooth Tools panel"""
    do_unify_twist: BoolProperty(
        name="1) Unify Twist (tilt)",
        description="Unify twist (tilt) of selected points by averaging (applies to all points if nothing is selected)",
        default=False
    )
    do_unify_scale: BoolProperty(
        name="2) Unify Scale (radius)",
        description="Unify radius of selected points by averaging (applies to all points if nothing is selected)",
        default=False
    )
    do_handle_edit: BoolProperty(
        name="3) Set Handle Type",
        description="Choose handle type and behavior (①–④)",
        default=False
    )
    handle_mode: EnumProperty(
        name="Handle Type",
        items=[
            ('AUTO',    "① Auto",    "Average the rotation (tilt) direction from neighbors. Handle placement is automatic"),
            ('VECTOR',  "② Vector",  "Aim handles toward neighboring points; handle length = one-third of distance to neighbor"),
            ('ALIGNED', "③ Aligned", "Keep handle lengths; align handle directions parallel to the secant (next - prev)"),
            ('FREE',    "④ Free",    "Only set handle type to Free (do not change positions)"),
        ],
        default='AUTO'
    )

class VIEW3D_PT_bezier_smooth_tools(Panel):
    """N-Panel: Sculpt Tools > Smooth Tools"""
    bl_label = "Bezier Sculpt Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sculpt Tools"
    bl_context = "curve_edit"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def draw(self, context):
        layout = self.layout
        s = context.scene.bezier_smooth_settings

        box = layout.box()
        box.label(text="Draw / Effects (Edit Mode)")
        col = box.column(align=True)
        col.operator("curve.bezier_spiral")
        col.operator("curve.bezier_scale_variation")
        col.operator("curve.bezier_rotate_variation")
        col.operator("curve.bezier_smooth_points")

        layout.separator()
        box2 = layout.box()
        box2.label(text="Smooth Options")
        col = box2.column(align=True)
        col.prop(s, "do_unify_twist")
        col.prop(s, "do_unify_scale")
        col.prop(s, "do_handle_edit")
        sub = col.column(align=True)
        sub.enabled = s.do_handle_edit
        sub.prop(s, "handle_mode")


class CURVE_PT_subdiv_decimate_panel(bpy.types.Panel):
    """N-Panel: Sculpt Tools > Subdivide & Decimate"""
    bl_label = "Curve Subdivide & Decimate"
    bl_idname = "CURVE_PT_subdiv_decimate"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt Tools'
    bl_context = "curve_edit"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Subdivide (Edit Mode):")
        layout.operator("curve.subdivide_curve")
        layout.separator()
        layout.label(text="Decimate (Edit Mode):")
        layout.operator("curve.decimate_curve")


# =========================================================
# Main Tool Panel (Object Mode gateway + all tools)
# =========================================================

class BezierToolPanel(bpy.types.Panel):
    bl_label = "Bezier Sculpt Tools"
    bl_idname = "OBJECT_PT_bezier_draw"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt Tools'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Bezier Drawing (Object Mode)")
        layout.operator("curve.bezier_draw")
        layout.operator("curve.finalize_bezier")

        layout.separator()
        layout.label(text="Object-Mode Effects")
        layout.operator("curve.scale_variation", text="Scale Variation / Twist / Spiral (Object Mode)")

        layout.separator()
        layout.label(text="Edit-Mode Shortcuts")
        row = layout.row(align=True)
        row.operator("curve.bezier_spiral")
        row.operator("curve.bezier_smooth_points")
        row = layout.row(align=True)
        row.operator("curve.subdivide_curve")
        row.operator("curve.decimate_curve")


# =========================================================
# Registration
# =========================================================

classes = [
    BezierDrawOperator,
    FinalizeBezierOperator,
    # Edit-mode operators…
    BEZIER_OT_spiral,
    BEZIER_OT_scale_variation,
    BEZIER_OT_rotate_variation,
    BEZIER_OT_smooth_points,
    CURVE_OT_subdivide_curve,
    CURVE_OT_decimate_curve,
    # Object-mode consolidated operator
    OBJECT_OT_curve_effects,
    # Panels & UI state
    BezierSmoothSettings,
    VIEW3D_PT_bezier_smooth_tools,
    CURVE_PT_subdiv_decimate_panel,
    BezierToolPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bezier_smooth_settings = bpy.props.PointerProperty(type=BezierSmoothSettings)

def unregister():
    del bpy.types.Scene.bezier_smooth_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
