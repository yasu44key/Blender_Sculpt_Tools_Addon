bl_info = {
    "name": "Curve Subdivide & Decimate",
    "author": "Yoshiki Yasunaga, ChatGPT",
    "version": (1, 0, 4),
    "blender": (4, 0, 0),
    "location": "View3D > UI > Sculpt Tools",
    "description": "選択／非選択に応じて部分または全体を Edit Mode のまま subdivide & decimate",
    "wiki_url":    "https://note.com/yoshiki_yasunaga",
    "tracker_url": "https://github.com/yasu44key/curve-subdivide-decimate/issues",
    "category": "Object",
}

import bpy
from mathutils import Vector

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


# --- Subdivide Operator (Edit Mode) ---
class CURVE_OT_subdivide_curve(bpy.types.Operator):
    """Edit Mode で選択または全体のカーブを細分化"""
    bl_idname = "curve.subdivide_curve"
    bl_label = "Subdivide Curve"
    bl_options = {'REGISTER', 'UNDO'}

    cuts: bpy.props.IntProperty(
        name="Number of Cuts",
        default=1, min=1, max=100,
        description="各セグメントを何分割するか（最大100）"
    )

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        obj = context.object
        total_sel = 0
        for spline in obj.data.splines:
            if spline.type != 'BEZIER': continue
            total_sel += sum(1 for p in spline.bezier_points if p.select_control_point)

        if total_sel >= 2:
            bpy.ops.curve.subdivide(number_cuts=self.cuts)
        else:
            bpy.ops.curve.select_all(action='SELECT')
            bpy.ops.curve.subdivide(number_cuts=self.cuts)
            bpy.ops.curve.select_all(action='DESELECT')

        return {'FINISHED'}


# --- Decimate Operator (Edit Mode) ---
class CURVE_OT_decimate_curve(bpy.types.Operator):
    """Edit Mode で選択または全体のカーブを RDP デシメート"""
    bl_idname = "curve.decimate_curve"
    bl_label = "Decimate Curve"
    bl_options = {'REGISTER', 'UNDO'}

    error: bpy.props.FloatProperty(
        name="Error Threshold",
        default=0.001,           # 初期値を0.001に
        min=0.0001,              # 必要に応じて最小値を0.0001などに
        max=1.0,
        precision=6,             # 小数点以下6桁まで表示
        step=0.01,              # ← ここで矢印ボタン１回あたりの増減量を設定
        description="RDP の許容誤差 (大きいほどポイントが減少)"
    )

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CURVE' and context.mode == 'EDIT_CURVE'

    def execute(self, context):
        obj = context.object
        data = obj.data

        # 1) 各 BEZIER スプラインのデータと keep インデックスを先に収集
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

            # 選択されたインデックスを取得
            sel_idx = [i for i, p in enumerate(pts) if p.select_control_point]
            contiguous = len(sel_idx) >= 2 and max(sel_idx) - min(sel_idx) == len(sel_idx) - 1

            if contiguous:
                start, end = min(sel_idx), max(sel_idx)
                sub_coords = coords[start:end+1]
                keep_sub = rdp_indices(sub_coords, self.error)
                # 全体インデックスにマッピング
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

        # 2) 元の BEZIER スプラインをすべて削除
        for spline in [s for s in data.splines if s.type == 'BEZIER']:
            data.splines.remove(spline)

        # 3) 収集したデータから再構築
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


# --- UI Panel ---
class CURVE_PT_subdiv_decimate_panel(bpy.types.Panel):
    bl_label = "Curve Subdivide & Decimate"
    bl_idname = "CURVE_PT_subdiv_decimate"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt Tools'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Subdivide (Edit Mode):")
        layout.operator("curve.subdivide_curve")
        layout.separator()
        layout.label(text="Decimate (Edit Mode):")
        layout.operator("curve.decimate_curve")


# --- Registration ---
classes = (
    CURVE_OT_subdivide_curve,
    CURVE_OT_decimate_curve,
    CURVE_PT_subdiv_decimate_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
