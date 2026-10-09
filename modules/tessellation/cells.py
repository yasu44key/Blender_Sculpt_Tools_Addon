"""Live Cells: a cell pattern as a Geometry Nodes modifier (stays editable).

One cell per vertex of the (subdivided, triangulated) surface: the Dual Mesh
of a triangle mesh is mostly hexagons, and jittering the vertices first (then
snapping them back onto the surface) makes it irregular like Voronoi cells.
Works on curved surfaces with no seams, and every input can be changed later.
"""

import bpy

from ...core import nodes

MOD_NAME = "STS Cells"
GROUP_NAME = "STS Cells"
VERSION = 1

# (name, socket type, default, min, max, description)
INPUTS = (
    ("Subdivisions", 'NodeSocketInt', 1, 0, 6, "Subdivide the surface first: more, smaller cells"),
    ("Triangulate", 'NodeSocketBool', True, None, None,
     "Triangulate first, so cells are mostly hexagons (off: cells follow the quads)"),
    ("Jitter", 'NodeSocketFloat', 0.3, 0.0, 1.0, "Randomly move the cell centers (0 = regular)"),
    ("Seed", 'NodeSocketInt', 0, 0, None, "Random seed for the jitter"),
    ("Gap", 'NodeSocketFloat', 0.1, 0.0, 0.95, "Space between cells, as a fraction of each cell"),
    ("Cell Thickness", 'NodeSocketFloat', 0.02, None, None, "Extrude each cell (0 = flat)"),
    ("Keep Base", 'NodeSocketBool', False, None, None, "Keep the original surface under the cells"),
    ("Lattice", 'NodeSocketBool', False, None, None, "Make a lattice of round struts along the cell edges"),
    ("Strut Radius", 'NodeSocketFloat', 0.01, 0.0, None, "Radius of the lattice struts"),
)


def _new_input(itf, name, typ, default, mn, mx, desc):
    s = itf.new_socket(name, in_out='INPUT', socket_type=typ)
    s.default_value = default
    s.description = desc
    if mn is not None:
        s.min_value = mn
    if mx is not None:
        s.max_value = mx
    if typ == 'NodeSocketFloat' and name in ("Cell Thickness", "Strut Radius"):
        s.subtype = 'DISTANCE'
    if typ == 'NodeSocketFloat' and name in ("Jitter", "Gap"):
        s.subtype = 'FACTOR'
    return s


def build_node_group():
    ng = bpy.data.node_groups.new(GROUP_NAME, 'GeometryNodeTree')
    ng["sts_cells_version"] = VERSION
    itf = ng.interface
    itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    for spec in INPUTS:
        _new_input(itf, *spec)
    itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    N, link = ng.nodes, ng.links.new
    gin = N.new('NodeGroupInput')
    gout = N.new('NodeGroupOutput')

    sub = N.new('GeometryNodeSubdivideMesh')
    tri = N.new('GeometryNodeTriangulate')
    use_tri = N.new('GeometryNodeSwitch')
    use_tri.input_type = 'GEOMETRY'

    # jitter: a random offset sized by the local edge length, then back onto the surface
    edge_vs = N.new('GeometryNodeInputMeshEdgeVertices')
    edge_len = N.new('ShaderNodeVectorMath')
    edge_len.operation = 'DISTANCE'
    cap = N.new('GeometryNodeCaptureAttribute')
    cap.domain = 'EDGE'
    cap.capture_items.new('FLOAT', "Length")
    rnd = N.new('FunctionNodeRandomValue')
    rnd.data_type = 'FLOAT_VECTOR'
    rnd.inputs["Min"].default_value = (-1.0, -1.0, -1.0)
    rnd.inputs["Max"].default_value = (1.0, 1.0, 1.0)
    amount = N.new('ShaderNodeMath')
    amount.operation = 'MULTIPLY'
    half = N.new('ShaderNodeMath')
    half.operation = 'MULTIPLY'
    half.inputs[1].default_value = 0.5
    offset = N.new('ShaderNodeVectorMath')
    offset.operation = 'SCALE'
    jitter = N.new('GeometryNodeSetPosition')
    prox = N.new('GeometryNodeProximity')
    prox.target_element = 'FACES'
    onto = N.new('GeometryNodeSetPosition')

    dual = N.new('GeometryNodeDualMesh')
    dual.inputs["Keep Boundaries"].default_value = True

    # cells: split apart, shrink by Gap, extrude by Thickness
    split = N.new('GeometryNodeSplitEdges')
    keep = N.new('ShaderNodeMath')
    keep.operation = 'SUBTRACT'
    keep.inputs[0].default_value = 1.0
    shrink = N.new('GeometryNodeScaleElements')
    shrink.domain = 'FACE'
    extrude = N.new('GeometryNodeExtrudeMesh')
    extrude.mode = 'FACES'
    extrude.inputs["Individual"].default_value = False
    flip = N.new('GeometryNodeFlipFaces')
    solid = N.new('GeometryNodeJoinGeometry')
    flat = N.new('ShaderNodeMath')
    flat.operation = 'COMPARE'
    flat.inputs[1].default_value = 0.0
    flat.inputs[2].default_value = 0.0
    thick_or_flat = N.new('GeometryNodeSwitch')
    thick_or_flat.input_type = 'GEOMETRY'

    # lattice: the cell edges as round struts
    to_curve = N.new('GeometryNodeMeshToCurve')
    profile = N.new('GeometryNodeCurvePrimitiveCircle')
    profile.inputs["Resolution"].default_value = 6
    struts = N.new('GeometryNodeCurveToMesh')
    pick = N.new('GeometryNodeSwitch')
    pick.input_type = 'GEOMETRY'

    base = N.new('GeometryNodeJoinGeometry')
    with_base = N.new('GeometryNodeSwitch')
    with_base.input_type = 'GEOMETRY'

    link(gin.outputs["Geometry"], sub.inputs["Mesh"])
    link(gin.outputs["Subdivisions"], sub.inputs["Level"])
    link(sub.outputs[0], tri.inputs["Mesh"])
    link(gin.outputs["Triangulate"], use_tri.inputs["Switch"])
    link(sub.outputs[0], use_tri.inputs["False"])
    link(tri.outputs[0], use_tri.inputs["True"])

    link(use_tri.outputs[0], cap.inputs["Geometry"])
    link(edge_vs.outputs["Position 1"], edge_len.inputs[0])
    link(edge_vs.outputs["Position 2"], edge_len.inputs[1])
    link(edge_len.outputs["Value"], cap.inputs[1])
    link(gin.outputs["Seed"], rnd.inputs["Seed"])
    link(gin.outputs["Jitter"], amount.inputs[0])
    link(cap.outputs[1], amount.inputs[1])
    link(amount.outputs[0], half.inputs[0])
    link(rnd.outputs["Value"], offset.inputs[0])
    link(half.outputs[0], offset.inputs["Scale"])
    link(cap.outputs[0], jitter.inputs["Geometry"])
    link(offset.outputs[0], jitter.inputs["Offset"])
    link(jitter.outputs[0], onto.inputs["Geometry"])
    link(gin.outputs["Geometry"], prox.inputs["Geometry"])
    link(prox.outputs["Position"], onto.inputs["Position"])
    link(onto.outputs[0], dual.inputs["Mesh"])

    link(dual.outputs[0], split.inputs["Mesh"])
    link(gin.outputs["Gap"], keep.inputs[1])
    link(split.outputs[0], shrink.inputs["Geometry"])
    link(keep.outputs[0], shrink.inputs["Scale"])
    link(shrink.outputs[0], extrude.inputs["Mesh"])
    link(gin.outputs["Cell Thickness"], extrude.inputs["Offset Scale"])
    link(shrink.outputs[0], flip.inputs["Mesh"])
    link(extrude.outputs["Mesh"], solid.inputs[0])
    link(flip.outputs[0], solid.inputs[0])
    link(gin.outputs["Cell Thickness"], flat.inputs[0])
    link(flat.outputs[0], thick_or_flat.inputs["Switch"])
    link(solid.outputs[0], thick_or_flat.inputs["False"])
    link(shrink.outputs[0], thick_or_flat.inputs["True"])

    link(dual.outputs[0], to_curve.inputs["Mesh"])
    link(gin.outputs["Strut Radius"], profile.inputs["Radius"])
    link(to_curve.outputs[0], struts.inputs["Curve"])
    link(profile.outputs["Curve"], struts.inputs["Profile Curve"])
    link(gin.outputs["Lattice"], pick.inputs["Switch"])
    link(thick_or_flat.outputs[0], pick.inputs["False"])
    link(struts.outputs[0], pick.inputs["True"])

    link(pick.outputs[0], base.inputs[0])
    link(gin.outputs["Geometry"], base.inputs[0])
    link(gin.outputs["Keep Base"], with_base.inputs["Switch"])
    link(pick.outputs[0], with_base.inputs["False"])
    link(base.outputs[0], with_base.inputs["True"])
    link(with_base.outputs[0], gout.inputs[0])

    columns = (
        (gin,), (sub, edge_vs), (tri, edge_len), (use_tri,), (cap, rnd), (amount, prox), (half,),
        (offset,), (jitter,), (onto,), (dual, keep), (split, to_curve, profile), (shrink, struts),
        (extrude, flip, flat), (solid,), (thick_or_flat,), (pick,), (base,), (with_base,), (gout,),
    )
    for i, col in enumerate(columns):
        for j, node in enumerate(col):
            node.location = (i * 200, -j * 220)
    return ng


def node_group():
    """The shared node group (rebuilt under a new name if an older version is found)."""
    for ng in bpy.data.node_groups:
        if ng.bl_idname == 'GeometryNodeTree' and ng.get("sts_cells_version") == VERSION:
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
