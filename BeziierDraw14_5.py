bl_info = {
    "name": "Bezier Draw Tool with Effects",
    "blender": (4, 0, 0),
    "category": "Object",
    "author": "Yoshiki Yasunaga & ChatGPT",
    "version": (1, 4, 5),
    "description": "Draw Bezier curves and apply point effects: spiral, scale, rotation, smoothing, plus Object‑Mode effects",
}

import bpy
import math
from mathutils import Vector

# --- Base Draw Operators ---
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


# --- Edit‑Mode Effect Operators (unchanged) ---
class BEZIER_OT_spiral(bpy.types.Operator):
    """Arrange selected Bezier points in a spiral, with adjustable handle scaling"""
    bl_idname = "curve.bezier_spiral"
    bl_label = "Spiral Points"
    bl_options = {'REGISTER', 'UNDO'}

    radius: bpy.props.FloatProperty(
        name="Max Radius",
        default=1.0, min=0.0,
        description="最大半径"
    )
    turns: bpy.props.FloatProperty(
        name="Turns",
        default=1.0, min=0.0,
        description="スパイラルの回転数"
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ('Z','Z','Rotate in XY-plane'),
            ('Y','Y','Rotate in XZ-plane'),
            ('X','X','Rotate in YZ-plane'),
        ],
        default='Z',
        description="回転させる平面の軸"
    )
    handle_scale: bpy.props.FloatProperty(
        name="Handle Scale",
        default=1.0, min=0.0,
        description="コントロールハンドルの長さを倍率で調整"
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.object.mode == 'EDIT'

    def execute(self, context):
        obj = context.object

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue

            # 選択中のポイントと元のハンドルオフセットを取得
            pts = [p for p in spline.bezier_points if p.select_control_point]
            offsets = [(p.handle_left - p.co, p.handle_right - p.co) for p in pts]
            n = len(pts)
            if n == 0:
                continue

            for i, p in enumerate(pts):
                t = i / (n - 1) if n > 1 else 0.0
                angle = t * self.turns * 2 * math.pi
                r = t * self.radius

                # 新しい制御点位置を計算
                x = r * math.cos(angle)
                y = r * math.sin(angle)
                z = p.co.z

                if self.axis == 'Z':
                    new_co = Vector((x, y, z))
                elif self.axis == 'Y':
                    new_co = Vector((x, p.co.y, y))
                else:  # 'X'
                    new_co = Vector((p.co.x, x, y))

                p.co = new_co

                # 元のハンドルオフセットに倍率をかけて再配置
                off_l, off_r = offsets[i]
                p.handle_left  = new_co + off_l * self.handle_scale
                p.handle_right = new_co + off_r * self.handle_scale

        return {'FINISHED'}

class BEZIER_OT_scale_variation(bpy.types.Operator):
    """Apply scale variation to selected Bezier points"""
    bl_idname = "curve.bezier_scale_variation"
    bl_label = "Scale Variation"
    bl_options = {'REGISTER', 'UNDO'}

    var_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ('CONSTANT','Constant','Same scale'),
            ('LINEAR','Linear','Interpolate from min to max'),
            ('WAVE','Wave','Sinusoidal variation')
        ], default='CONSTANT'
    )
    min_scale: bpy.props.FloatProperty(name="Min Scale", default=1.0)
    max_scale: bpy.props.FloatProperty(name="Max Scale", default=2.0)
    frequency: bpy.props.FloatProperty(name="Frequency", default=1.0)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.object.mode == 'EDIT'

    def execute(self, context):
        obj = context.object

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue

            pts = [p for p in spline.bezier_points if p.select_control_point]
            n = len(pts)
            if n == 0:
                continue

            diff = self.max_scale - self.min_scale
            for i, p in enumerate(pts):
                t = i / (n - 1) if n > 1 else 0
                if self.var_type == 'CONSTANT':
                    s = self.min_scale
                elif self.var_type == 'LINEAR':
                    s = self.min_scale + diff * t
                else:  # WAVE
                    s = self.min_scale + diff * 0.5 * (1 + math.sin(2 * math.pi * self.frequency * t))
                p.radius = s

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
        return obj and obj.type == 'CURVE' and context.object.mode == 'EDIT'

    def execute(self, context):
        obj = context.object

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue

            pts = [p for p in spline.bezier_points if p.select_control_point]
            for i, p in enumerate(pts):
                p.tilt = self.base_angle + self.angle_step * i

        return {'FINISHED'}

class BEZIER_OT_smooth_points(bpy.types.Operator):
    """Smooth handles of selected Bezier points"""
    bl_idname = "curve.bezier_smooth_points"
    bl_label = "Smooth Points"
    bl_options = {'REGISTER', 'UNDO'}

    handle_mode: bpy.props.EnumProperty(
        name="Handle Mode",
        items=[
            ('AUTO',    "Auto",    "Automatic handles"),
            ('VECTOR',  "Vector",  "Vector handles toward neighbors"),
            ('ALIGNED', "Aligned", "Aligned handles between neighbors"),
            ('FREE',    "Free",    "Free handles (no auto)"),
        ],
        default='AUTO'
    )
    handle_scale: bpy.props.FloatProperty(
        name="Handle Scale",
        description="Multiply all handle lengths by this factor",
        default=1.0, min=0.0
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'CURVE' and context.object.mode == 'EDIT'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "handle_mode")
        layout.prop(self, "handle_scale")

    def execute(self, context):
        obj = context.object

        for spline in obj.data.splines:
            if spline.type != 'BEZIER':
                continue

            pts = spline.bezier_points
            sel_idxs = [i for i, p in enumerate(pts) if p.select_control_point]
            if not sel_idxs:
                continue

            # 1) ハンドルタイプを切り替え
            for i in sel_idxs:
                p = pts[i]
                p.handle_left_type  = self.handle_mode
                p.handle_right_type = self.handle_mode

            # 2) Vector モードなら方向と長さを再計算
            if self.handle_mode == 'VECTOR':
                for i in sel_idxs:
                    p = pts[i]
                    co = p.co
                    # 隣の方向ベクトル
                    dir_prev = (pts[i-1].co - co).normalized() if i > 0 else None
                    dir_next = (pts[i+1].co - co).normalized() if i < len(pts)-1 else None

                    # 長さを平均化
                    orig_l = (p.handle_left - co).length
                    orig_r = (p.handle_right - co).length
                    len_prev = (pts[i-1].handle_right - pts[i-1].co).length if dir_prev else orig_l
                    len_next = (pts[i+1].handle_left  - pts[i+1].co).length if dir_next else orig_r

                    len_l = (orig_l + len_prev) / 2.0 if dir_prev else orig_l
                    len_r = (orig_r + len_next) / 2.0 if dir_next else orig_r

                    if dir_prev:
                        p.handle_left  = co + dir_prev * len_l
                    if dir_next:
                        p.handle_right = co + dir_next * len_r

            # 3) すべての選択ポイントでハンドル長を倍率調整
            if self.handle_scale != 1.0:
                for i in sel_idxs:
                    p = pts[i]
                    co = p.co
                    off_l = p.handle_left  - co
                    off_r = p.handle_right - co
                    p.handle_left  = co + off_l * self.handle_scale
                    p.handle_right = co + off_r * self.handle_scale

        return {'FINISHED'}

# --- Object‑Mode Effect Operator ---
class OBJECT_OT_curve_effects(bpy.types.Operator):
    """Apply various effects to all Bezier splines in Object Mode"""
    bl_idname = "curve.scale_variation"
    bl_label = "Scale Variation (Object Mode)"
    bl_options = {'REGISTER', 'UNDO'}

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
            ('SPIRAL',     "Spiral",          "Reposition in spiral shape"),
        ],
        default='CONST',
    )
    # Scale params
    min_scale: bpy.props.FloatProperty(name="Min Scale", default=1.0)
    max_scale: bpy.props.FloatProperty(name="Max Scale", default=2.0)
    cycles: bpy.props.FloatProperty(name="Cycles", default=1.0, min=0.1)

    # Twist params
    twist_base: bpy.props.FloatProperty(name="Base Angle (rad)", default=0.0)
    twist_step: bpy.props.FloatProperty(name="Angle Step (rad)", default=math.pi/16)

    # Spiral params
    spiral_radius: bpy.props.FloatProperty(name="Max Radius", default=1.0)
    spiral_turns:  bpy.props.FloatProperty(name="Turns", default=1.0)
    spiral_axis: bpy.props.EnumProperty(
        name="Spiral Axis",
        items=[('Z','Z','XY-plane'),('Y','Y','XZ-plane'),('X','X','YZ-plane')],
        default='Z'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mode")
        # 共通 scale パラメータ
        if self.mode in {'CONST','LINEAR','SINE','QUAD','TRI_LINEAR','TRI_SMOOTH'}:
            layout.prop(self, "min_scale")
            layout.prop(self, "max_scale")
            if self.mode == 'SINE':
                layout.prop(self, "cycles")
        # Twist パラメータ
        if self.mode == 'TWIST':
            layout.prop(self, "twist_base")
            layout.prop(self, "twist_step")
        # Spiral パラメータ
        if self.mode == 'SPIRAL':
            layout.prop(self, "spiral_radius")
            layout.prop(self, "spiral_turns")
            layout.prop(self, "spiral_axis")

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

            # オブジェクトモードでは常に全ポイントを対象
            for i, p in enumerate(pts):
                t = i/(n-1) if n>1 else 0.0

                # 各モードの実装
                if self.mode == 'CONST':
                    p.radius = self.min_scale

                elif self.mode == 'LINEAR':
                    p.radius = self.min_scale + diff * t

                elif self.mode == 'SINE':
                    val = 0.5*(1 + math.sin(2*math.pi*self.cycles*t))
                    p.radius = self.min_scale + diff * val

                elif self.mode == 'QUAD':
                    # t^2 による二次関数的増加
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

                elif self.mode == 'SPIRAL':
                    ang = t * self.spiral_turns * 2 * math.pi
                    r   = t * self.spiral_radius
                    x = r*math.cos(ang)
                    y = r*math.sin(ang)
                    z = p.co.z
                    if self.spiral_axis == 'Z':
                        p.co = Vector((x,y,z))
                    elif self.spiral_axis == 'Y':
                        p.co = Vector((x,p.co.y,y))
                    else:
                        p.co = Vector((p.co.x,x,y))

        return {'FINISHED'}


# --- UI Panel ---
class BezierToolPanel(bpy.types.Panel):
    bl_label = "Bezier Draw Tool"
    bl_idname = "OBJECT_PT_bezier_draw"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt Tools'

    def draw(self, context):
        layout = self.layout
        layout.operator("curve.bezier_draw")
        layout.operator("curve.finalize_bezier")
        layout.separator()
        layout.operator("curve.bezier_spiral")
        layout.operator("curve.bezier_scale_variation")
        layout.operator("curve.bezier_rotate_variation")
        layout.operator("curve.bezier_smooth_points")
        layout.separator()
        layout.operator("curve.scale_variation", text="Scale Variation(Object Mode)")


# --- Registration ---
classes = [
    BezierDrawOperator,
    FinalizeBezierOperator,
    # Edit‑mode operators…
    BEZIER_OT_spiral,
    BEZIER_OT_scale_variation,
    BEZIER_OT_rotate_variation,
    BEZIER_OT_smooth_points,
    # Object‑mode consolidated operator
    OBJECT_OT_curve_effects,
    BezierToolPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
