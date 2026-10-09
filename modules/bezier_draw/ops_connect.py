"""Connect two Bezier curves with G1 (tangent) continuity.

Replaces: ★archive/CurveMedering/Curve_Continuity_Tool.py

The old tool copied local coordinates from one object to the other (wrong as
soon as the objects are moved or rotated), used only the first spline and took
"first / second" from the selection order. Here the closest pair of open
endpoints is found in world space, over every Bezier spline of both objects;
the other curve's end moves onto the active curve's end and its handles line up.
"""

import bpy

from ...core import curve_utils as cu


def _open_ends(obj):
    """(world position, point, is_start, neighbour point) of every open Bezier spline end."""
    mw = obj.matrix_world
    out = []
    for s in obj.data.splines:
        if s.type != 'BEZIER' or s.use_cyclic_u or len(s.bezier_points) < 2:
            continue
        pts = s.bezier_points
        out.append((mw @ pts[0].co, pts[0], True, pts[1]))
        out.append((mw @ pts[-1].co, pts[-1], False, pts[-2]))
    return out


def _outward(point, is_start):
    """Name of the handle that points away from the curve at this end."""
    return "handle_left" if is_start else "handle_right"


def _inward(point, is_start):
    return "handle_right" if is_start else "handle_left"


class CURVE_OT_sts_connect_g1(bpy.types.Operator):
    """Move the closest end of the other selected curve onto the active curve's end
and line up the handles (G1, tangent continuity)"""
    bl_idname = "curve.sts_connect_g1"
    bl_label = "Connect (G1)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and cu.is_curve(context.active_object)

    def execute(self, context):
        active = context.active_object
        others = [o for o in context.selected_objects if o is not active and cu.is_curve(o)]
        if len(others) != 1:
            self.report({'WARNING'}, "Select one more curve (the active curve stays put)")
            return {'CANCELLED'}
        other = others[0]
        ends_a, ends_b = _open_ends(active), _open_ends(other)
        if not ends_a or not ends_b:
            self.report({'WARNING'}, "Both curves need an open Bezier spline")
            return {'CANCELLED'}

        pa, pb = min(((a, b) for a in ends_a for b in ends_b), key=lambda ab: (ab[0][0] - ab[1][0]).length)
        wa, point_a, start_a, neighbour_a = pa
        _wb, point_b, start_b, _n = pb

        mwa = active.matrix_world
        mwb = other.matrix_world
        to_b = mwb.inverted()

        out_a = (mwa @ getattr(point_a, _outward(point_a, start_a))) - wa
        if out_a.length < 1e-9:      # no handle to follow: continue the last segment instead
            out_a = wa - (mwa @ neighbour_a.co)
        direction = out_a.normalized()

        # lengths are kept (measured in world space)
        wb_old = mwb @ point_b.co
        len_out_b = ((mwb @ getattr(point_b, _outward(point_b, start_b))) - wb_old).length
        len_in_b = ((mwb @ getattr(point_b, _inward(point_b, start_b))) - wb_old).length

        point_b.handle_left_type = point_b.handle_right_type = 'FREE'
        point_b.co = to_b @ wa
        # the other curve's outward handle points back into the active curve
        setattr(point_b, _outward(point_b, start_b), to_b @ (wa - direction * len_out_b))
        setattr(point_b, _inward(point_b, start_b), to_b @ (wa + direction * len_in_b))
        point_b.handle_left_type = point_b.handle_right_type = 'ALIGNED'
        other.data.update_tag()
        return {'FINISHED'}


classes = (
    CURVE_OT_sts_connect_g1,
)
