"""Functional tests for modules/strip_draw (drawing itself: tests/gui/gui_strip_draw.py)."""

import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def S():
    return submodule("modules.strip_draw.strip")


def sphere():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
    return bpy.context.object


def stroke(reverse=False, name="Stroke", y=0.0):
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new('POLY')
    n = 30
    sp.points.add(n - 1)
    idx = list(range(n))[::-1] if reverse else list(range(n))
    for p, i in zip(sp.points, idx):
        a = -0.9 + 1.8 * i / (n - 1)
        v = Vector((math.sin(a), y, math.cos(a))).normalized()
        p.co = (*v, 1.0)
        p.radius = 1.0
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    return o


def select(active, *others):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in (active,) + others:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def band(o):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    verts = [o.matrix_world @ v.co for v in me.vertices]
    faces = len(me.polygons)
    edges = {}
    for p in me.polygons:
        for k in p.edge_keys:
            edges[k] = edges.get(k, 0) + 1
    open_edges = sum(1 for c in edges.values() if c == 1)
    ev.to_mesh_clear()
    return verts, faces, open_edges


def setup(**kw):
    s = bpy.context.scene.sts_strip_draw
    s.target = None
    for k, v in kw.items():
        setattr(s, k, v)
    t = sphere()
    c = stroke()
    select(t, c)
    return t, c


def test_registered():
    check("module listed in MODULES", "strip_draw" in sys.modules[package()].MODULES)
    check("META tabs is ('Sculpt',)", submodule("modules.strip_draw").META["tabs"] == ("Sculpt",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_strip_draw", None)
    check("panel in the Sculpt tab", p is not None and p.bl_category == submodule("core.tabs").SCULPT)
    P = bpy.context.scene.sts_strip_draw.bl_rna.properties
    check("settings: lengths", all(P[k].unit == 'LENGTH' for k in ("width", "offset", "thickness", "voxel_size")))
    check("settings: styles", {i.identifier for i in P["style"].enum_items} == {'RIBBON', 'CLAY'})


def test_ribbon_lies_on_the_surface():
    t, c = setup(width=0.1, offset=0.01, thickness=0.0, style='RIBBON')
    r = bpy.ops.object.sts_strip_from_curves()
    check("from curves: finished, modifier with the target", r == {'FINISHED'} and S().get(c) is not None
          and S().get_input(S().get(c), "Target") is t)
    verts, faces, _open = band(c)
    rr = [v.length for v in verts]
    check("flat ribbon: on the surface + offset", verts and all(abs(x - 1.01) < 0.005 for x in rr), f"{min(rr)}..{max(rr)}")
    ys = [v.y for v in verts]
    check("ribbon: width across the stroke (y from -0.05 to 0.05)", abs(max(ys) - 0.05) < 0.003 and abs(min(ys) + 0.05) < 0.003,
          f"{min(ys)}..{max(ys)}")


def test_thick_band_outward_either_direction():
    for reverse in (False, True):
        bpy.ops.wm.read_homefile(use_empty=True)
        s = bpy.context.scene.sts_strip_draw
        s.target = None
        s.width, s.offset, s.thickness, s.style = 0.1, 0.0, 0.05, 'RIBBON'
        t = sphere()
        c = stroke(reverse=reverse)
        select(t, c)
        bpy.ops.object.sts_strip_from_curves()
        verts, faces, open_edges = band(c)
        rr = [v.length for v in verts]
        check(f"thick band (drawn {'backward' if reverse else 'forward'}): from the surface outward",
              min(rr) > 0.995 and max(rr) > 1.04 and max(rr) < 1.06, f"{min(rr)}..{max(rr)}")
        check(f"thick band ({'backward' if reverse else 'forward'}): a closed slab", open_edges == 0, str(open_edges))


def test_pressure_width():
    t, c = setup(width=0.1, offset=0.0, thickness=0.0)
    for i, p in enumerate(c.data.splines[0].points):
        p.radius = 0.2 if i < 15 else 1.0
    bpy.ops.object.sts_strip_from_curves()
    verts, _f, _o = band(c)
    narrow = [abs(v.y) for v in verts if v.x < -0.3]
    wide = [abs(v.y) for v in verts if v.x > 0.3]
    check("pen pressure (radius) scales the width", max(narrow) < 0.012 and max(wide) > 0.045,
          f"{max(narrow)} {max(wide)}")


def test_each_strip_keeps_its_own_values():
    t = sphere()
    s = bpy.context.scene.sts_strip_draw
    s.target = None
    s.width, s.thickness = 0.1, 0.0
    a = stroke(name="A", y=0.0)
    b = stroke(name="B", y=0.3)
    select(t, a, b)
    bpy.ops.object.sts_strip_from_curves()
    before = band(b)[0]
    S().set_input(S().get(a), "Width", 0.3)
    after = band(b)[0]
    check("changing one strip leaves the others alone (old armor rebuilt a shared group)",
          all((p - q).length < 1e-6 for p, q in zip(before, after)))
    check("the two strips share one node group", S().get(a).node_group is S().get(b).node_group)


def test_clay_and_to_mesh():
    t, c = setup(width=0.1, offset=0.0, thickness=0.03, style='CLAY', voxel_size=0.01)
    bpy.ops.object.sts_strip_from_curves()
    verts, faces, open_edges = band(c)
    check("clay: a closed remeshed lump", faces > 100 and open_edges == 0, f"{faces} {open_edges}")
    select(c)
    r = bpy.ops.object.sts_strip_to_mesh()
    o = bpy.context.active_object
    check("to mesh: a mesh object with the band", r == {'FINISHED'} and o.type == 'MESH' and len(o.data.polygons) > 100)


def test_start_finish():
    t = sphere()
    select(t)
    r = bpy.ops.curve.sts_strip_start()
    o = bpy.context.active_object
    check("start: a curve in Edit Mode with the strip modifier",
          r == {'FINISHED'} and o.type == 'CURVE' and bpy.context.mode == 'EDIT_CURVE' and S().get(o) is not None, str(r))
    check("start: the surface remembered", bpy.context.scene.sts_strip_draw.target is t)
    r = bpy.ops.curve.sts_strip_finish()
    check("finish with nothing drawn: back to Object Mode, empty strip removed",
          r == {'FINISHED'} and bpy.context.mode == 'OBJECT' and not [x for x in bpy.data.objects if x.type == 'CURVE'])
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.scene.sts_strip_draw.target = None
    bpy.ops.object.empty_add()
    check("start without a surface -> CANCELLED", bpy.ops.curve.sts_strip_start() == {'CANCELLED'})


run([
    test_registered,
    test_ribbon_lies_on_the_surface,
    test_thick_band_outward_either_direction,
    test_pressure_width,
    test_each_strip_keeps_its_own_values,
    test_clay_and_to_mesh,
    test_start_finish,
])
