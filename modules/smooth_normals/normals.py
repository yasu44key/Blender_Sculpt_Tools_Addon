"""Smooth Normals: blend the shading normals toward a blurred (smoothed) normal,
weighted by a vertex group, as a Geometry Nodes modifier (custom normals).

    normal = normalize( mix(normal, normalize(blur(vertex normal)), weight · Strength) )

The blur runs on the vertices (so flat faces of a hard edge get smoothed too);
the result is written per face corner with Set Mesh Normal (Free). Applying
the modifier keeps the custom normals; the shape itself never changes.

Replaces: parametric_plane/smoothmod.py (it crashed on vertex groups and wrote
BMVert.normal, which is not stored).
"""

import bpy

from ...core import nodes, sculpt_mask

MOD_NAME = "STS Smooth Normals"
GROUP_NAME = "STS Smooth Normals"
VERSION = 2

INPUTS = (
    ("Vertex Group", 'NodeSocketString', "", None, None, 'NONE',
     "Weights that say where to smooth (empty = the whole mesh)"),
    ("Strength", 'NodeSocketFloat', 1.0, 0.0, 1.0, 'FACTOR', "How far the normals move toward the smoothed ones"),
    ("Smoothness", 'NodeSocketInt', 5, 0, 200, 'NONE', "Blur steps: more = smoother over a wider area"),
)


def build_node_group():
    ng = bpy.data.node_groups.new(GROUP_NAME, 'GeometryNodeTree')
    ng["sts_smooth_normals_version"] = VERSION
    itf = ng.interface
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    for name, typ, default, mn, mx, subtype, desc in INPUTS:
        s = itf.new_socket(name, in_out='INPUT', socket_type=typ)
        s.default_value = default
        s.description = desc
        if mn is not None:
            s.min_value = mn
        if mx is not None:
            s.max_value = mx
        if subtype != 'NONE':
            s.subtype = subtype
    itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    N, link = ng.nodes, ng.links.new
    gin = N.new('NodeGroupInput')
    gout = N.new('NodeGroupOutput')

    normal = N.new('GeometryNodeInputNormal')
    blur = N.new('GeometryNodeBlurAttribute')
    blur.data_type = 'FLOAT_VECTOR'
    on_points = N.new('GeometryNodeFieldOnDomain')     # blur between vertices, not corners
    on_points.domain = 'POINT'
    on_points.data_type = 'FLOAT_VECTOR'
    # Blurred normals shrink (opposite directions cancel out); without this the
    # mix would barely move until Strength reaches 1.
    blur_unit = N.new('ShaderNodeVectorMath')
    blur_unit.operation = 'NORMALIZE'

    weight = N.new('GeometryNodeInputNamedAttribute')
    weight.data_type = 'FLOAT'
    whole = N.new('GeometryNodeSwitch')                # no such group (or empty name) -> 1.0
    whole.input_type = 'FLOAT'
    whole.inputs["False"].default_value = 1.0
    factor = N.new('ShaderNodeMath')
    factor.operation = 'MULTIPLY'
    factor.use_clamp = True

    mix = N.new('ShaderNodeMix')
    mix.data_type = 'VECTOR'
    unit = N.new('ShaderNodeVectorMath')
    unit.operation = 'NORMALIZE'
    setn = N.new('GeometryNodeSetMeshNormal')
    setn.mode = 'FREE'
    setn.domain = 'CORNER'

    link(normal.outputs[0], blur.inputs[0])
    link(gin.outputs["Smoothness"], blur.inputs["Iterations"])
    link(blur.outputs[0], on_points.inputs[0])

    link(gin.outputs["Vertex Group"], weight.inputs["Name"])
    link(weight.outputs["Exists"], whole.inputs["Switch"])
    link(weight.outputs["Attribute"], whole.inputs["True"])
    link(whole.outputs[0], factor.inputs[0])
    link(gin.outputs["Strength"], factor.inputs[1])

    link(factor.outputs[0], mix.inputs["Factor"])
    link(normal.outputs[0], mix.inputs["A"])
    link(on_points.outputs[0], blur_unit.inputs[0])
    link(blur_unit.outputs[0], mix.inputs["B"])
    link(mix.outputs["Result"], unit.inputs[0])
    link(gin.outputs["Geometry"], setn.inputs["Mesh"])
    link(unit.outputs[0], setn.inputs["Custom Normal"])
    link(setn.outputs[0], gout.inputs[0])

    for i, col in enumerate(((gin,), (normal, weight), (blur, whole), (on_points, factor), (blur_unit,), (mix,), (unit,),
                             (setn,), (gout,))):
        for j, node in enumerate(col):
            node.location = (i * 200, -j * 220)
    return ng


SCULPT_MASK = sculpt_mask.SCULPT_MASK
MASK_GROUP = "Sculpt Mask"


def mask_to_group(obj):
    """Copy the sculpt mask into the vertex group "Sculpt Mask" (see core/sculpt_mask.py)."""
    return sculpt_mask.mask_to_group(obj, MASK_GROUP)


def node_group():
    for ng in bpy.data.node_groups:
        if ng.bl_idname == 'GeometryNodeTree' and ng.get("sts_smooth_normals_version") == VERSION:
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
