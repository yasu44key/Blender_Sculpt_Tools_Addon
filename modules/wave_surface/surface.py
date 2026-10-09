"""Wave Surface: z = f(x, y) as a Geometry Nodes modifier (stays editable, can animate).

    h = a·x² + b·y² + c·xy + d·x + e·y + f
      + Σ (k = 1..3)  A_k · sin( 2π / λ_k · (r_k − v_k · t) )      r_k = distance to center k

x, y are the object's local coordinates. The height moves each vertex along
local Z, or along its normal (so it also works on meshes that are not flat).
t is the scene time in seconds when Animate is on (plus Time Offset), so a
wave with speed v travels outward at v metres per second.

Replaces: parametric_plane/parametric_plane.py, create_wave_plane.py,
create_wave_plane01.py, Create_Complex_Wave_Plane.py, Create_Complex_Wave_Plane02.py
"""

import math

import bpy

from ...core import nodes

MOD_NAME = "STS Wave Surface"
GROUP_NAME = "STS Wave Surface"
VERSION = 1
WAVES = 3

# coefficient inputs: (name, default)
QUADRATIC = (
    ("x² (a)", 0.0), ("y² (b)", 0.0), ("xy (c)", 0.0), ("x (d)", 0.0), ("y (e)", 0.0), ("Constant (f)", 0.0),
)


def wave_inputs(k):
    amp = 0.5 if k == 1 else 0.0
    return (
        (f"Wave {k} Amplitude", 'NodeSocketFloat', amp, None, None, 'DISTANCE', "Height of the wave (0 = off)"),
        (f"Wave {k} Wavelength", 'NodeSocketFloat', 1.0 + k, 0.001, None, 'DISTANCE', "Distance between crests"),
        (f"Wave {k} Center X", 'NodeSocketFloat', 0.0, None, None, 'DISTANCE', "Where the rings start"),
        (f"Wave {k} Center Y", 'NodeSocketFloat', 0.0, None, None, 'DISTANCE', "Where the rings start"),
        (f"Wave {k} Speed", 'NodeSocketFloat', 1.0, None, None, 'NONE',
         "How fast the rings travel outward, in metres per second (negative = inward)"),
    )


OTHER = (
    ("Animate", 'NodeSocketBool', False, None, None, 'NONE', "Move the waves with the scene time"),
    ("Time Offset", 'NodeSocketFloat', 0.0, None, None, 'NONE', "Seconds added to the time (pose a still frame)"),
    ("Along Normals", 'NodeSocketBool', False, None, None, 'NONE',
     "Move vertices along their normals instead of local Z (for meshes that are not flat)"),
)


def _new_input(itf, name, typ, default, mn, mx, subtype, desc, parent=None):
    s = itf.new_socket(name, in_out='INPUT', socket_type=typ, parent=parent)
    s.default_value = default
    s.description = desc
    if mn is not None:
        s.min_value = mn
    if mx is not None:
        s.max_value = mx
    if subtype != 'NONE':
        s.subtype = subtype
    return s


def input_names():
    """All value inputs in panel order: [(panel title, [names])]."""
    out = [("Shape (Quadratic)", [n for n, _d in QUADRATIC])]
    for k in range(1, WAVES + 1):
        out.append((f"Wave {k}", [spec[0] for spec in wave_inputs(k)]))
    out.append(("Motion", [spec[0] for spec in OTHER]))
    return out


class _Builder:
    def __init__(self, ng):
        self.ng = ng
        self.col = 0
        self.row = 0

    def node(self, idname, **attrs):
        n = self.ng.nodes.new(idname)
        for k, v in attrs.items():
            setattr(n, k, v)
        n.location = (self.col * 180, -self.row * 160)
        self.row += 1
        if self.row > 8:
            self.row = 0
            self.col += 1
        return n

    def link(self, a, b):
        self.ng.links.new(a, b)

    def _feed(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0):
        n = self.node('ShaderNodeMath', operation=op)
        self._feed(n.inputs[0], a)
        self._feed(n.inputs[1], b)
        return n.outputs[0]

    def add(self, *terms):
        acc = terms[0]
        for t in terms[1:]:
            acc = self.math('ADD', acc, t)
        return acc


def build_node_group():
    ng = bpy.data.node_groups.new(GROUP_NAME, 'GeometryNodeTree')
    ng["sts_wave_surface_version"] = VERSION
    itf = ng.interface
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    p = itf.new_panel("Shape (Quadratic)", default_closed=True)
    for name, d in QUADRATIC:
        _new_input(itf, name, 'NodeSocketFloat', d, None, None, 'NONE',
                   "Coefficient of the quadratic surface term", parent=p)
    for k in range(1, WAVES + 1):
        p = itf.new_panel(f"Wave {k}", default_closed=k > 1)
        for spec in wave_inputs(k):
            _new_input(itf, *spec, parent=p)
    p = itf.new_panel("Motion")
    for spec in OTHER:
        _new_input(itf, *spec, parent=p)
    itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    B = _Builder(ng)
    gin = B.node('NodeGroupInput')
    gout = B.node('NodeGroupOutput')
    I = gin.outputs

    pos = B.node('GeometryNodeInputPosition')
    sep = B.node('ShaderNodeSeparateXYZ')
    B.link(pos.outputs[0], sep.inputs[0])
    x, y = sep.outputs["X"], sep.outputs["Y"]

    quad = B.add(
        B.math('MULTIPLY', I["x² (a)"], B.math('MULTIPLY', x, x)),
        B.math('MULTIPLY', I["y² (b)"], B.math('MULTIPLY', y, y)),
        B.math('MULTIPLY', I["xy (c)"], B.math('MULTIPLY', x, y)),
        B.math('MULTIPLY', I["x (d)"], x),
        B.math('MULTIPLY', I["y (e)"], y),
        I["Constant (f)"],
    )

    scene_time = B.node('GeometryNodeInputSceneTime')
    run = B.node('GeometryNodeSwitch', input_type='FLOAT')
    B.link(I["Animate"], run.inputs["Switch"])
    run.inputs["False"].default_value = 0.0
    B.link(scene_time.outputs["Seconds"], run.inputs["True"])
    t = B.math('ADD', run.outputs[0], I["Time Offset"])

    terms = [quad]
    for k in range(1, WAVES + 1):
        dx = B.math('SUBTRACT', x, I[f"Wave {k} Center X"])
        dy = B.math('SUBTRACT', y, I[f"Wave {k} Center Y"])
        r = B.math('SQRT', B.math('ADD', B.math('MULTIPLY', dx, dx), B.math('MULTIPLY', dy, dy)))
        travel = B.math('SUBTRACT', r, B.math('MULTIPLY', I[f"Wave {k} Speed"], t))
        k_num = B.math('DIVIDE', 2.0 * math.pi, I[f"Wave {k} Wavelength"])
        wave = B.math('MULTIPLY', I[f"Wave {k} Amplitude"], B.math('SINE', B.math('MULTIPLY', k_num, travel)))
        terms.append(wave)
    h = B.add(*terms)

    up = B.node('ShaderNodeCombineXYZ')
    B.link(h, up.inputs["Z"])
    normal = B.node('GeometryNodeInputNormal')
    along = B.node('ShaderNodeVectorMath', operation='SCALE')
    B.link(normal.outputs[0], along.inputs[0])
    B.link(h, along.inputs["Scale"])
    pick = B.node('GeometryNodeSwitch', input_type='VECTOR')
    B.link(I["Along Normals"], pick.inputs["Switch"])
    B.link(up.outputs[0], pick.inputs["False"])
    B.link(along.outputs[0], pick.inputs["True"])

    setp = B.node('GeometryNodeSetPosition')
    B.link(I["Geometry"], setp.inputs["Geometry"])
    B.link(pick.outputs[0], setp.inputs["Offset"])
    B.link(setp.outputs[0], gout.inputs[0])
    gout.location = ((B.col + 1) * 180, 0)
    return ng


def node_group():
    for ng in bpy.data.node_groups:
        if ng.bl_idname == 'GeometryNodeTree' and ng.get("sts_wave_surface_version") == VERSION:
            return ng
    return build_node_group()


def add(obj):
    mod = obj.modifiers.get(MOD_NAME)
    if mod is None:
        mod = obj.modifiers.new(MOD_NAME, 'NODES')
    if mod.node_group is None:
        mod.node_group = node_group()
    return mod


def get(obj):
    mod = obj.modifiers.get(MOD_NAME) if obj is not None else None
    return mod if mod is not None and mod.type == 'NODES' else None


def set_input(mod, name, value):
    nodes.set_modifier_input(mod, nodes.socket_identifier(mod.node_group, name), value)


def get_input(mod, name):
    return nodes.get_modifier_input(mod, nodes.socket_identifier(mod.node_group, name))
