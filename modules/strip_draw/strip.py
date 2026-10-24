"""Strip: a drawn curve turned into a band on a surface, as a live Geometry Nodes modifier.

Replaces: ★archive/Armor_Ribbon/Armor_Ribbon_Pro.py and Mesh_Clay_Strip v0.2.2-0.2.4

    curve (radius = pen pressure)
      -> curve normal = tangent x surface normal of the target (so the band lies ON the surface;
         Curve to Mesh lays the profile along the curve normal)
      -> Curve to Mesh with a line profile Width x radius wide
      -> lift along the surface normal by Offset
      -> Thickness: extrude (a closed slab)
      -> Clay: Mesh to Volume -> Volume to Mesh (a soft, remeshed lump)

The old armor tool rebuilt ONE shared node group with nodes.clear() every time, so changing
the settings changed every armor drawn before; here each stroke keeps its own inputs on its
own modifier (the node group is shared, the values are not).
"""

import bpy

from ...core import nodes

MOD_NAME = "STS Strip"
GROUP_NAME = "STS Strip"
VERSION = 4        # 3: lengths in plain Blender units; 4: Voxel Size really used (was voxel Amount)
VOXELS_ACROSS = 200   # the clay voxel is never finer than Width / this (a fine voxel on a long strip
                      # fills memory and freezes Blender)

# Lengths have no unit subtype: they show as plain Blender units, like the scene's own grid.
INPUTS = (
    ("Target", 'NodeSocketObject', None, None, None, 'NONE', "Surface the band lies on"),
    ("Width", 'NodeSocketFloat', 5.0, 0.0, None, 'NONE', "Band width (times the pen pressure)"),
    ("Offset", 'NodeSocketFloat', 0.1, None, None, 'NONE', "Lift above the surface"),
    ("Band Thickness", 'NodeSocketFloat', 1.0, 0.0, None, 'NONE', "Thickness of the band (0 = a flat ribbon)"),
    ("Clay", 'NodeSocketBool', False, None, None, 'NONE', "Remesh the band into a soft clay strip"),
    ("Voxel Size", 'NodeSocketFloat', 0.1, 0.0001, None, 'NONE',
     f"Detail of the clay remesh (never finer than Width / {VOXELS_ACROSS})"),
)


def _set_free_normal_mode(node):
    """Set Curve Normal: 'Free' is a node property in some versions, a menu input in 5.x."""
    if hasattr(node, "mode"):
        node.mode = 'FREE'
    else:
        node.inputs["Mode"].default_value = 'Free'


def _set_voxel_size_mode(node):
    """Mesh to Volume: by voxel Size (the default is a voxel Amount, which ignores Voxel Size)."""
    if hasattr(node, "resolution_mode"):
        node.resolution_mode = 'VOXEL_SIZE'
    else:
        node.inputs["Resolution Mode"].default_value = 'Size'


def build_node_group():
    ng = bpy.data.node_groups.new(GROUP_NAME, 'GeometryNodeTree')
    ng["sts_strip_version"] = VERSION
    itf = ng.interface
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    for name, typ, default, mn, mx, subtype, desc in INPUTS:
        s = itf.new_socket(name, in_out='INPUT', socket_type=typ)
        s.description = desc
        if default is not None:
            s.default_value = default
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

    info = N.new('GeometryNodeObjectInfo')
    info.transform_space = 'RELATIVE'
    normal = N.new('GeometryNodeInputNormal')
    surf_n = N.new('GeometryNodeSampleNearestSurface')      # target normal at each curve point
    surf_n.data_type = 'FLOAT_VECTOR'
    tangent = N.new('GeometryNodeInputTangent')
    side = N.new('ShaderNodeVectorMath')
    side.operation = 'CROSS_PRODUCT'
    side_n = N.new('ShaderNodeVectorMath')
    side_n.operation = 'NORMALIZE'
    set_n = N.new('GeometryNodeSetCurveNormal')
    _set_free_normal_mode(set_n)

    profile = N.new('GeometryNodeCurvePrimitiveLine')
    profile.inputs["Start"].default_value = (-0.5, 0.0, 0.0)
    profile.inputs["End"].default_value = (0.5, 0.0, 0.0)
    radius = N.new('GeometryNodeInputRadius')
    width = N.new('ShaderNodeMath')
    width.operation = 'MULTIPLY'
    sweep = N.new('GeometryNodeCurveToMesh')

    lift_n = N.new('GeometryNodeSampleNearestSurface')      # target normal again, at the band's points
    lift_n.data_type = 'FLOAT_VECTOR'
    lift = N.new('ShaderNodeVectorMath')
    lift.operation = 'SCALE'
    lifted = N.new('GeometryNodeSetPosition')

    # face the band away from the surface whichever way the stroke was drawn
    facing = N.new('ShaderNodeVectorMath')
    facing.operation = 'DOT_PRODUCT'
    away = N.new('ShaderNodeMath')
    away.operation = 'LESS_THAN'
    away.inputs[1].default_value = 0.0
    orient = N.new('GeometryNodeFlipFaces')

    extrude = N.new('GeometryNodeExtrudeMesh')
    extrude.mode = 'FACES'
    extrude.inputs["Individual"].default_value = False
    flip = N.new('GeometryNodeFlipFaces')
    slab = N.new('GeometryNodeJoinGeometry')
    weld = N.new('GeometryNodeMergeByDistance')     # the bottom copy meets the side walls
    weld.inputs["Distance"].default_value = 1e-6
    flat = N.new('ShaderNodeMath')
    flat.operation = 'COMPARE'
    flat.inputs[1].default_value = 0.0
    flat.inputs[2].default_value = 0.0
    thick_or_flat = N.new('GeometryNodeSwitch')
    thick_or_flat.input_type = 'GEOMETRY'

    to_vol = N.new('GeometryNodeMeshToVolume')
    _set_voxel_size_mode(to_vol)
    finest = N.new('ShaderNodeMath')
    finest.operation = 'DIVIDE'
    finest.inputs[1].default_value = VOXELS_ACROSS
    voxel = N.new('ShaderNodeMath')
    voxel.operation = 'MAXIMUM'
    to_mesh = N.new('GeometryNodeVolumeToMesh')
    clay = N.new('GeometryNodeSwitch')
    clay.input_type = 'GEOMETRY'

    link(gin.outputs["Target"], info.inputs["Object"])
    link(info.outputs["Geometry"], surf_n.inputs["Mesh"])
    link(normal.outputs[0], surf_n.inputs["Value"])
    link(tangent.outputs[0], side.inputs[0])
    link(surf_n.outputs["Value"], side.inputs[1])
    link(side.outputs[0], side_n.inputs[0])
    link(gin.outputs["Geometry"], set_n.inputs["Curve"])
    link(side_n.outputs[0], set_n.inputs["Normal"])

    link(radius.outputs[0], width.inputs[0])
    link(gin.outputs["Width"], width.inputs[1])
    link(set_n.outputs[0], sweep.inputs["Curve"])
    link(profile.outputs[0], sweep.inputs["Profile Curve"])
    link(width.outputs[0], sweep.inputs["Scale"])

    link(info.outputs["Geometry"], lift_n.inputs["Mesh"])
    link(normal.outputs[0], lift_n.inputs["Value"])
    link(lift_n.outputs["Value"], lift.inputs[0])
    link(gin.outputs["Offset"], lift.inputs["Scale"])
    link(sweep.outputs[0], lifted.inputs["Geometry"])
    link(lift.outputs[0], lifted.inputs["Offset"])

    link(normal.outputs[0], facing.inputs[0])
    link(lift_n.outputs["Value"], facing.inputs[1])
    link(facing.outputs["Value"], away.inputs[0])
    link(lifted.outputs[0], orient.inputs["Mesh"])
    link(away.outputs[0], orient.inputs["Selection"])

    link(orient.outputs[0], extrude.inputs["Mesh"])
    link(gin.outputs["Band Thickness"], extrude.inputs["Offset Scale"])
    link(orient.outputs[0], flip.inputs["Mesh"])
    link(extrude.outputs["Mesh"], slab.inputs[0])
    link(flip.outputs[0], slab.inputs[0])
    link(gin.outputs["Band Thickness"], flat.inputs[0])
    link(flat.outputs[0], thick_or_flat.inputs["Switch"])
    link(slab.outputs[0], weld.inputs["Geometry"])
    link(weld.outputs[0], thick_or_flat.inputs["False"])
    link(orient.outputs[0], thick_or_flat.inputs["True"])

    link(thick_or_flat.outputs[0], to_vol.inputs["Mesh"])
    link(gin.outputs["Width"], finest.inputs[0])
    link(gin.outputs["Voxel Size"], voxel.inputs[0])
    link(finest.outputs[0], voxel.inputs[1])
    link(voxel.outputs[0], to_vol.inputs["Voxel Size"])
    link(to_vol.outputs[0], to_mesh.inputs["Volume"])
    link(gin.outputs["Clay"], clay.inputs["Switch"])
    link(thick_or_flat.outputs[0], clay.inputs["False"])
    link(to_mesh.outputs[0], clay.inputs["True"])
    link(clay.outputs[0], gout.inputs[0])

    columns = ((gin,), (info, normal, tangent, radius), (surf_n, side, width, profile), (side_n, lift_n),
               (set_n, lift), (sweep, facing), (lifted, away), (orient,), (extrude, flip, flat), (slab,), (weld,), (thick_or_flat,),
               (finest, voxel), (to_vol,), (to_mesh,), (clay,), (gout,))
    for i, col in enumerate(columns):
        for j, node in enumerate(col):
            node.location = (i * 200, -j * 220)
    return ng


def node_group():
    """The current group; strips on an older one are moved onto it (their values stay:
    the inputs keep their order, so their identifiers match)."""
    groups = [ng for ng in bpy.data.node_groups if ng.bl_idname == 'GeometryNodeTree' and "sts_strip_version" in ng]
    current = next((ng for ng in groups if ng["sts_strip_version"] == VERSION), None)
    old = [ng for ng in groups if ng["sts_strip_version"] != VERSION]
    if current is None:
        current = build_node_group()
    for ng in old:
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.node_group is ng:
                    values = {name: get_input(mod, name) for name, *_ in INPUTS}
                    mod.node_group = current
                    for name, value in values.items():
                        set_input(mod, name, value)
        if ng.users == 0:
            bpy.data.node_groups.remove(ng)
    return current


def upgrade_old():
    """Move strips off older node groups (on load / enable); nothing is built when there are none."""
    if any(ng.bl_idname == 'GeometryNodeTree' and ng.get("sts_strip_version", VERSION) != VERSION
           for ng in bpy.data.node_groups):
        node_group()


def get(obj):
    mod = obj.modifiers.get(MOD_NAME) if obj is not None else None
    return mod if mod is not None and mod.type == 'NODES' else None


def set_input(mod, name, value):
    nodes.set_modifier_input(mod, nodes.socket_identifier(mod.node_group, name), value)


def get_input(mod, name):
    return nodes.get_modifier_input(mod, nodes.socket_identifier(mod.node_group, name))


def add(obj, target, settings):
    """Give a curve object the strip modifier with the settings' values (its own copy)."""
    mod = get(obj)
    if mod is None:
        mod = obj.modifiers.new(MOD_NAME, 'NODES')
    if mod.node_group is None:
        mod.node_group = node_group()
    set_input(mod, "Target", target)
    set_input(mod, "Width", settings.width)
    set_input(mod, "Offset", settings.offset)
    set_input(mod, "Band Thickness", settings.thickness)
    set_input(mod, "Clay", settings.style == 'CLAY')
    set_input(mod, "Voxel Size", settings.voxel_size)
    return mod
