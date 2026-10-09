"""Tests for the Thickness Guard Brush logic (modules/thickness_guard/brush.py).
The modal itself: tests/gui/gui_thickness_brush.py"""

import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, run, submodule  # noqa: E402


def B():
    return submodule("modules.thickness_guard.brush")


def plate(thick=0.05, location=(0, 0, 0), scale=1.0):
    """A 2 x 2 plate, `thick` thick, subdivided 16 x 16 on top and bottom."""
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(2.0, 2.0, thick), verts=r["verts"])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=15, use_grid_fill=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Plate")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("Plate", me)
    o.location = location
    o.scale = (scale, scale, scale)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    bpy.context.view_layer.update()
    return o


def gap_at(o, x, y):
    """World thickness of the plate at (x, y): top z - bottom z of the nearest vertices."""
    mw = o.matrix_world
    pts = [mw @ v.co for v in o.data.vertices]
    near = [p for p in pts if abs(p.x - x) < 0.07 and abs(p.y - y) < 0.07]
    return max(p.z for p in near) - min(p.z for p in near)


def test_registered():
    check("brush operator registered", hasattr(bpy.types, "OBJECT_OT_sts_thickness_guard_brush"))
    P = bpy.context.scene.sts_thickness_brush.bl_rna.properties
    check("brush settings are lengths", P["min_thickness"].unit == 'LENGTH' and P["radius"].unit == 'LENGTH')


def test_dab_thickens_only_under_the_brush():
    o = plate()
    n = B().guard_at(o, (0, 0, 0.025), radius=0.5, min_thickness=0.1, strength=1.0)
    check("dab: vertices moved", n > 0, str(n))
    check("dab: centre brought to the minimum (both walls pushed out)", abs(gap_at(o, 0, 0) - 0.1) < 0.004,
          str(gap_at(o, 0, 0)))
    check("dab: softer toward the rim", 0.05 < gap_at(o, 0.4, 0) < gap_at(o, 0, 0) - 0.01, str(gap_at(o, 0.4, 0)))
    check("dab: outside the radius untouched", abs(gap_at(o, 0.8, 0.8) - 0.05) < 1e-6, str(gap_at(o, 0.8, 0.8)))
    before = [v.co.copy() for v in o.data.vertices]
    B().guard_at(o, (0, 0, 0.05), radius=0.5, min_thickness=0.1, strength=1.0)
    check("dab again: the centre does not grow past the minimum", abs(gap_at(o, 0, 0) - 0.1) < 0.004,
          str(gap_at(o, 0, 0)))
    check("a thick enough wall is left alone",
          B().guard_at(o, (0, 0, 0.05), radius=0.05, min_thickness=0.02, strength=1.0) == 0)
    del before


def test_strength_and_world_units():
    o = plate(location=(5, 0, 0), scale=2.0)            # world: 4 x 4 x 0.1
    B().guard_at(o, (5, 0, 0.05), radius=1.0, min_thickness=0.2, strength=0.5)
    g = gap_at(o, 5, 0)
    check("world units on a scaled object; strength 0.5 adds half the missing thickness",
          abs(g - 0.15) < 0.008, str(g))


def test_needs_object_or_sculpt_mode():
    o = plate()
    bpy.ops.object.mode_set(mode='EDIT')
    check("brush poll is false in Edit Mode", not bpy.ops.object.sts_thickness_guard_brush.poll())
    bpy.ops.object.mode_set(mode='OBJECT')
    del o


run([
    test_registered,
    test_dab_thickens_only_under_the_brush,
    test_strength_and_world_units,
    test_needs_object_or_sculpt_mode,
])
