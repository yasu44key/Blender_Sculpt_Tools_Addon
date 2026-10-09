"""Add parametric solids at the 3D cursor: spindle, egg family, gear, star, platonic.

Replaces: special_object_maker_addon.py, platonic_solids_generator.py

All values live on the operators (adjustable afterwards with F9); nothing is
stored on the Scene. Torus and Pyramid are left to Blender's own Torus / Cone.
"""

import math

import bpy
import bmesh
from mathutils import Vector


# ---------------------------------------------------------------------------
# Common helpers

def _to_object_mode(context):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def _link_at_cursor(context, bm, name):
    """Finish the bmesh into a new object at the 3D cursor; select only it."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = context.scene.cursor.location
    context.collection.objects.link(obj)
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj


def _ring(bm, radius, z, segments):
    out = []
    for i in range(segments):
        a = math.tau * i / segments
        out.append(bm.verts.new((radius * math.cos(a), radius * math.sin(a), z)))
    return out


def _fan(bm, apex, ring):
    n = len(ring)
    for i in range(n):
        bm.faces.new((apex, ring[i], ring[(i + 1) % n]))


def _bridge(bm, ring_a, ring_b):
    n = len(ring_a)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ring_a[i], ring_b[i], ring_b[j], ring_a[j]))


# ---------------------------------------------------------------------------

class MESH_OT_sts_add_spindle(bpy.types.Operator):
    """Add a spindle: one equatorial ring with triangle fans to the top and bottom tips"""
    bl_idname = "mesh.sts_add_spindle"
    bl_label = "Spindle"
    bl_options = {'REGISTER', 'UNDO'}

    radius: bpy.props.FloatProperty(name="Radius", default=1.0, min=0.01, max=10.0, unit='LENGTH')
    height: bpy.props.FloatProperty(name="Height", default=2.0, min=0.01, max=20.0, unit='LENGTH')
    segments: bpy.props.IntProperty(name="Segments", default=32, min=3, max=128)

    def execute(self, context):
        _to_object_mode(context)
        bm = bmesh.new()
        ring = _ring(bm, self.radius, 0.0, self.segments)
        _fan(bm, bm.verts.new((0, 0, self.height / 2)), ring)
        _fan(bm, bm.verts.new((0, 0, -self.height / 2)), ring)
        _link_at_cursor(context, bm, "Spindle")
        return {'FINISHED'}


# ---------------------------------------------------------------------------

# preset -> (rho1, rho2, cylinder height as a multiple of R, object name)
_EGG_PRESETS = {
    'EGG': (0.9, 0.7, 0.0, "Egg"),
    'SPHERE': (1.0, 1.0, 0.0, "Sphere"),
    'CAPSULE': (1.0, 1.0, 1.0, "Capsule"),
    'LEMON': (0.5, 0.5, 0.0, "Lemon"),
    'ASYM': (2.0, 1.0, 0.5, "Asymmetric"),
}


def _update_egg_preset(self, _context):
    r1, r2, cyl, _name = _EGG_PRESETS[self.preset]
    self.rho1 = r1
    self.rho2 = r2
    self.cyl_height = cyl * self.radius


class MESH_OT_sts_add_egg(bpy.types.Operator):
    """Add an egg / capsule: bottom and top half-ellipsoids around a cylinder section"""
    bl_idname = "mesh.sts_add_egg"
    bl_label = "Egg / Capsule"
    bl_options = {'REGISTER', 'UNDO'}

    preset: bpy.props.EnumProperty(
        name="Preset",
        items=[('EGG', "Egg", ""), ('SPHERE', "Sphere", ""), ('CAPSULE', "Capsule", ""),
               ('LEMON', "Lemon", ""), ('ASYM', "Asymmetric", "")],
        default='EGG',
        update=_update_egg_preset,
    )
    radius: bpy.props.FloatProperty(name="Radius", default=1.0, min=0.01, max=10.0, unit='LENGTH')
    rho1: bpy.props.FloatProperty(
        name="Bottom Curvature", default=0.9, min=0.1, max=5.0,
        description="Curvature radius of the bottom as a fraction of R (1.0 = hemisphere)")
    rho2: bpy.props.FloatProperty(
        name="Top Curvature", default=0.7, min=0.1, max=5.0,
        description="Curvature radius of the top as a fraction of R (1.0 = hemisphere)")
    cyl_height: bpy.props.FloatProperty(name="Cylinder Height", default=0.0, min=0.0, max=20.0,
                                        unit='LENGTH')
    segments: bpy.props.IntProperty(name="Segments", default=32, min=3, max=128)
    rings: bpy.props.IntProperty(name="Rings", default=8, min=2, max=32,
                                 description="Rings per half")

    def execute(self, context):
        _to_object_mode(context)
        R, segs, hs = self.radius, self.segments, self.rings
        # h = R^2 / (rho * R): rho is the curvature radius as a fraction of R
        h1 = R * R / (self.rho1 * R)
        h2 = R * R / (self.rho2 * R)
        cyl = self.cyl_height
        z_ofs = (cyl + h2 - h1) / 2  # put the whole shape's centre at the origin

        bm = bmesh.new()
        rings = []
        for j in range(1, hs + 1):  # bottom half-ellipsoid (above the south pole -> equator)
            phi = -math.pi / 2 + j * (math.pi / 2) / hs
            rings.append(_ring(bm, R * math.cos(phi), h1 * math.sin(phi) - z_ofs, segs))
        if cyl > 1e-9:
            rings.append(_ring(bm, R, cyl - z_ofs, segs))
        for j in range(1, hs):  # top half-ellipsoid (above the cylinder -> below the north pole)
            phi = j * (math.pi / 2) / hs
            rings.append(_ring(bm, R * math.cos(phi), cyl + h2 * math.sin(phi) - z_ofs, segs))
        _fan(bm, bm.verts.new((0, 0, -h1 - z_ofs)), rings[0])
        for k in range(len(rings) - 1):
            _bridge(bm, rings[k], rings[k + 1])
        _fan(bm, bm.verts.new((0, 0, cyl + h2 - z_ofs)), rings[-1])

        r1, r2, _cyl, name = _EGG_PRESETS[self.preset]
        if abs(self.rho1 - r1) > 1e-9 or abs(self.rho2 - r2) > 1e-9:
            name = "Egg"  # numbers moved away from the preset
        _link_at_cursor(context, bm, name)
        return {'FINISHED'}


# ---------------------------------------------------------------------------

class MESH_OT_sts_add_gear(bpy.types.Operator):
    """Add a gear: one tooth = valley + two tip points, walls as quads, caps fan- or ring-filled"""
    bl_idname = "mesh.sts_add_gear"
    bl_label = "Gear"
    bl_options = {'REGISTER', 'UNDO'}

    teeth: bpy.props.IntProperty(name="Teeth", default=12, min=3, max=128)
    inner_radius: bpy.props.FloatProperty(name="Inner Radius", default=0.6, min=0.01, max=10.0,
                                          unit='LENGTH')
    outer_radius: bpy.props.FloatProperty(name="Outer Radius", default=1.0, min=0.01, max=10.0,
                                          unit='LENGTH')
    depth: bpy.props.FloatProperty(name="Plate Thickness", default=0.3, min=0.01, max=10.0, unit='LENGTH')
    tooth_ratio: bpy.props.FloatProperty(
        name="Tooth Width", default=0.5, min=0.1, max=0.9,
        description="Tip width as a fraction of one tooth's angle (bigger = flatter tips)")
    hole_radius: bpy.props.FloatProperty(name="Hole Radius", default=0.0, min=0.0, max=10.0,
                                         unit='LENGTH', description="0 = no hole")

    def execute(self, context):
        if self.hole_radius >= self.inner_radius:
            # the hole would cut through the valleys and turn the caps inside out
            self.hole_radius = self.inner_radius * 0.9
            self.report({'WARNING'}, "Hole Radius must be smaller than Inner Radius")
        _to_object_mode(context)
        delta = math.tau / self.teeth
        tip = self.tooth_ratio * delta
        gap = (delta - tip) / 2
        profile = []  # (angle, radius): valley, tip left, tip right per tooth
        for i in range(self.teeth):
            base = i * delta
            profile.append((base, self.inner_radius))
            profile.append((base + gap, self.outer_radius))
            profile.append((base + gap + tip, self.outer_radius))
        n = len(profile)

        bm = bmesh.new()
        z = self.depth / 2
        top = [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a, r in profile]
        bot = [bm.verts.new((r * math.cos(a), r * math.sin(a), -z)) for a, r in profile]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((top[i], top[j], bot[j], bot[i]))  # side wall

        if self.hole_radius > 1e-9:
            hr = self.hole_radius
            htop = [bm.verts.new((hr * math.cos(a), hr * math.sin(a), z)) for a, _r in profile]
            hbot = [bm.verts.new((hr * math.cos(a), hr * math.sin(a), -z)) for a, _r in profile]
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((top[i], top[j], htop[j], htop[i]))  # top cap ring
                bm.faces.new((bot[i], hbot[i], hbot[j], bot[j]))  # bottom cap ring
                bm.faces.new((htop[i], hbot[i], hbot[j], htop[j]))  # hole wall
        else:
            ct = bm.verts.new((0, 0, z))
            cb = bm.verts.new((0, 0, -z))
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((ct, top[i], top[j]))
                bm.faces.new((cb, bot[j], bot[i]))

        _link_at_cursor(context, bm, "Gear")
        return {'FINISHED'}


# ---------------------------------------------------------------------------

class MESH_OT_sts_add_star(bpy.types.Operator):
    """Add a star prism: outer / inner points alternating, caps as triangle fans"""
    bl_idname = "mesh.sts_add_star"
    bl_label = "Star"
    bl_options = {'REGISTER', 'UNDO'}

    points: bpy.props.IntProperty(name="Tips", description="Number of points of the star", default=5, min=3, max=16)
    inner_radius: bpy.props.FloatProperty(name="Inner Radius", default=0.4, min=0.01, max=10.0,
                                          unit='LENGTH')
    outer_radius: bpy.props.FloatProperty(name="Outer Radius", default=1.0, min=0.01, max=10.0,
                                          unit='LENGTH')
    depth: bpy.props.FloatProperty(name="Plate Thickness", default=0.3, min=0.01, max=10.0, unit='LENGTH')

    def execute(self, context):
        _to_object_mode(context)
        profile = []
        for i in range(self.points):
            profile.append((math.tau * i / self.points, self.outer_radius))
            profile.append((math.tau * (i + 0.5) / self.points, self.inner_radius))
        n = len(profile)

        bm = bmesh.new()
        z = self.depth / 2
        top = [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a, r in profile]
        bot = [bm.verts.new((r * math.cos(a), r * math.sin(a), -z)) for a, r in profile]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((top[i], top[j], bot[j], bot[i]))
        ct = bm.verts.new((0, 0, z))
        cb = bm.verts.new((0, 0, -z))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ct, top[i], top[j]))
            bm.faces.new((cb, bot[j], bot[i]))

        _link_at_cursor(context, bm, "Star")
        return {'FINISHED'}


# ---------------------------------------------------------------------------

_PHI = (1.0 + math.sqrt(5.0)) / 2.0

_PLATONIC_NAMES = {
    'TETRA': "Tetrahedron", 'CUBE': "Cube", 'OCTA': "Octahedron",
    'DODECA': "Dodecahedron", 'ICOSA': "Icosahedron", 'TRUNC_ICOSA': "Truncated Icosahedron",
}


def _platonic_coords(solid):
    def cyc(x, y, z):  # the three cyclic permutations
        return [(x, y, z), (y, z, x), (z, x, y)]

    coords = []
    if solid == 'TETRA':
        coords = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    elif solid == 'CUBE':
        coords = [(sx, sy, sz) for sx in (1, -1) for sy in (1, -1) for sz in (1, -1)]
    elif solid == 'OCTA':
        for sx in (1, -1):
            coords += cyc(sx, 0, 0)
    elif solid == 'DODECA':
        coords = [(sx, sy, sz) for sx in (1, -1) for sy in (1, -1) for sz in (1, -1)]
        for sy in (1, -1):
            for sz in (1, -1):
                coords += cyc(0, sy / _PHI, sz * _PHI)
    elif solid == 'ICOSA':
        for sy in (1, -1):
            for sz in (1, -1):
                coords += cyc(0, sy, sz * _PHI)
    elif solid == 'TRUNC_ICOSA':
        for sy in (1, -1):
            for sz in (1, -1):
                coords += cyc(0, sy, 3 * sz * _PHI)
        for sx in (1, -1):
            for sy in (1, -1):
                for sz in (1, -1):
                    coords += cyc(sx, sy * (2 + _PHI), sz * 2 * _PHI)
        for sx in (1, -1):
            for sy in (1, -1):
                for sz in (1, -1):
                    coords += cyc(sx * _PHI, 2 * sy, sz * (2 * _PHI + 1))
    return coords


class MESH_OT_sts_add_platonic(bpy.types.Operator):
    """Add a platonic solid (or a truncated icosahedron) on the circumsphere of the given size"""
    bl_idname = "mesh.sts_add_platonic"
    bl_label = "Platonic Solid"
    bl_options = {'REGISTER', 'UNDO'}

    solid: bpy.props.EnumProperty(
        name="Solid",
        items=[('TETRA', "Tetrahedron", ""), ('CUBE', "Cube", ""), ('OCTA', "Octahedron", ""),
               ('DODECA', "Dodecahedron", ""), ('ICOSA', "Icosahedron", ""),
               ('TRUNC_ICOSA', "Truncated Icosahedron", "")],
        default='TETRA',
    )
    size: bpy.props.FloatProperty(name="Size", default=1.0, min=0.01, max=100.0, unit='LENGTH',
                                  description="Circumsphere radius")

    def execute(self, context):
        _to_object_mode(context)
        bm = bmesh.new()
        for c in _platonic_coords(self.solid):
            bm.verts.new(Vector(c).normalized() * self.size)
        bmesh.ops.convex_hull(bm, input=bm.verts[:])
        stray = [v for v in bm.verts if not v.link_faces]
        if stray:
            bmesh.ops.delete(bm, geom=stray, context='VERTS')
        # merge the hull's coplanar triangles into one face per flat polygon
        bmesh.ops.dissolve_limit(bm, angle_limit=0.01, verts=bm.verts[:], edges=bm.edges[:])
        _link_at_cursor(context, bm, _PLATONIC_NAMES[self.solid])
        return {'FINISHED'}


# ---------------------------------------------------------------------------

SHAPES = (
    (MESH_OT_sts_add_spindle, 'MESH_CYLINDER'),
    (MESH_OT_sts_add_egg, 'MESH_UVSPHERE'),
    (MESH_OT_sts_add_gear, 'MOD_SCREW'),
    (MESH_OT_sts_add_star, 'MESH_CONE'),
    (MESH_OT_sts_add_platonic, 'MESH_ICOSPHERE'),
)


def add_menu(self, _context):
    layout = self.layout
    layout.separator()
    for op, icon in SHAPES:
        layout.operator(op.bl_idname, icon=icon)


classes = tuple(op for op, _icon in SHAPES)
