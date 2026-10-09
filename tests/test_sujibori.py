"""Functional tests for modules/sujibori. Run through tests/run_tests.sh."""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

W = 0.04


def logic():
    return submodule("modules.sujibori.logic")


def sphere():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
    return bpy.context.object


def ring_curve(z, outside=1.05, name="Line"):
    """Closed curve around the sphere at height z, drawn `outside` x off the surface."""
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new('BEZIER')
    n = 16
    sp.bezier_points.add(n - 1)
    sp.use_cyclic_u = True
    r = math.sqrt(1 - z * z) * outside
    for i, bp in enumerate(sp.bezier_points):
        a = 2 * math.pi * i / n
        bp.co = (r * math.cos(a), r * math.sin(a), z * outside)
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    return o


def select_only(active, *others):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in (active,) + others:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def evaluated(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return obj.evaluated_get(dg).data


def groove_bottom(obj, z=0.0):
    me = evaluated(obj)
    near = [v.co.length for v in me.vertices if abs(v.co.z - z) < 0.01]
    return min(near) if near else None


def setup(method, *lines):
    t = sphere()
    for ln in lines:
        ln.select_set(True)
    select_only(t)
    r = bpy.ops.object.sts_sujibori_setup(method=method)
    t.sts_sujibori.width = W
    if lines:
        select_only(t, *lines)
        bpy.ops.object.sts_sujibori_add_lines()
    return t, r


# ---------------------------------------------------------------- tests

def test_registered():
    check("module listed in MODULES", "sujibori" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.sujibori").META["tabs"] == ("Model",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_sujibori", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    s = bpy.types.Object.bl_rna.properties.get("sts_sujibori")
    check("settings stored on the object", s is not None)
    P = bpy.context.scene.objects[0].sts_sujibori.bl_rna.properties if bpy.context.scene.objects else None
    sphere()
    P = bpy.context.object.sts_sujibori.bl_rna.properties
    check("solver default MANIFOLD", P["solver"].default == 'MANIFOLD')
    check("width is a length", P["width"].unit == 'LENGTH')
    check("lines / cutters are collection pointers",
          P["lines"].fixed_type.identifier == 'Collection' and P["cutters"].fixed_type.identifier == 'Collection')


def test_live_cuts_off_surface_line_at_half_width():
    line = ring_curve(0.0)
    t, r = setup('LIVE', line)
    check("setup finished", r == {'FINISHED'}, str(r))
    check("GN modifier added", t.modifiers.get(logic().GN_MOD) is not None)
    check("line moved into the line collection", line.name in t.sts_sujibori.lines.objects)
    b = groove_bottom(t)
    check("groove depth = width / 2 even though the line is 5% off the surface",
          b is not None and abs(b - (1.0 - W / 2)) < 0.004, str(b))


def test_live_follows_the_line():
    line = ring_curve(0.0)
    t, _ = setup('LIVE', line)
    before = groove_bottom(t, 0.0)
    line.location.z = 0.3
    after_old = groove_bottom(t, 0.0)
    check("live: groove left the old place when the line moved",
          before is not None and (after_old is None or after_old > 0.995), f"{before} -> {after_old}")


def test_live_width_change():
    line = ring_curve(0.0)
    t, _ = setup('LIVE', line)
    t.sts_sujibori.width = 0.08
    b = groove_bottom(t)
    check("width change updates the live groove", b is not None and abs(b - 0.96) < 0.005, str(b))


def test_boolean_snapshot():
    line = ring_curve(0.0)
    t, r = setup('BOOLEAN', line)
    check("boolean modifier added", t.modifiers.get(logic().BOOL_MOD) is not None)
    check("one cutter per line", len(t.sts_sujibori.cutters.objects) == 1,
          str(len(t.sts_sujibori.cutters.objects)))
    b = groove_bottom(t)
    check("boolean: off-surface line still cuts (centre line projected) at width / 2",
          b is not None and abs(b - (1.0 - W / 2)) < 0.004, str(b))
    line.location.z = 0.3
    check("boolean: no change until Update Grooves", abs(groove_bottom(t) - b) < 1e-6)
    select_only(t)
    bpy.ops.object.sts_sujibori_update()
    after = groove_bottom(t, 0.0)
    check("boolean: Update Grooves moves the groove", after is None or after > 0.995, str(after))


def test_switch_method_no_duplicates():
    line = ring_curve(0.0)
    t, _ = setup('LIVE', line)
    t.sts_sujibori.method = 'BOOLEAN'
    t.sts_sujibori.method = 'LIVE'
    t.sts_sujibori.method = 'BOOLEAN'
    kinds = [m.type for m in t.modifiers]
    check("switching keeps exactly one groove modifier", kinds == ['BOOLEAN'], str(kinds))
    t.sts_sujibori.method = 'LIVE'
    kinds = [m.type for m in t.modifiers]
    check("back to live: only the GN modifier", kinds == ['NODES'], str(kinds))
    check("live: cutters cleared", len(t.sts_sujibori.cutters.objects) == 0)
    b = groove_bottom(t)
    check("still carving after the switches", b is not None and b < 0.99, str(b))


def test_rename_does_not_break():
    line = ring_curve(0.0)
    t, _ = setup('BOOLEAN', line)
    t.name = "Renamed Target"
    line.name = "Renamed Line"
    select_only(t)
    r = bpy.ops.object.sts_sujibori_update()
    check("update after renaming", r == {'FINISHED'} and len(t.sts_sujibori.cutters.objects) == 1)
    check("panel can find the target of a renamed line", logic().target_of_line(line) is t)


def test_remove_line_keeps_curve():
    line = ring_curve(0.0)
    t, _ = setup('LIVE', line)
    select_only(t)
    bpy.ops.object.sts_sujibori_remove_line(line=line.name)
    check("line taken out of the line collection", line.name not in t.sts_sujibori.lines.objects)
    check("the curve itself still exists", line.name in bpy.data.objects and line.users_collection)
    b = groove_bottom(t)
    check("groove gone with the line", b is None or b > 0.995, str(b))


def test_add_line_strips_bevel():
    line = ring_curve(0.3)
    line.data.bevel_depth = 0.1
    t, _ = setup('LIVE', line)
    check("a line has no bevel of its own", line.data.bevel_depth == 0.0)


def test_teardown():
    line = ring_curve(0.0)
    t, _ = setup('BOOLEAN', line)
    select_only(t)
    bpy.ops.object.sts_sujibori_remove()
    check("no groove modifiers left", not t.modifiers)
    check("lines kept", line.name in bpy.data.objects)
    check("cutters collection removed", t.sts_sujibori.cutters is None)
    check("can be set up again", bpy.ops.object.sts_sujibori_setup.poll())


def test_empty_lines_is_harmless():
    t, r = setup('LIVE')
    me = evaluated(t)
    check("no lines: mesh unchanged", len(me.polygons) == len(t.data.polygons), f"{len(me.polygons)}")


run([
    test_registered,
    test_live_cuts_off_surface_line_at_half_width,
    test_live_follows_the_line,
    test_live_width_change,
    test_boolean_snapshot,
    test_switch_method_no_duplicates,
    test_rename_does_not_break,
    test_remove_line_keeps_curve,
    test_add_line_strips_bevel,
    test_teardown,
    test_empty_lines_is_harmless,
])
