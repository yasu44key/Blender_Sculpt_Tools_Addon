"""GUI-free logic for the NURBS Grid module.

Replaces: Draw_NURBS_Grid_Patch63.py (create_surface_grid / flip_nurbs_normal)

build_grid makes the surface the way the old tool did — one U-row NURBS spline,
then curve.extrude (TRANSLATION) in Edit Mode — because a NURBS spline's
point_count_u / point_count_v cannot be set directly. Every point's coordinates
and weight are written afterwards, so the extrude's own values do not matter.

flip reverses the V rows of each NURBS spline using spline.point_count_u (the
old tool's custom property nurbs_u_count is not needed).
"""

import bpy
from mathutils import Vector


def _surface_normal(obj):
    """Area-weighted mean world normal of the evaluated surface, or None."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    mw = obj.matrix_world
    n = Vector()
    for p in me.polygons:
        n += (mw @ p.normal) * p.area
    ev.to_mesh_clear()
    return n.normalized() if n.length > 1e-12 else None


def build_grid(context, points, u_count, view_vector=None):
    """Make a SURFACE object "NURBS Grid" from points placed row after row.

    points: list of (Vector co, float weight), world coordinates. Only full
    rows are used; fewer than 2 full rows -> None and nothing is created.
    With view_vector (the direction the view looks in) the surface is turned
    to face the viewer. The new object is the only selected one and active,
    in Object Mode.
    """
    u = max(2, int(u_count))
    total = (len(points) // u) * u
    v = total // u
    if v < 2:
        return None
    used = points[:total]

    curve = bpy.data.curves.new("GridSurface", type='SURFACE')
    curve.dimensions = '3D'
    obj = bpy.data.objects.new("NURBS Grid", curve)
    context.collection.objects.link(obj)

    for o in context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj

    spline = curve.splines.new('NURBS')
    spline.points.add(u - 1)
    for i in range(u):
        co, w = used[i]
        spline.points[i].co = (co.x, co.y, co.z, w)
    spline.use_endpoint_u = True
    spline.order_u = min(3, u)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.curve.select_all(action='SELECT')
    for _ in range(v - 1):
        bpy.ops.curve.extrude(mode='TRANSLATION')
    bpy.ops.object.mode_set(mode='OBJECT')

    spline = obj.data.splines[0]
    spline.use_endpoint_v = True
    spline.order_v = min(3, v)
    for i, (co, w) in enumerate(used):
        spline.points[i].co = (co.x, co.y, co.z, w)

    if view_vector is not None:
        n = _surface_normal(obj)
        if n is not None and n.dot(Vector(view_vector)) > 0.0:
            flip(obj)

    for o in context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj


def flip(obj):
    """Reverse the V rows of every NURBS spline (flips its normals).

    Points are stored row after row (points[v * u + u]); reversing the row
    order flips the surface side while keeping each U row's point order.
    Returns True when at least one spline was flipped.
    """
    flipped = False
    for spline in obj.data.splines:
        if spline.type != 'NURBS':
            continue
        u = spline.point_count_u
        v = spline.point_count_v
        if u < 1 or v < 2 or len(spline.points) != u * v:
            continue
        coords = [tuple(pt.co) for pt in spline.points]
        new_coords = []
        for row in range(v - 1, -1, -1):
            new_coords.extend(coords[row * u:(row + 1) * u])
        for pt, co in zip(spline.points, new_coords):
            pt.co = co
        flipped = True
    return flipped
