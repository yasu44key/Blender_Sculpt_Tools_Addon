"""Annotation Convert operator — annotation strokes to one Bezier curve or mesh polyline.

Replaces: Annotations_to_Bezier_Curves_14.py, Poly_Line_Tool10.py (docs/old/)

Fixes over the old versions: the 5.x annotation API (scene.annotation,
layers.active_index — the old Bezier read a nonexistent layer.active and
always converted the first layer; the old Polyline used scene.grease_pencil);
layer.active_frame is not trusted (it can be None right after opening a file,
the frame is picked from layer.frames); points are thinned with
Ramer-Douglas-Peucker for both targets (the old Polyline did not thin and had
its edge condition inverted); MESH connects the thinned points with edges and
no faces; only the new object ends up selected and active; the two operators
become one with F9-adjustable properties.
"""

import math

import bpy
from mathutils import Vector


def _point_to_line_dist(p, a, b):
    ab = b - a
    ab_len = ab.length
    if ab_len < 1e-10:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / (ab_len * ab_len)))
    return (p - (a + ab * t)).length


def _rdp_reduce(points, epsilon):
    """Ramer-Douglas-Peucker thinning of a point chain.

    Iterative: a long annotation stroke (thousands of points) would hit
    Python's recursion limit with the recursive form.
    """
    n = len(points)
    if n < 3:
        return list(points)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        max_dist, max_idx = 0.0, -1
        for k in range(i + 1, j):
            d = _point_to_line_dist(points[k], points[i], points[j])
            if d > max_dist:
                max_dist, max_idx = d, k
        if max_idx > 0 and max_dist > epsilon:
            keep[max_idx] = True
            stack.append((i, max_idx))
            stack.append((max_idx, j))
    return [p for p, k in zip(points, keep) if k]


def _is_sharp_corner(positions, i, corner_threshold_rad):
    v1 = positions[i] - positions[i - 1]
    v2 = positions[i + 1] - positions[i]
    if v1.length < 1e-10 or v2.length < 1e-10:
        return False
    cos_a = v1.normalized().dot(v2.normalized())
    return math.acos(max(-1.0, min(1.0, cos_a))) > corner_threshold_rad


def _build_bezier_spline(curve_data, positions, corner_threshold_rad):
    """Smooth (FREE, Catmull-Rom-like) handles; VECTOR where the turn is sharp."""
    n = len(positions)
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(n - 1)
    for i, pos in enumerate(positions):
        bp = spline.bezier_points[i]
        bp.co = pos
        if 0 < i < n - 1 and _is_sharp_corner(positions, i, corner_threshold_rad):
            bp.handle_left_type = 'VECTOR'
            bp.handle_right_type = 'VECTOR'
        else:
            if i == 0:
                tangent = (positions[1] - positions[0]) / 3.0
            elif i == n - 1:
                tangent = (positions[n - 1] - positions[n - 2]) / 3.0
            else:
                tangent = (positions[i + 1] - positions[i - 1]) / 6.0
            bp.handle_left = pos - tangent
            bp.handle_right = pos + tangent
            bp.handle_left_type = 'FREE'
            bp.handle_right_type = 'FREE'
    return spline


def _frame_for(layer, current_frame):
    """The frame shown at the current frame: the newest frame at or below it,
    else the first one (layer.active_frame can be None right after opening)."""
    if not layer.frames:
        return None
    best = None
    for frame in layer.frames:
        if frame.frame_number <= current_frame and (best is None or frame.frame_number > best.frame_number):
            best = frame
    return best if best is not None else layer.frames[0]


def _stroke_positions(layer, current_frame):
    """World-space point lists of the layer's strokes, chains with < 2 points skipped."""
    frame = _frame_for(layer, current_frame)
    if frame is None:
        return []
    strokes = []
    for stroke in frame.strokes:
        points = [p.co.copy() for p in stroke.points]
        if len(points) >= 2:
            strokes.append(points)
    return strokes


def _target_layers(ann, layers_mode):
    if layers_mode == 'ACTIVE':
        index = ann.layers.active_index
        if 0 <= index < len(ann.layers):
            return [ann.layers[index]]
        return []
    return [layer for layer in ann.layers if not layer.annotation_hide]


class CURVE_OT_sts_annotation_convert(bpy.types.Operator):
    """Convert annotation strokes into a Bezier curve or a mesh polyline"""
    bl_idname = "curve.sts_annotation_convert"
    bl_label = "Convert Annotation"
    bl_options = {'REGISTER', 'UNDO'}

    target: bpy.props.EnumProperty(
        name="Target",
        description="What to build from the strokes",
        items=(
            ('BEZIER', "Bezier", "One Bezier spline per stroke, thinned, smooth handles"),
            ('MESH', "Mesh", "Vertices and edges along each stroke (no faces)"),
        ),
        default='BEZIER',
    )
    layers: bpy.props.EnumProperty(
        name="Layers",
        description="Which annotation layers to convert",
        items=(
            ('ACTIVE', "Active", "Only the active layer"),
            ('VISIBLE', "Visible", "Every layer that is not hidden"),
        ),
        default='ACTIVE',
    )
    simplify: bpy.props.FloatProperty(
        name="Simplify",
        description="Maximum deviation when thinning points (0 keeps every point)",
        unit='LENGTH', default=0.02, min=0.0, soft_max=1.0, step=1, precision=4,
    )
    corner_angle: bpy.props.FloatProperty(
        name="Corner Angle",
        description="Turns sharper than this get straight (VECTOR) handles",
        subtype='ANGLE', default=math.radians(60), min=0.0, max=math.pi,
    )
    hide_after: bpy.props.BoolProperty(
        name="Hide After",
        description="Hide the converted annotation layers afterwards",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def _positions(self, points):
        return _rdp_reduce(points, self.simplify) if self.simplify > 0.0 else points

    def _make_curve(self, context, groups):
        curve_data = bpy.data.curves.new("Annotation Curve", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.resolution_u = 12
        for _layer, strokes in groups:
            for points in strokes:
                _build_bezier_spline(curve_data, self._positions(points), self.corner_angle)
        obj = bpy.data.objects.new("Annotation Curve", curve_data)
        context.collection.objects.link(obj)
        return obj

    def _make_mesh(self, context, groups):
        verts, edges = [], []
        for _layer, strokes in groups:
            for points in strokes:
                positions = self._positions(points)
                base = len(verts)
                verts.extend(tuple(p) for p in positions)
                edges.extend((base + i, base + i + 1) for i in range(len(positions) - 1))
        mesh = bpy.data.meshes.new("Annotation Polyline")
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj = bpy.data.objects.new("Annotation Polyline", mesh)
        context.collection.objects.link(obj)
        return obj

    def execute(self, context):
        ann = context.scene.annotation
        if ann is None or not ann.layers:
            self.report({'WARNING'}, "No annotation found")
            return {'CANCELLED'}

        current_frame = context.scene.frame_current
        groups = []
        for layer in _target_layers(ann, self.layers):
            strokes = _stroke_positions(layer, current_frame)
            if strokes:
                groups.append((layer, strokes))
        if not groups:
            self.report({'WARNING'}, "No annotation strokes to convert")
            return {'CANCELLED'}

        obj = self._make_curve(context, groups) if self.target == 'BEZIER' else self._make_mesh(context, groups)

        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

        if self.hide_after:
            for layer, _strokes in groups:
                layer.annotation_hide = True
        return {'FINISHED'}


classes = (
    CURVE_OT_sts_annotation_convert,
)
