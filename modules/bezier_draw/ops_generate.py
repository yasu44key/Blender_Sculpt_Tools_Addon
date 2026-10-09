"""Parametric Bezier curve generators (Add > Curve, and the Generate tab).

All options stay adjustable afterwards in the Adjust Last Operation panel (F9).
"""

import math

import bpy
from mathutils import Matrix, Vector

from ...core import curve_utils as cu


class _Generator(cu.CurveGeometryProps, cu.PointTiltProps):
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def new_curve(self, name):
        data = bpy.data.curves.new(name, type='CURVE')
        self.apply_geometry(data)
        return data


# ---------------------------------------------------------------------------

class CURVE_OT_sts_lissajous_add(_Generator, bpy.types.Operator):
    """Add a 3D Lissajous curve at the 3D cursor"""
    bl_idname = "curve.sts_lissajous_add"
    bl_label = "3D Lissajous"

    steps: bpy.props.IntProperty(name="Points", default=128, min=8, max=2048)
    freq_a: bpy.props.FloatProperty(name="Frequency X", default=3.0, min=0.1, max=32.0, step=10)
    freq_b: bpy.props.FloatProperty(name="Frequency Y", default=4.0, min=0.1, max=32.0, step=10)
    freq_c: bpy.props.FloatProperty(name="Frequency Z", default=5.0, min=0.1, max=32.0, step=10)
    amp_x: bpy.props.FloatProperty(name="Size X", default=1.0, min=0.01, max=10.0, unit='LENGTH')
    amp_y: bpy.props.FloatProperty(name="Size Y", default=1.0, min=0.01, max=10.0, unit='LENGTH')
    amp_z: bpy.props.FloatProperty(name="Size Z", default=1.0, min=0.01, max=10.0, unit='LENGTH')
    phase_x: bpy.props.FloatProperty(name="Phase X", default=0.0, subtype='ANGLE')
    phase_y: bpy.props.FloatProperty(name="Phase Y", default=math.pi / 4, subtype='ANGLE')
    phase_z: bpy.props.FloatProperty(name="Phase Z", default=math.pi / 2, subtype='ANGLE')
    cyclic: bpy.props.BoolProperty(
        name="Cyclic", default=True,
        description="Close the curve (seamless only for integer frequencies)")

    def execute(self, context):
        n = self.steps
        coords, tilts = [], []
        for i in range(n):
            u = i / n if self.cyclic else cu.param_t(i, n)
            t = u * math.tau
            coords.append((self.amp_x * math.sin(self.freq_a * t + self.phase_x),
                           self.amp_y * math.sin(self.freq_b * t + self.phase_y),
                           self.amp_z * math.sin(self.freq_c * t + self.phase_z)))
            tilts.append(self.tilt_at(cu.param_t(i, n)))
        data = self.new_curve("Lissajous")
        cu.add_bezier_spline(data, coords, tilts, self.cyclic)
        cu.link_new_object(context, "Lissajous", data)
        return {'FINISHED'}

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "steps")
        col = layout.column(align=True)
        col.prop(self, "freq_a")
        col.prop(self, "freq_b")
        col.prop(self, "freq_c")
        col = layout.column(align=True)
        col.prop(self, "amp_x")
        col.prop(self, "amp_y")
        col.prop(self, "amp_z")
        col = layout.column(align=True)
        col.prop(self, "phase_x")
        col.prop(self, "phase_y")
        col.prop(self, "phase_z")
        layout.prop(self, "cyclic")
        self.draw_tilt(layout)
        self.draw_geometry(layout)


# ---------------------------------------------------------------------------

def _resample(points, n):
    """Arc-length resample a list of Vectors to exactly n points."""
    if len(points) < 2:
        return [points[0]] * n
    arcs = [0.0]
    for i in range(1, len(points)):
        arcs.append(arcs[-1] + (points[i] - points[i - 1]).length)
    total = arcs[-1]
    if total < 1e-10:
        return [points[0]] * n
    out, j = [], 0
    for k in range(n):
        target = total * cu.param_t(k, n)
        while j < len(arcs) - 2 and arcs[j + 1] < target:
            j += 1
        seg = arcs[j + 1] - arcs[j]
        u = (target - arcs[j]) / seg if seg > 1e-10 else 0.0
        out.append(points[j].lerp(points[j + 1], u))
    return out


def _parallel_transport_frames(points):
    """(normal, binormal) per point, transported along the polyline."""
    n = len(points)
    tangents = []
    for i in range(n):
        a = points[max(i - 1, 0)]
        b = points[min(i + 1, n - 1)]
        v = b - a
        tangents.append(v.normalized() if v.length_squared > 1e-10
                        else (tangents[-1] if tangents else Vector((0, 0, 1))))
    t = tangents[0]
    seed = Vector((1, 0, 0)) if abs(t.dot(Vector((0, 0, 1)))) > 0.98 else Vector((0, 0, 1))
    nv = t.cross(seed).cross(t).normalized()
    bv = t.cross(nv).normalized()
    frames = [(nv.copy(), bv.copy())]
    for i in range(1, n):
        t_new = tangents[i]
        axis = t.cross(t_new)
        if axis.length_squared > 1e-10:
            axis.normalize()
            rot = Matrix.Rotation(math.acos(max(-1.0, min(1.0, t.dot(t_new)))), 3, axis)
            nv = (rot @ nv).normalized()
            bv = (rot @ bv).normalized()
        t = t_new
        frames.append((nv.copy(), bv.copy()))
    return frames


class CURVE_OT_sts_strand_add(_Generator, bpy.types.Operator):
    """Add twisted wire / braid strands, optionally following a guide curve"""
    bl_idname = "curve.sts_strand_add"
    bl_label = "Strand Curve"

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[('WIRE', "Twisted Wire", "Strands spiral around a common axis"),
               ('BRAID', "Braid", "Strands weave over and under each other"),
               ('DIAMOND', "Diamond Braid", "Two groups turning in opposite directions")],
        default='BRAID',
    )
    strands: bpy.props.IntProperty(name="Strands", default=3, min=2, max=16)
    steps: bpy.props.IntProperty(name="Points", default=128, min=8, max=2048,
                                 description="Points per strand")
    radius: bpy.props.FloatProperty(name="Radius", default=0.5, min=0.01, max=10.0, unit='LENGTH')
    turns: bpy.props.FloatProperty(name="Turns", default=4.0, min=0.1, max=64.0)
    length: bpy.props.FloatProperty(name="Length", default=3.0, min=0.01, max=200.0, unit='LENGTH',
                                    description="Strand length when no guide curve is used")
    flatten: bpy.props.FloatProperty(name="Flatten", default=1.0, min=0.01, max=1.0,
                                     description="1 = round, small = flat ribbon")
    cyclic: bpy.props.BoolProperty(name="Cyclic", default=False)
    guide_name: bpy.props.StringProperty(
        name="Guide Curve", default="",
        description="Curve object to follow (empty = straight along Z)")
    tilt_track: bpy.props.BoolProperty(
        name="Follow Strand Angle", default=False,
        description="Add each strand's rotation to the tilt (keeps Twisted Wire extrude facing outwards)")

    def _offset(self, k, n_strands, t):
        if self.mode == 'WIRE':
            ang = math.tau * (t * self.turns + k / n_strands)
            return self.radius * math.cos(ang), self.radius * math.sin(ang)
        if self.mode == 'BRAID':
            ang = math.tau * (n_strands * t * self.turns + k / n_strands)
        else:  # DIAMOND
            half = n_strands // 2
            sign = 1 if k < half else -1
            ang = sign * half * math.tau * t * self.turns + math.tau * (k % half) / half
        return self.radius * math.cos(ang), self.radius * math.sin(ang) * self.flatten

    def _guide(self, context):
        guide = context.scene.objects.get(self.guide_name)
        if not cu.is_curve(guide):
            return None
        eval_obj = guide.evaluated_get(context.evaluated_depsgraph_get())
        mesh = eval_obj.to_mesh()
        raw = [guide.matrix_world @ v.co for v in mesh.vertices] if mesh else []
        eval_obj.to_mesh_clear()
        if len(raw) < 2:
            return None
        pts = _resample(raw, self.steps)
        return pts, _parallel_transport_frames(pts)

    def execute(self, context):
        n_strands = self.strands + (self.strands % 2 if self.mode == 'DIAMOND' else 0)
        guide = self._guide(context) if self.guide_name else None
        if self.guide_name and guide is None:
            self.report({'WARNING'}, "Guide curve not usable; using a straight axis")

        data = self.new_curve("Strand")
        n = self.steps
        for k in range(n_strands):
            coords, tilts = [], []
            for s in range(n):
                t = s / n if self.cyclic else cu.param_t(s, n)
                ox, oy = self._offset(k, n_strands, t)
                if guide:
                    pt = guide[0][s]
                    nv, bv = guide[1][s]
                    coords.append(pt + ox * nv + oy * bv)
                else:
                    coords.append((ox, oy, t * self.length - self.length * 0.5))
                tilt = self.tilt_at(cu.param_t(s, n))
                if self.tilt_track:
                    tilt += math.tau * (k / n_strands + t * self.turns)
                tilts.append(tilt)
            cu.add_bezier_spline(data, coords, tilts, self.cyclic)

        # A guided strand is built in world space.
        cu.link_new_object(context, "Strand", data,
                           location=(0.0, 0.0, 0.0) if guide else None)
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "mode")
        col = layout.column(align=True)
        col.prop(self, "strands")
        if self.mode == 'DIAMOND' and self.strands % 2:
            col.label(text="Rounded up to an even number", icon='INFO')
        col.prop(self, "steps")
        col.prop(self, "radius")
        col.prop(self, "turns")
        if self.mode != 'WIRE':
            col.prop(self, "flatten")
        layout.prop(self, "cyclic")
        layout.prop_search(self, "guide_name", context.scene, "objects", icon='CURVE_DATA')
        guide = context.scene.objects.get(self.guide_name)
        if self.guide_name and not cu.is_curve(guide):
            layout.label(text="Pick a curve object", icon='ERROR')
        if not cu.is_curve(guide):
            layout.prop(self, "length")
        col = self.draw_tilt(layout)
        col.prop(self, "tilt_track")
        self.draw_geometry(layout)


# ---------------------------------------------------------------------------

class CURVE_OT_sts_crossnet_add(_Generator, bpy.types.Operator):
    """Add a woven net: two sets of strands crossing over and under"""
    bl_idname = "curve.sts_crossnet_add"
    bl_label = "Cross Net"

    strands_a: bpy.props.IntProperty(name="Strands (vertical)", default=5, min=2, max=32)
    strands_b: bpy.props.IntProperty(name="Strands (horizontal)", default=5, min=2, max=32)
    spacing: bpy.props.FloatProperty(name="Spacing", default=0.5, min=0.01, max=20.0, unit='LENGTH')
    amplitude: bpy.props.FloatProperty(name="Weave Height", default=0.05, min=0.001, max=5.0,
                                       unit='LENGTH')
    freq_mult: bpy.props.FloatProperty(name="Weave Frequency", default=1.0, min=0.1, max=8.0,
                                       description="1 = one over/under per crossing")
    steps: bpy.props.IntProperty(name="Points", default=128, min=8, max=2048)

    def execute(self, context):
        na, nb, sp, amp, n = (self.strands_a, self.strands_b, self.spacing,
                              self.amplitude, self.steps)
        width, height = (na - 1) * sp, (nb - 1) * sp
        freq_a = (nb - 1) * 0.5 * self.freq_mult
        freq_b = (na - 1) * 0.5 * self.freq_mult
        tilts = [self.tilt_at(cu.param_t(s, n)) for s in range(n)]
        data = self.new_curve("CrossNet")

        # Neighbouring strands are in opposite phase, and the two directions
        # are offset by pi, so every crossing alternates over / under.
        for i in range(na):
            x0, phase = i * sp - width * 0.5, (0.0 if i % 2 == 0 else math.pi)
            coords = [(x0, amp * math.sin(freq_a * cu.param_t(s, n) * math.tau + phase),
                       cu.param_t(s, n) * height - height * 0.5) for s in range(n)]
            cu.add_bezier_spline(data, coords, tilts)
        for j in range(nb):
            z0, phase = j * sp - height * 0.5, (math.pi if j % 2 == 0 else 0.0)
            coords = [(cu.param_t(s, n) * width - width * 0.5,
                       amp * math.sin(freq_b * cu.param_t(s, n) * math.tau + phase), z0)
                      for s in range(n)]
            cu.add_bezier_spline(data, coords, tilts)

        cu.link_new_object(context, "CrossNet", data)
        return {'FINISHED'}

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column(align=True)
        for name in ("strands_a", "strands_b", "spacing", "amplitude", "freq_mult", "steps"):
            col.prop(self, name)
        self.draw_tilt(layout)
        self.draw_geometry(layout)


# ---------------------------------------------------------------------------

class CURVE_OT_sts_spiral_add(_Generator, bpy.types.Operator):
    """Add a flat spiral or a spring at the 3D cursor"""
    bl_idname = "curve.sts_spiral_add"
    bl_label = "Spiral"

    radius_start: bpy.props.FloatProperty(name="Start Radius", default=1.0, min=0.0, unit='LENGTH')
    radius_end: bpy.props.FloatProperty(name="End Radius", default=5.0, min=0.0, unit='LENGTH')
    height: bpy.props.FloatProperty(name="Height", default=0.0, unit='LENGTH',
                                    description="0 = flat spiral, other values = spring")
    turns: bpy.props.FloatProperty(name="Turns", default=3.0, min=0.1, max=200.0)
    steps: bpy.props.IntProperty(name="Points", default=128, min=8, max=4096)

    def execute(self, context):
        n = self.steps
        coords, tilts = [], []
        for i in range(n):
            t = cu.param_t(i, n)
            ang = t * self.turns * math.tau
            r = self.radius_start + (self.radius_end - self.radius_start) * t
            coords.append((r * math.cos(ang), r * math.sin(ang), t * self.height))
            tilts.append(self.tilt_at(t))
        data = self.new_curve("Spiral")
        cu.add_bezier_spline(data, coords, tilts)
        cu.link_new_object(context, "Spiral", data)
        return {'FINISHED'}

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column(align=True)
        for name in ("radius_start", "radius_end", "height", "turns", "steps"):
            col.prop(self, name)
        self.draw_tilt(layout)
        self.draw_geometry(layout)


GENERATORS = (
    (CURVE_OT_sts_spiral_add, 'FORCE_VORTEX'),
    (CURVE_OT_sts_lissajous_add, 'FORCE_MAGNETIC'),
    (CURVE_OT_sts_strand_add, 'FORCE_CURVE'),
    (CURVE_OT_sts_crossnet_add, 'MESH_GRID'),
)


def add_menu(self, _context):
    layout = self.layout
    layout.separator()
    for op, icon in GENERATORS:
        layout.operator(op.bl_idname, icon=icon)


classes = tuple(op for op, _icon in GENERATORS)
