"""3D View helpers for modal operators that react to mouse clicks."""

from bpy_extras.view3d_utils import (region_2d_to_location_3d, region_2d_to_origin_3d,
                                     region_2d_to_vector_3d)
from mathutils import Vector

# Enum items for tools that place things under the mouse (Scene settings).
DEPTH_ITEMS = (
    ('SURFACE', "Snap to Surface", "Place on object surfaces (3D cursor depth when nothing is hit)"),
    ('CURSOR', "Cursor Depth", "Use the depth of the 3D cursor"),
    ('PLANE', "World Plane", "Place on a world plane, ignoring surfaces"),
)
PLANE_ITEMS = (
    ('XY', "XY", "World plane Z = 0"),
    ('XZ', "XZ", "World plane Y = 0"),
    ('YZ', "YZ", "World plane X = 0"),
)


def window_region_under_mouse(area, mouse_x, mouse_y):
    """The 3D View WINDOW region under the mouse (window coordinates), or None.

    A button in the sidebar starts the operator, so context.region is the
    sidebar; the WINDOW region is looked up from the area. The sidebar and
    header overlap the WINDOW region, so the mouse over them returns None.
    """
    if area is None:
        return None
    for r in area.regions:
        if (r.type != 'WINDOW' and r.width > 1 and r.height > 1
                and r.x <= mouse_x < r.x + r.width and r.y <= mouse_y < r.y + r.height):
            return None
    for r in area.regions:
        if (r.type == 'WINDOW' and r.data is not None
                and r.x <= mouse_x < r.x + r.width and r.y <= mouse_y < r.y + r.height):
            return r
    return None


def mouse_ray(region, mouse_x, mouse_y):
    """(origin, direction) in world space through the mouse position."""
    xy = (mouse_x - region.x, mouse_y - region.y)
    return (region_2d_to_origin_3d(region, region.data, xy),
            region_2d_to_vector_3d(region, region.data, xy))


def mouse_on_plane(region, mouse_x, mouse_y, depth_location):
    """World position under the mouse at the depth of `depth_location`."""
    xy = (mouse_x - region.x, mouse_y - region.y)
    return region_2d_to_location_3d(region, region.data, xy, depth_location)


_PLANE_NORMALS = {'XY': (0.0, 0.0, 1.0), 'XZ': (0.0, 1.0, 0.0), 'YZ': (1.0, 0.0, 0.0)}


def _excluded(obj, exclude):
    if obj is None or exclude is None:
        return False
    if isinstance(exclude, (list, tuple, set)):
        return obj in exclude
    return obj is exclude


def surface_point(scene, depsgraph, origin, direction, fallback, offset=0.0, exclude=None):
    """Ray-cast from origin along direction; return (Vector, hit).

    offset moves the hit point along the face normal. When the ray hits an
    excluded object (the mesh being drawn into) it is re-shot from just
    past that hit so the new geometry never snaps to itself. A miss returns
    (fallback, False).
    """
    origin = Vector(origin)
    direction = Vector(direction)
    if direction.length < 1e-12:
        return Vector(fallback), False
    direction.normalize()
    step = direction * 1e-4

    loc = origin
    for _ in range(32):
        hit, co, normal, _index, obj, _matrix = scene.ray_cast(depsgraph, loc, direction)
        if not hit:
            return Vector(fallback), False
        if _excluded(obj, exclude):
            loc = co + step
            continue
        if offset:
            co = co + normal * offset
        return co, True
    return Vector(fallback), False


def plane_point(origin, direction, axis):
    """Where the ray meets the world plane through the origin (XY -> Z = 0,
    XZ -> Y = 0, YZ -> X = 0), or None when the ray is parallel to the plane
    or the plane lies behind the ray.
    """
    normal = _PLANE_NORMALS.get(axis)
    if normal is None:
        return None
    origin = Vector(origin)
    direction = Vector(direction)
    denom = direction.dot(normal)
    if abs(denom) < 1e-12:
        return None
    t = -origin.dot(normal) / denom
    if t < 0.0:
        return None
    return origin + direction * t


def drag_far_enough(last_co, co, interval):
    """True when `co` is at least `interval` away from the last placed point.
    No last point (None) means the next point is always far enough.
    """
    if last_co is None:
        return True
    return (Vector(co) - Vector(last_co)).length >= interval


def pick_point(context, region, mouse_x, mouse_y, depth_mode, plane_axis='XY',
               offset=0.0, exclude=None):
    """World position under the mouse for a DEPTH_ITEMS mode.

    SURFACE: surface_point (3D cursor depth on a miss); CURSOR: 3D cursor depth;
    PLANE: plane_point (3D cursor depth when the plane is not hit).
    """
    cursor_depth = mouse_on_plane(region, mouse_x, mouse_y, context.scene.cursor.location)
    if depth_mode == 'CURSOR':
        return cursor_depth
    origin, direction = mouse_ray(region, mouse_x, mouse_y)
    if depth_mode == 'PLANE':
        co = plane_point(origin, direction, plane_axis)
        return co if co is not None else cursor_depth
    co, _hit = surface_point(context.scene, context.evaluated_depsgraph_get(), origin, direction,
                             cursor_depth, offset=offset, exclude=exclude)
    return co
