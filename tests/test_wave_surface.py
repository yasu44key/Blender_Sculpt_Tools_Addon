"""Functional tests for modules/wave_surface. Run through tests/run_tests.sh."""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402


def S():
    return submodule("modules.wave_surface.surface")


def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return o.evaluated_get(dg).data


def select_only(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def heights(o):
    """{(x, y): z} of the evaluated mesh, keyed by the original (rounded) x, y."""
    me = evaluated(o)
    base = o.data.vertices
    return {(round(base[i].co.x, 4), round(base[i].co.y, 4)): v.co.z for i, v in enumerate(me.vertices)}


def new_grid(**kw):
    r = bpy.ops.mesh.sts_wave_surface_add(**kw)
    return bpy.context.active_object, r


def zero_waves(mod):
    for k in range(1, 4):
        S().set_input(mod, f"Wave {k} Amplitude", 0.0)


def test_registered():
    check("module listed in MODULES", "wave_surface" in sys.modules[package()].MODULES)
    check("META tabs is ('Generate',)", submodule("modules.wave_surface").META["tabs"] == ("Generate",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_wave_surface", None)
    check("panel in the Generate tab", p is not None and p.bl_category == submodule("core.tabs").GENERATE)
    P = bpy.ops.mesh.sts_wave_surface_add.get_rna_type().properties
    check("size is a length", P["size"].unit == 'LENGTH')
    funcs = getattr(bpy.types.VIEW3D_MT_mesh_add.draw, "_draw_funcs", [])
    check("in Add > Mesh", any(getattr(f, "__module__", "").endswith("wave_surface.ops") for f in funcs))


def test_new_grid_at_cursor_selected():
    bpy.context.scene.cursor.location = (3.0, -2.0, 1.0)
    o, r = new_grid(size=4.0, resolution=20)
    check("add finished", r == {'FINISHED'}, str(r))
    check("at the 3D cursor", (o.location - bpy.context.scene.cursor.location).length < 1e-6, str(tuple(o.location)))
    check("selected and active", o.select_get() and bpy.context.view_layer.objects.active is o)
    check("grid resolution (21 x 21 vertices)", len(o.data.vertices) == 441, str(len(o.data.vertices)))
    check("modifier added", S().get(o) is not None)


def test_ring_wave_formula():
    o, _ = new_grid(size=4.0, resolution=40)
    mod = S().get(o)
    S().set_input(mod, "Wave 1 Amplitude", 0.3)
    S().set_input(mod, "Wave 1 Wavelength", 1.5)
    S().set_input(mod, "Wave 1 Center X", 0.5)
    S().set_input(mod, "Wave 1 Center Y", -0.2)
    S().set_input(mod, "Time Offset", 0.4)
    S().set_input(mod, "Wave 1 Speed", 0.7)
    worst = 0.0
    for (x, y), z in heights(o).items():
        r = math.hypot(x - 0.5, y + 0.2)
        want = 0.3 * math.sin(2 * math.pi / 1.5 * (r - 0.7 * 0.4))
        worst = max(worst, abs(z - want))
    check("h = A sin(2π/λ (r − v t)) around the center", worst < 1e-4, str(worst))


def test_quadratic_formula():
    o, _ = new_grid(size=2.0, resolution=10)
    mod = S().get(o)
    zero_waves(mod)
    coef = {"x² (a)": 0.3, "y² (b)": -0.2, "xy (c)": 0.5, "x (d)": 0.1, "y (e)": -0.4, "Constant (f)": 0.25}
    for k, v in coef.items():
        S().set_input(mod, k, v)
    worst = 0.0
    for (x, y), z in heights(o).items():
        want = 0.3 * x * x - 0.2 * y * y + 0.5 * x * y + 0.1 * x - 0.4 * y + 0.25
        worst = max(worst, abs(z - want))
    check("h = a x² + b y² + c xy + d x + e y + f", worst < 1e-4, str(worst))


def test_three_waves_add_up():
    o, _ = new_grid(size=4.0, resolution=20)
    mod = S().get(o)
    zero_waves(mod)
    single = []
    for k in range(1, 4):
        zero_waves(mod)
        S().set_input(mod, f"Wave {k} Amplitude", 0.2 * k)
        S().set_input(mod, f"Wave {k} Center X", 0.3 * k)
        single.append(heights(o))
    for k in range(1, 4):
        S().set_input(mod, f"Wave {k} Amplitude", 0.2 * k)
    total = heights(o)
    worst = max(abs(total[p] - sum(s[p] for s in single)) for p in total)
    check("waves add up", worst < 1e-4, str(worst))


def test_animation():
    o, _ = new_grid(size=4.0, resolution=20)
    mod = S().get(o)
    sc = bpy.context.scene
    sc.frame_set(1)
    h1 = heights(o)
    sc.frame_set(25)
    h2 = heights(o)
    check("Animate off: frame change does not move the surface",
          max(abs(h1[p] - h2[p]) for p in h1) < 1e-6)
    S().set_input(mod, "Animate", True)
    sc.frame_set(1)
    a1 = heights(o)
    sc.frame_set(25)
    a2 = heights(o)
    check("Animate on: the surface moves with the frame", max(abs(a1[p] - a2[p]) for p in a1) > 0.01)
    S().set_input(mod, "Animate", False)
    S().set_input(mod, "Time Offset", sc.frame_current / sc.render.fps)
    still = heights(o)
    check("Time Offset poses the same moment", max(abs(still[p] - a2[p]) for p in still) < 1e-4)


def test_along_normals_on_sphere():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16)
    s = bpy.context.object
    bpy.ops.object.sts_wave_surface_assign()
    mod = S().get(s)
    zero_waves(mod)
    S().set_input(mod, "Constant (f)", 0.2)
    S().set_input(mod, "Along Normals", True)
    rr = [v.co.length for v in evaluated(s).vertices]
    check("along normals: a constant grows the sphere evenly", max(abs(r - 1.2) for r in rr) < 0.01,
          f"{min(rr)}..{max(rr)}")


def test_assign_remove_shared():
    bpy.ops.mesh.primitive_plane_add(location=(-3, 0, 0))
    a = bpy.context.object
    bpy.ops.mesh.primitive_plane_add(location=(3, 0, 0))
    b = bpy.context.object
    a.select_set(True)
    r = bpy.ops.object.sts_wave_surface_assign()
    check("assign finished", r == {'FINISHED'}, str(r))
    check("one shared node group", S().get(a).node_group is S().get(b).node_group)
    bpy.ops.object.sts_wave_surface_assign()
    check("assign twice: no duplicate", sum(1 for m in a.modifiers if m.type == 'NODES') == 1)
    r = bpy.ops.object.sts_wave_surface_remove()
    check("removed", r == {'FINISHED'} and S().get(a) is None and S().get(b) is None)
    check("remove again -> CANCELLED", bpy.ops.object.sts_wave_surface_remove() == {'CANCELLED'})
    for x in list(bpy.context.selected_objects):
        x.select_set(False)
    check("assign with nothing selected -> CANCELLED", bpy.ops.object.sts_wave_surface_assign() == {'CANCELLED'})


def test_scatter_centers():
    o, _ = new_grid()
    mod = S().get(o)
    bpy.ops.object.sts_wave_surface_scatter(seed=3, spread=2.0)
    c1 = [S().get_input(mod, f"Wave {k} Center {a}") for k in range(1, 4) for a in "XY"]
    bpy.ops.object.sts_wave_surface_scatter(seed=3, spread=2.0)
    c2 = [S().get_input(mod, f"Wave {k} Center {a}") for k in range(1, 4) for a in "XY"]
    bpy.ops.object.sts_wave_surface_scatter(seed=4, spread=2.0)
    c3 = [S().get_input(mod, f"Wave {k} Center {a}") for k in range(1, 4) for a in "XY"]
    check("scatter: within the spread", all(abs(c) <= 2.0 for c in c1) and any(abs(c) > 1e-6 for c in c1))
    check("scatter: same seed, same centers", c1 == c2)
    check("scatter: other seed, other centers", c1 != c3)


def test_apply():
    o, _ = new_grid(size=4.0, resolution=10)
    want = heights(o)
    bpy.ops.object.modifier_apply(modifier=S().MOD_NAME)
    got = {(round(v.co.x, 4), round(v.co.y, 4)): v.co.z for v in o.data.vertices}
    check("apply bakes the surface", S().get(o) is None and max(abs(got[p] - want[p]) for p in got) < 1e-5)


def test_from_edit_mode():
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.object.mode_set(mode='EDIT')
    o, r = new_grid(size=2.0, resolution=4)
    check("from edit mode: a new object in Object Mode",
          r == {'FINISHED'} and bpy.context.mode == 'OBJECT' and o.name.startswith("Wave Surface"))


run([
    test_registered,
    test_new_grid_at_cursor_selected,
    test_ring_wave_formula,
    test_quadratic_formula,
    test_three_waves_add_up,
    test_animation,
    test_along_normals_on_sphere,
    test_assign_remove_shared,
    test_scatter_centers,
    test_apply,
    test_from_edit_mode,
])
