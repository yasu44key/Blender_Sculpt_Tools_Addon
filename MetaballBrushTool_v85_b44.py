bl_info = {
    "name": "Metaball Brush Tool v8.5",
    "author": "ChatGPT & User",
    "version": (8, 5, 0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Sculpt Tools",
    "description": "Metaball painting with pressure curve, stroke-undo, snap/cursor/view depth placement, mirror X/Y/Z, and GPU preview.",
    "category": "Object",
}

import bpy
import time
import math
from mathutils import Vector
from bpy.props import FloatProperty, PointerProperty, EnumProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy_extras import view3d_utils
import gpu
from gpu_extras.batch import batch_for_shader


# -----------------------------
# Properties
# -----------------------------
class MetaballBrushProperties(PropertyGroup):
    draw_mode: EnumProperty(
        name="Draw Mode",
        items=[
            ('VIEW',   "View Depth",       "Use view direction with fixed depth"),
            ('CURSOR', "3D Cursor Depth",  "Align depth to 3D cursor"),
            ('SNAP',   "Snap (Raycast)",   "Raycast to scene (ignores current stroke object)"),
        ],
        default='CURSOR'
    )
    undo_mode: EnumProperty(
        name="Undo Mode",
        items=[
            ('STROKE',  "Per Stroke",  "Undo once per pen-up (stroke boundary)"),
            ('ELEMENT', "Per Element", "Undo each element (every placement)"),
        ],
        default='STROKE'
    )
    # サイズ
    min_size: FloatProperty(name="Min Size", default=0.25, min=0.01, max=10.0)
    max_size: FloatProperty(name="Max Size", default=1.0, min=0.05, max=10.0)  # ★デフォルト1.0
    pressure_curve: FloatProperty(
        name="Pressure Curve",
        default=0.5, min=0.1, max=2.0,
        description="Pressure sensitivity ( <1 = smoother, >1 = sharper )"
    )
    # 配置
    interval: FloatProperty(name="Interval (s)", default=0.10, min=0.01, max=2.0)
    resolution: FloatProperty(name="Resolution", default=0.10, min=0.01, max=1.0)
    view_depth: FloatProperty(name="View Depth", default=10.0, min=0.1, max=100.0)
    # ミラー
    mirror_x: BoolProperty(name="X", default=False, description="Mirror across local X=0 plane")
    mirror_y: BoolProperty(name="Y", default=False, description="Mirror across local Y=0 plane")
    mirror_z: BoolProperty(name="Z", default=False, description="Mirror across local Z=0 plane")


# -----------------------------
# Main modal painter
# -----------------------------
class MetaballBrushOperator(Operator):
    bl_idname = "object.metaball_brush_v85"
    bl_label = "Start Metaball Brush v8.5"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _obj = None
    _last_time = 0.0
    _mouse_down = False
    _last_mouse = (0, 0)
    _last_pressure = 0.0
    _draw_handle = None

    # ---------- modal loop ----------
    def modal(self, context, event):
        props = context.scene.metaball_brush_props

        if event.type == 'TIMER':
            if self._mouse_down and (time.time() - self._last_time) >= props.interval:
                self.add_metaball(context, *self._last_mouse, self._last_pressure)
                self._last_time = time.time()
            return {'RUNNING_MODAL'}

        elif event.type == 'MOUSEMOVE':
            self._last_mouse = (event.mouse_region_x, event.mouse_region_y)
            if hasattr(event, "pressure"):
                # 一部デバイスでは MOUSEMOVE 時に 0.0 が来ることがあるが、直近の値として保持
                self._last_pressure = event.pressure
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self._mouse_down = True
                self._last_pressure = getattr(event, "pressure", 0.0)

                mb = bpy.data.metaballs.new("MetaStroke")
                mb.resolution = props.resolution
                obj = bpy.data.objects.new("MetaStroke", mb)
                context.collection.objects.link(obj)
                context.view_layer.objects.active = obj
                obj.select_set(True)
                self._obj = obj

            elif event.value == 'RELEASE':
                self._mouse_down = False
                if props.undo_mode == 'STROKE':
                    try:
                        bpy.ops.ed.undo_push(message="Metaball Stroke")
                    except Exception:
                        pass
                self._obj = None
            return {'RUNNING_MODAL'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    # ---------- add one metaball element (with mirror & pressure curve) ----------
    def add_metaball(self, context, x, y, pressure):
        props = context.scene.metaball_brush_props
        region = context.region
        rv3d = context.region_data

        if not rv3d or self._obj is None or self._obj.type != 'META':
            return

        try:
            origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, (x, y))
            direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, (x, y))
        except Exception:
            return

        # --- 決定位置（ワールド座標） ---
        if props.draw_mode == 'VIEW':
            location_world = origin + direction * props.view_depth
        elif props.draw_mode == 'CURSOR':
            cursor = context.scene.cursor.location
            location_world = view3d_utils.region_2d_to_location_3d(region, rv3d, (x, y), cursor)
        elif props.draw_mode == 'SNAP':
            depsgraph = context.evaluated_depsgraph_get()
            nearest_hit_dist = None
            nearest_hit_loc = None
            for obj in context.visible_objects:
                if obj == self._obj:
                    continue
                try:
                    eval_obj = obj.evaluated_get(depsgraph)
                    mat_inv = eval_obj.matrix_world.inverted()
                    ro = mat_inv @ origin
                    rd = (mat_inv.to_3x3() @ direction).normalized()
                    hit, loc, normal, face_index = eval_obj.ray_cast(ro, rd)
                    if hit:
                        world_loc = eval_obj.matrix_world @ loc
                        dist = (world_loc - origin).length
                        if nearest_hit_dist is None or dist < nearest_hit_dist:
                            nearest_hit_dist = dist
                            nearest_hit_loc = world_loc
                except Exception:
                    continue
            location_world = nearest_hit_loc if nearest_hit_loc else (origin + direction * props.view_depth)
        else:
            location_world = origin + direction * props.view_depth

        # --- 半径（筆圧カーブ適用：マウス=Max, ペン=Min→Max） ---
        if pressure and pressure > 0.0:
            adj = pressure ** props.pressure_curve
            radius = props.min_size + (props.max_size - props.min_size) * adj
        else:
            radius = props.max_size

        # --- ローカル座標に変換してミラー配置 ---
        mw_inv = self._obj.matrix_world.inverted()
        base_local = mw_inv @ location_world  # Vector

        # ミラーの符号セット（選択された軸の全組み合わせを生成）
        signs = [(1.0, 1.0, 1.0)]
        if props.mirror_x:
            signs = signs + [(-sx, sy, sz) for (sx, sy, sz) in signs]
        if props.mirror_y:
            signs = signs + [(sx, -sy, sz) for (sx, sy, sz) in signs]
        if props.mirror_z:
            signs = signs + [(sx, sy, -sz) for (sx, sy, sz) in signs]

        # 重複回避のため位置キー（丸め）で集合管理
        placed_keys = set()
        for sx, sy, sz in signs:
            local = Vector((base_local.x * sx, base_local.y * sy, base_local.z * sz))
            key = (round(local.x, 7), round(local.y, 7), round(local.z, 7))
            if key in placed_keys:
                continue
            placed_keys.add(key)

            try:
                elem = self._obj.data.elements.new(type='BALL')
                elem.co = local             # ★ローカル座標で配置
                elem.radius = radius
            except Exception:
                pass

        try:
            self._obj.data.resolution = props.resolution
            self._obj.data.update()
            if props.undo_mode == 'ELEMENT':
                bpy.ops.ed.undo_push(message="Add Metaball Element(s)")
        except Exception:
            pass

    # ---------- GPU preview (pressure curve only; no mirror preview to keep it simple) ----------
    def draw_preview(self, context):
        if not context.region:
            return
        x, y = self._last_mouse
        props = context.scene.metaball_brush_props

        if self._last_pressure and self._last_pressure > 0.0:
            adj = self._last_pressure ** props.pressure_curve
            radius = props.min_size + (props.max_size - props.min_size) * adj
        else:
            radius = props.max_size

        r_px = int(20 + 15 * radius)
        r_px = max(12, min(120, r_px))

        verts = [(x + r_px * math.cos(2*math.pi*i/48),
                  y + r_px * math.sin(2*math.pi*i/48)) for i in range(48)]

        shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": verts})

        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", (1.0, 1.0, 1.0, 0.7))
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    # ---------- invoke / finish ----------
    def invoke(self, context, event):
        props = context.scene.metaball_brush_props
        self._obj = None
        self._last_mouse = (event.mouse_region_x, event.mouse_region_y)
        self._mouse_down = False
        self._last_pressure = getattr(event, "pressure", 0.0)
        self._last_time = time.time()

        wm = context.window_manager
        self._timer = wm.event_timer_add(props.interval, window=context.window)
        wm.modal_handler_add(self)

        if self._draw_handle is None:
            self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw_preview, (context,), 'WINDOW', 'POST_PIXEL'
            )
        return {'RUNNING_MODAL'}

    def finish(self, context):
        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        if self._draw_handle:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            except Exception:
                pass
            self._draw_handle = None
        self._obj = None


# -----------------------------
# UI Panel
# -----------------------------
class VIEW3D_PT_metaball_brush_panel(Panel):
    bl_label = "Metaball Brush Tool v8.5"
    bl_idname = "VIEW3D_PT_metaball_brush_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sculpt Tools"

    def draw(self, context):
        props = context.scene.metaball_brush_props
        layout = self.layout

        layout.operator("object.metaball_brush_v85", text="Start Brush (v8.5)", icon='BRUSH_DATA')
        layout.prop(props, "undo_mode")
        layout.prop(props, "draw_mode")

        box = layout.box()
        box.label(text="Size / Pressure")
        box.prop(props, "min_size")
        box.prop(props, "max_size")
        box.prop(props, "pressure_curve")

        box.separator()
        box.label(text="Placement")
        box.prop(props, "interval")
        box.prop(props, "resolution")
        if props.draw_mode == 'VIEW':
            box.prop(props, "view_depth")

        box.separator()
        box.label(text="Mirror (local origin)")
        row = box.row(align=True)
        row.prop(props, "mirror_x")
        row.prop(props, "mirror_y")
        row.prop(props, "mirror_z")

        box.separator()
        box.label(text="Controls:")
        box.label(text=" - End: ESC / Right Click", icon='INFO')
        box.label(text=" - Undo: Ctrl+Z", icon='LOOP_BACK')


# -----------------------------
# Register
# -----------------------------
classes = (
    MetaballBrushProperties,
    MetaballBrushOperator,
    VIEW3D_PT_metaball_brush_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.metaball_brush_props = PointerProperty(type=MetaballBrushProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.metaball_brush_props

if __name__ == "__main__":
    register()
