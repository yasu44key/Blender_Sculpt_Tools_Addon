"""Bezier-curve helpers shared by curve modules."""

import math

import bpy


# ---------------------------------------------------------------------------
# Profiles: map t in [0, 1] to a value
# ---------------------------------------------------------------------------

def smoothstep(x):
    return x * x * (3.0 - 2.0 * x)


def norm01(v, vmin, vmax):
    if vmax <= vmin + 1e-12:
        return 0.0
    return max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))


def three_point_linear(t, a, b, c):
    if t <= 0.5:
        u = t / 0.5
        return a * (1.0 - u) + b * u
    u = (t - 0.5) / 0.5
    return b * (1.0 - u) + c * u


def three_point_smooth(t, a, b, c):
    if t <= 0.5:
        u = smoothstep(t / 0.5)
        return a * (1.0 - u) + b * u
    u = smoothstep((t - 0.5) / 0.5)
    return b * (1.0 - u) + c * u


PROFILE_ITEMS = [
    ('CONST',      "Constant",        "Same value everywhere (Min)"),
    ('LINEAR',     "Linear",          "Min to Max"),
    ('SINE',       "Sine Wave",       "Oscillate between Min and Max (Wave Count)"),
    ('QUAD',       "Quadratic",       "Ease-in from Min to Max"),
    ('TRI_LINEAR', "Triangle Linear", "Min to Max to Min"),
    ('TRI_SMOOTH', "Triangle Smooth", "Min to Max to Min, smooth"),
]


def profile_value(mode, t, vmin, vmax, cycles=1.0):
    diff = vmax - vmin
    if mode == 'LINEAR':
        return vmin + diff * t
    if mode == 'SINE':
        return vmin + diff * 0.5 * (1.0 + math.sin(2.0 * math.pi * cycles * t))
    if mode == 'QUAD':
        return vmin + diff * t * t
    if mode == 'TRI_LINEAR':
        u = t * 2.0 if t <= 0.5 else 2.0 * (1.0 - t)
        return vmin + diff * u
    if mode == 'TRI_SMOOTH':
        u = t * 2.0 if t <= 0.5 else 2.0 * (1.0 - t)
        return vmin + diff * smoothstep(u)
    return vmin


def param_t(i, n):
    """0..1 position of the i-th of n items."""
    return i / (n - 1) if n > 1 else 0.0


# ---------------------------------------------------------------------------
# Ramer–Douglas–Peucker
# ---------------------------------------------------------------------------

def rdp_indices(points, eps):
    """Indices of ``points`` (Vectors) to keep. Iterative, so long strokes
    cannot hit Python's recursion limit."""
    n = len(points)
    if n < 3:
        return list(range(n))
    keep = {0, n - 1}
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        ab = points[j] - points[i]
        denom = ab.length
        max_d, idx = 0.0, None
        for k in range(i + 1, j):
            if denom == 0.0:
                d = (points[k] - points[i]).length
            else:
                d = ab.cross(points[k] - points[i]).length / denom
            if d > max_d:
                max_d, idx = d, k
        if idx is not None and max_d > eps:
            keep.add(idx)
            stack.append((i, idx))
            stack.append((idx, j))
    return sorted(keep)


def contiguous_runs(indices):
    """[1,2,3,7,8] -> [[1,2,3],[7,8]]"""
    runs = []
    for i in indices:
        if runs and i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


# ---------------------------------------------------------------------------
# Target points: Edit Mode = selected, Object Mode = all
# ---------------------------------------------------------------------------

def is_curve(obj):
    return obj is not None and obj.type == 'CURVE'


def poll_curve_object_or_edit(context):
    return is_curve(context.object) and context.mode in {'OBJECT', 'EDIT_CURVE'}


def target_point_sets(context):
    """List of (spline, [point indices]) for every Bezier spline.

    In Edit Mode only selected control points are targets; in Object Mode
    every point is.
    """
    edit = context.mode == 'EDIT_CURVE'
    result = []
    for spline in context.object.data.splines:
        if spline.type != 'BEZIER':
            continue
        pts = spline.bezier_points
        if edit:
            idx = [i for i, p in enumerate(pts) if p.select_control_point]
        else:
            idx = list(range(len(pts)))
        if idx:
            result.append((spline, idx))
    return result


def scope_label(context):
    return "Selected points" if context.mode == 'EDIT_CURVE' else "All points"


def set_point_co(p, co, handle_scale=1.0):
    """Move a Bezier point and carry its handles along with it."""
    off_l = (p.handle_left - p.co) * handle_scale
    off_r = (p.handle_right - p.co) * handle_scale
    p.co = co
    p.handle_left = co + off_l
    p.handle_right = co + off_r


# ---------------------------------------------------------------------------
# Generators: shared operator properties
# ---------------------------------------------------------------------------

TWIST_ITEMS = [
    ('Z_UP',    "Z-Up",    "Use world Z as the up direction"),
    ('MINIMUM', "Minimum", "Use the least twist over the curve"),
    ('TANGENT', "Tangent", "Follow the curve tangent"),
]


class CurveGeometryProps:
    """Bevel / extrude settings for generator operators (adjustable with F9)."""

    bevel_depth: bpy.props.FloatProperty(
        name="Bevel Depth", default=0.0, min=0.0, max=10.0, step=1, unit='LENGTH',
        description="Tube thickness (0 = wire only)",
    )
    bevel_resolution: bpy.props.IntProperty(
        name="Bevel Resolution", default=4, min=0, max=32,
        description="Cross-section detail (0 = flat ribbon)",
    )
    extrude: bpy.props.FloatProperty(
        name="Extrude", default=0.0, min=0.0, max=100.0, step=1, unit='LENGTH',
        description="Extrude along the curve normal",
    )
    offset: bpy.props.FloatProperty(
        name="Offset", default=0.0, min=-10.0, max=10.0, step=1,
        description="Offset the geometry from the curve center line",
    )
    twist_mode: bpy.props.EnumProperty(
        name="Twist Method", items=TWIST_ITEMS, default='MINIMUM',
        description="How the curve twist is computed",
    )
    use_fill_caps: bpy.props.BoolProperty(
        name="Fill Caps", default=True,
        description="Close both ends of the beveled tube",
    )

    def apply_geometry(self, curve_data):
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = self.bevel_depth
        curve_data.bevel_resolution = self.bevel_resolution
        curve_data.extrude = self.extrude
        curve_data.offset = self.offset
        curve_data.twist_mode = self.twist_mode
        curve_data.use_fill_caps = self.use_fill_caps
        if self.bevel_depth > 0.0:
            curve_data.bevel_mode = 'ROUND'

    def draw_geometry(self, layout):
        box = layout.box()
        box.label(text="Curve Geometry", icon='CURVE_DATA')
        col = box.column(align=True)
        for name in ("bevel_depth", "bevel_resolution", "extrude", "offset",
                     "twist_mode", "use_fill_caps"):
            col.prop(self, name)


class PointTiltProps:
    """Per-point tilt for generator operators (sets cross-section direction)."""

    tilt_mode: bpy.props.EnumProperty(
        name="Tilt Mode",
        items=[
            ('NONE',        "None",        "No tilt"),
            ('UNIFORM',     "Uniform",     "Same tilt on every point"),
            ('PROGRESSIVE', "Progressive", "Tilt changes linearly from start to end"),
        ],
        default='NONE',
        description="Rotation of each point around the curve tangent",
    )
    tilt_uniform: bpy.props.FloatProperty(name="Tilt", default=0.0, subtype='ANGLE')
    tilt_start: bpy.props.FloatProperty(name="Tilt Start", default=0.0, subtype='ANGLE')
    tilt_end: bpy.props.FloatProperty(name="Tilt End", default=math.tau, subtype='ANGLE')

    def tilt_at(self, t):
        if self.tilt_mode == 'UNIFORM':
            return self.tilt_uniform
        if self.tilt_mode == 'PROGRESSIVE':
            return self.tilt_start + (self.tilt_end - self.tilt_start) * t
        return 0.0

    def draw_tilt(self, layout):
        box = layout.box()
        box.label(text="Point Tilt", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        col = box.column(align=True)
        col.prop(self, "tilt_mode")
        if self.tilt_mode == 'UNIFORM':
            col.prop(self, "tilt_uniform")
        elif self.tilt_mode == 'PROGRESSIVE':
            col.prop(self, "tilt_start")
            col.prop(self, "tilt_end")
        return col


def add_bezier_spline(curve_data, coords, tilts=None, cyclic=False):
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(len(coords) - 1)
    spline.use_cyclic_u = cyclic
    for i, bp in enumerate(spline.bezier_points):
        bp.co = coords[i]
        bp.handle_left_type = 'AUTO'
        bp.handle_right_type = 'AUTO'
        if tilts is not None:
            bp.tilt = tilts[i]
    return spline


def link_new_object(context, name, data, location=None):
    obj = bpy.data.objects.new(name, data)
    obj.location = context.scene.cursor.location if location is None else location
    context.collection.objects.link(obj)
    for o in context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj
