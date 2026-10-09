"""Add / remove Bezier points (Edit Mode)."""

import bpy

from ...core import curve_utils as cu


def _poll_edit_curve(context):
    return cu.is_curve(context.object) and context.mode == 'EDIT_CURVE'


def _bezier_splines(obj):
    return [s for s in obj.data.splines if s.type == 'BEZIER']


def _select_point(p, state):
    p.select_control_point = state
    p.select_left_handle = state
    p.select_right_handle = state


class CURVE_OT_sts_subdivide(bpy.types.Operator):
    """Subdivide the selected segments, or the whole curve if fewer than 2 points are selected"""
    bl_idname = "curve.sts_subdivide"
    bl_label = "Subdivide"
    bl_options = {'REGISTER', 'UNDO'}

    cuts: bpy.props.IntProperty(name="Number of Cuts", default=1, min=1, max=100)

    @classmethod
    def poll(cls, context):
        return _poll_edit_curve(context)

    def execute(self, context):
        splines = _bezier_splines(context.object)
        n_sel = sum(p.select_control_point for s in splines for p in s.bezier_points)
        if n_sel >= 2:
            bpy.ops.curve.subdivide(number_cuts=self.cuts)
        else:
            bpy.ops.curve.select_all(action='SELECT')
            bpy.ops.curve.subdivide(number_cuts=self.cuts)
            bpy.ops.curve.select_all(action='DESELECT')
        return {'FINISHED'}


class CURVE_OT_sts_decimate(bpy.types.Operator):
    """Remove points that barely change the shape (Ramer–Douglas–Peucker).
    With a selection, only runs of selected points are reduced; without one, the whole curve"""
    bl_idname = "curve.sts_decimate"
    bl_label = "Decimate"
    bl_options = {'REGISTER', 'UNDO'}

    error: bpy.props.FloatProperty(
        name="Max Deviation", default=0.001, min=0.0001, max=1.0,
        precision=4, step=0.01, unit='LENGTH',
        description="Allowed deviation from the original shape (larger = fewer points)",
    )

    @classmethod
    def poll(cls, context):
        return _poll_edit_curve(context)

    def execute(self, context):
        splines = _bezier_splines(context.object)
        any_sel = any(p.select_control_point for s in splines for p in s.bezier_points)

        # Points are deleted in place, so cyclic / handle types / material /
        # resolution of every spline stay untouched.
        remove = []    # per spline: set of indices to delete
        reselect = []  # per spline: selection state of the points that remain
        total = 0
        for s in splines:
            pts = s.bezier_points
            coords = [p.co.copy() for p in pts]
            sel = [i for i, p in enumerate(pts) if p.select_control_point]
            drop = set()
            if any_sel:
                for run in cu.contiguous_runs(sel):
                    if len(run) < 3:
                        continue
                    start = run[0]
                    keep = set(cu.rdp_indices(coords[start:run[-1] + 1], self.error))
                    drop |= {start + k for k in range(len(run)) if k not in keep}
            else:
                keep = set(cu.rdp_indices(coords, self.error))
                drop = set(range(len(pts))) - keep
            remove.append(drop)
            reselect.append([p.select_control_point for i, p in enumerate(pts) if i not in drop])
            total += len(drop)

        if total == 0:
            self.report({'INFO'}, "Nothing to decimate")
            return {'CANCELLED'}

        for s, drop in zip(splines, remove):
            for i, p in enumerate(s.bezier_points):
                _select_point(p, i in drop)
        bpy.ops.curve.delete(type='VERT')

        for s, states in zip(_bezier_splines(context.object), reselect):
            for p, state in zip(s.bezier_points, states):
                _select_point(p, state)

        self.report({'INFO'}, f"Removed {total} points")
        return {'FINISHED'}


classes = (
    CURVE_OT_sts_subdivide,
    CURVE_OT_sts_decimate,
)
