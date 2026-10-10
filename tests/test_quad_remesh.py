"""Spec for modules/quad_remesh (new tool). Run through tests/run_tests.sh.

Model tab. object.sts_quad_remesh rebuilds the active mesh as quads with QuadWild Bi-MDF,
whose DLLs come from an installed QRemeshify (not shipped: GPL). It runs in a separate
background Blender; blocking=True waits in place (scripts, tests).

  Object Mode -> the whole evaluated mesh; Edit Mode -> only the selected faces
  target_faces    about how many quads after mirroring (a pass loop corrects the scale)
  symmetry_x/y/z  cut, remesh one piece, "STS Mirror" (clip + merge) rebuilds the rest
  detect_sharp    edges sharper than sharp_angle become feature lines
  fit_to_source   "STS Fit" Shrinkwrap onto the source (the proxy loses fine detail)
  asymmetry       symmetry on a lopsided shape -> WARNING (the mirrored side floats off the
                  real surface and the fit folds it: a scanned head turned a few degrees)
  result          new object "<name>_Quad" with the source's transform, selected + active;
                  the source is never changed
  no engine       CANCELLED with an error (the panel shows where to get QRemeshify)
  guide lines     strokes of the visible annotation layers: a row of quad edges lies on each
                  (hidden layers are ignored)
  density map     density_source MASK / COLOR: painted areas get quads detail_ratio times smaller;
                  needs the STS QuadWild engine (QRemeshify's build -> ERROR); no mask -> WARNING
  project detail  object.sts_quad_project_detail on a result with "STS Fit": applies "STS Mirror",
                  drops "STS Fit", Multires to `levels`, snap + relax rounds baked into it
  detect creases  object.sts_quad_detect_creases -> annotation layers "STS Ridge" (convex) /
                  "STS Valley" (concave); 5.2+ only (Python writes strokes from 5.2)

The isolated test user folder has no QRemeshify: the tests point STS_QUADWILD_DIR at the
real one of this machine (and skip the engine tests if it is missing).
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from _testlib import check, package, run, submodule  # noqa: E402

STS_ENGINE = os.path.join(os.environ.get("APPDATA", ""),     # STS QuadWild Engine (density maps)
                          r"Blender Foundation\Blender\5.2\extensions\user_default\sts_quadwild_engine\lib")
REAL_ENGINE = os.path.join(os.environ.get("APPDATA", ""),
                           r"Blender Foundation\Blender\5.2\extensions\user_default\qremeshify\lib")


def use_engine(on):
    if on:
        os.environ["STS_QUADWILD_DIR"] = REAL_ENGINE
    else:
        os.environ.pop("STS_QUADWILD_DIR", None)


def egg(name="Egg"):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0)
    o = bpy.context.object
    o.name = name
    for v in o.data.vertices:
        v.co.z *= 1.5
    return o


def result_of(src):
    return bpy.data.objects.get(src.name + "_Quad")


def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return o.evaluated_get(dg).data


def test_registered():
    check("module listed in MODULES", "quad_remesh" in sys.modules[package()].MODULES)
    check("META tabs is ('Model',)", submodule("modules.quad_remesh").META["tabs"] == ("Model",))
    p = getattr(bpy.types, "VIEW3D_PT_sts_quad_remesh", None)
    check("panel in the Model tab", p is not None and p.bl_category == submodule("core.tabs").MODEL)
    P = bpy.ops.object.sts_quad_remesh.get_rna_type().properties
    check("target faces default 8000", P["target_faces"].default == 8000)
    check("sharp angle: ANGLE, 35 deg", P["sharp_angle"].subtype == 'ANGLE'
          and abs(P["sharp_angle"].default - math.radians(35)) < 1e-5)
    check("blocking is hidden and not remembered", P["blocking"].is_hidden and P["blocking"].is_skip_save)
    check("no Scene copy of the settings", not any(k.startswith("sts_quad") for k in bpy.types.Scene.bl_rna.properties.keys()))


def test_no_engine():
    use_engine(False)
    eng = submodule("modules.quad_remesh.engine")
    check("no engine in the isolated user folder", eng.find_engine() is None)
    o = egg()
    try:   # an ERROR report reaches Python as RuntimeError
        r = bpy.ops.object.sts_quad_remesh(blocking=True)
    except RuntimeError as exc:
        r = {'CANCELLED'} if "QRemeshify" in str(exc) else {'ERROR'}
    check("no engine -> CANCELLED with an error", r == {'CANCELLED'})
    check("no engine -> nothing created", result_of(o) is None)
    os.environ["STS_QUADWILD_DIR"] = os.path.dirname(__file__)   # a folder without the DLLs
    check("a folder without the DLLs is not an engine", eng.find_engine() is None)
    use_engine(False)


def engine_ready():
    ok = os.path.isfile(os.path.join(REAL_ENGINE, "lib_quadwild.dll"))
    check("QRemeshify engine present on this machine", ok, REAL_ENGINE)
    use_engine(ok)
    return ok


def test_basic():
    if not engine_ready():
        return
    o = egg()
    o.location = (3.0, 1.0, 0.5)
    o.rotation_euler = (0.3, 0.0, 0.7)
    bpy.context.view_layer.update()
    n0 = len(o.data.vertices)
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=1500)
    q = result_of(o)
    check("finished, made <name>_Quad", r == {'FINISHED'} and q is not None)
    if q is None:
        return
    quads = sum(1 for p in q.data.polygons if len(p.vertices) == 4)
    n = len(q.data.polygons)
    check("all faces are quads", quads == n, f"{quads}/{n}")
    check("face count near the target (+-25%)", 1125 <= n <= 1875, str(n))
    check("result selected and active", q.select_get() and bpy.context.view_layer.objects.active == q)
    check("source unchanged", len(o.data.vertices) == n0 and not o.hide_get())
    check("same transform as the source",
          all(abs(a - b) < 1e-6 for ra, rb in zip(q.matrix_world, o.matrix_world) for a, b in zip(ra, rb)))
    fit = q.modifiers.get("STS Fit")
    check("STS Fit shrinkwraps onto the source", fit is not None and fit.type == 'SHRINKWRAP' and fit.target == o)
    # the result lies on the egg: local x^2 + y^2 + (z/1.5)^2 ~ 1
    me = evaluated(q)
    dev = max(abs(math.sqrt(v.co.x ** 2 + v.co.y ** 2 + (v.co.z / 1.5) ** 2) - 1.0) for v in me.vertices)
    check("result lies on the source surface", dev < 0.03, f"{dev:.4f}")


def test_symmetry():
    if not engine_ready():
        return
    o = egg()
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=1600, symmetry_x=True, fit_to_source=False)
    q = result_of(o)
    check("symmetry: finished", r == {'FINISHED'} and q is not None)
    if q is None:
        return
    m = q.modifiers.get("STS Mirror")
    check("STS Mirror on X with clipping", m is not None and tuple(m.use_axis) == (True, False, False) and m.use_clip)
    check("the base mesh is one half (x >= 0)", min(v.co.x for v in q.data.vertices) > -1e-4)
    me = evaluated(q)
    n = len(me.polygons)
    check("mirrored face count near the target (+-25%)", 1200 <= n <= 2000, str(n))
    bm = bmesh.new()
    bm.from_mesh(me)
    check("no open seam after mirroring", not any(e.is_boundary for e in bm.edges))
    bm.free()
    last = submodule("modules.quad_remesh.ops").RUN["last"]
    check("symmetric egg: no asymmetry warning", last is not None and last.asymmetry == [], str(last and last.asymmetry))


def test_asymmetry_warning():
    if not engine_ready():
        return
    o = egg()
    for v in o.data.vertices:          # bulge on +X only: a lopsided egg
        if v.co.x > 0:
            v.co.x *= 1.0 + 0.4 * v.co.x
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=1200, symmetry_x=True)
    last = submodule("modules.quad_remesh.ops").RUN["last"]
    check("lopsided egg + symmetry: still finished", r == {'FINISHED'} and result_of(o) is not None)
    check("lopsided egg + symmetry: warns about X", last is not None and [a for a, _, _ in last.asymmetry] == ["X"],
          str(last and last.asymmetry))


def test_edit_mode_selection():
    if not engine_ready():
        return
    o = egg()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    r = bpy.ops.object.sts_quad_remesh(blocking=True)
    check("edit mode, nothing selected -> CANCELLED", r == {'CANCELLED'} and result_of(o) is None)
    bm = bmesh.from_edit_mesh(o.data)
    for f in bm.faces:
        f.select_set(f.calc_center_median().z > 0.0)
    bmesh.update_edit_mesh(o.data)
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=800, fit_to_source=False)
    q = result_of(o)
    check("edit mode: finished, back in Object Mode", r == {'FINISHED'} and q is not None and bpy.context.mode == 'OBJECT')
    if q is None:
        return
    check("only the selected (upper) half was remeshed", min(v.co.z for v in q.data.vertices) > -0.1)
    check("source keeps all its faces", len(o.data.polygons) == 64 * 32)


def test_sharp_cube():
    if not engine_ready():
        return
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=12, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=600, detect_sharp=True, proxy='DECIMATE',
                                       fit_to_source=False)
    q = result_of(o)
    check("sharp cube: finished", r == {'FINISHED'} and q is not None)
    if q is None:
        return
    corners = [Vector((x, y, z)) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    near = sum(1 for c in corners if min((v.co - c).length for v in q.data.vertices) < 0.05)
    check("a vertex sits on every cube corner", near == 8, f"{near}/8")
    flat = max(min(abs(abs(c) - 1.0) for c in v.co) for v in q.data.vertices)
    check("every vertex stays on a cube face", flat < 0.02, f"{flat:.4f}")


def test_open_surface():
    if not engine_ready():
        return
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=2.0)
    o = bpy.context.object
    for v in o.data.vertices:
        v.co.z = 0.2 * math.sin(3 * v.co.x) * math.cos(2 * v.co.y)
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=500)
    q = result_of(o)
    check("open surface (auto -> decimate): finished", r == {'FINISHED'} and q is not None)
    if q is None:
        return
    n = len(q.data.polygons)
    check("open surface: all quads", all(len(p.vertices) == 4 for p in q.data.polygons))
    xs = [v.co.x for v in q.data.vertices]
    check("open surface keeps its border (reaches x = +-1)", min(xs) < -0.98 and max(xs) > 0.98)
    check("open surface: count near the target (+-30%)", 350 <= n <= 650, str(n))


def _ann_layer(name):
    sc = bpy.context.scene
    if sc.annotation is None:
        sc.annotation = bpy.data.annotations.new("Annotations")
    layer = sc.annotation.layers.new(name)
    return layer, layer.frames.new(sc.frame_current)


def _ring(n=64):
    t = math.radians(35)
    return [Vector((1.3 * math.cos(2 * math.pi * i / n), 1.3 * math.sin(2 * math.pi * i / n) * math.cos(t),
                    1.3 * math.sin(2 * math.pi * i / n) * math.sin(t) + 0.3)) for i in range(n)]


def test_guide_lines():
    if not engine_ready():
        return
    if bpy.app.version < (5, 2, 0):
        check("5.1: guide tests skipped (strokes can be written from Python only in 5.2)", True)
        return
    from mathutils.bvhtree import BVHTree
    o = egg()
    bm = bmesh.new()
    bm.from_mesh(o.data)
    tree = BVHTree.FromBMesh(bm)
    ring = [tree.find_nearest(p)[0] for p in _ring()]
    layer, frame = _ann_layer("Mine")
    st = frame.strokes.new()
    st.points.add(len(ring) + 1)
    for p, c in zip(st.points, ring + [ring[0]]):
        p.co = c
    hidden, hf = _ann_layer("Hidden")
    hidden.annotation_hide = True
    st2 = hf.strokes.new()
    st2.points.add(2)
    st2.points[0].co, st2.points[1].co = (0, -1, 0), (0, -1, 1)
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=1500, fit_to_source=False, guide_mode='HARD')
    q = result_of(o)
    check("guides (snap all): finished", r == {'FINISHED'} and q is not None)
    if q is None:
        return
    import json
    job = submodule("modules.quad_remesh.ops").RUN["last"]
    sent = json.load(open(os.path.join(job.dir, "job.json")))["guides"]
    check("guides: only the visible layer's stroke is sent, as a closed line",
          len(sent) == 1 and sent[0]["closed"], str([(len(g["points"]), g["closed"]) for g in sent]))
    qb = bmesh.new()
    qb.from_mesh(q.data)
    L = sum(e.calc_length() for e in qb.edges) / len(qb.edges)
    dense = [a.lerp(b, t / 10) for a, b in zip(ring, ring[1:] + ring[:1]) for t in range(10)]
    dense = [tree.find_nearest(p)[0] for p in dense]

    def near_ring(co):
        return min((co - p).length for p in dense) < 0.15 * L
    on = [e for e in qb.edges if near_ring(e.verts[0].co) and near_ring(e.verts[1].co)]
    probes = dense[::8]
    covered = sum(1 for p in probes if any(((e.verts[0].co + e.verts[1].co) / 2 - p).length < 0.7 * L for e in on))
    check("guides (snap all): quad edges lie on most of the ring (>= 60%; QuadWild varies run to run)",
          covered >= 0.6 * len(probes), f"{covered}/{len(probes)}")
    check("guides (snap all): still all quads", all(len(f.verts) == 4 for f in qb.faces))

    # steer (default): the field is turned along the ring (its visible effect varies run to run,
    # so only that it was applied and that the result stays sound is checked)
    bpy.data.objects.remove(q)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=1500, fit_to_source=False)
    q = result_of(o)
    job = submodule("modules.quad_remesh.ops").RUN["last"]
    log = open(job.log_path, errors="replace").read()
    steered = [int(l.split()[4]) for l in log.splitlines() if l.startswith("STS_INFO field steered on")]
    check("guides (steer, default): finished, field turned near the ring", r == {'FINISHED'} and q is not None
          and steered and steered[0] > 100, str(steered))
    check("guides (steer): all quads", q is not None and all(len(p.vertices) == 4 for p in q.data.polygons))
    n = len(q.data.polygons) if q else 0
    check("guides (steer): face count still near the target", 1125 <= n <= 1875, str(n))


def test_detect_creases():
    P = bpy.ops.object.sts_quad_detect_creases
    if bpy.app.version < (5, 2, 0):
        bpy.ops.mesh.primitive_cube_add()
        check("5.1: detect is unavailable (poll False)", not P.poll())
        return
    if not engine_ready():
        return
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=16, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    o.location = (2.0, 0.0, 0.0)
    r = P(blocking=True, target_faces=600, proxy='DECIMATE')
    ann = bpy.context.scene.annotation
    check("detect: finished and made the layers", r == {'FINISHED'} and ann is not None
          and ann.layers.get("STS Ridge") is not None and ann.layers.get("STS Valley") is not None)
    if ann is None or ann.layers.get("STS Ridge") is None:
        return
    ridge = ann.layers["STS Ridge"].frames[0].strokes
    valley = ann.layers["STS Valley"].frames[0].strokes
    check("detect: cube edges come out as ridges", len(ridge) >= 4, str(len(ridge)))
    check("detect: a convex cube has no valleys", len(valley) == 0, str(len(valley)))
    pts = [Vector(p.co) - Vector((2.0, 0.0, 0.0)) for st in ridge for p in st.points]
    off = max(sorted(abs(abs(c) - 1.0) for c in p)[1] for p in pts)
    check("detect: ridge points sit on cube edges (world space)", off < 0.08, f"{off:.3f}")
    n1 = len(ridge)
    old = ann.layers["STS Ridge"].frames.new(50)        # an old line on another frame
    st = old.strokes.new()
    st.points.add(2)
    P(blocking=True, target_faces=600, proxy='DECIMATE', replace=True)
    frames = ann.layers["STS Ridge"].frames
    total = sum(len(f.strokes) for f in frames)
    check("detect again with replace: no doubles, old lines on other frames gone too", total == n1, f"{total} vs {n1}")

    C = bpy.ops.object.sts_quad_clear_guides
    g, _f = _ann_layer("STS Guide")
    r = C(layer="STS Ridge")
    check("clear one layer by name", r == {'FINISHED'} and ann.layers.get("STS Ridge") is None
          and ann.layers.get("STS Valley") is not None and ann.layers.get("STS Guide") is not None)
    r = C(layer="")
    check("clear detected: both detected layers go, the hand-drawn layer stays",
          r == {'FINISHED'} and ann.layers.get("STS Valley") is None and ann.layers.get("STS Guide") is not None)
    r = C(layer="")
    check("clear with nothing left -> CANCELLED", r == {'CANCELLED'})


def _edge_ratio(q):
    """Mean edge length of the lower half over the upper half (quads, local z)."""
    top, bot = [], []
    for p in q.data.polygons:
        c = p.center
        vs = [q.data.vertices[i].co for i in p.vertices]
        e = sum((vs[i] - vs[(i + 1) % len(vs)]).length for i in range(len(vs))) / len(vs)
        if c.z > 0.2:
            top.append(e)
        elif c.z < -0.2:
            bot.append(e)
    return (sum(bot) / len(bot)) / (sum(top) / len(top))


def test_density_map():
    if not engine_ready():
        return
    o = egg()
    r = bpy.ops.object.sts_quad_remesh(blocking=True, density_source='MASK')
    check("density: no sculpt mask -> CANCELLED", r == {'CANCELLED'} and result_of(o) is None)
    att = o.data.attributes.new(".sculpt_mask", 'FLOAT', 'POINT')
    for i, v in enumerate(o.data.vertices):
        att.data[i].value = 1.0 if v.co.z > 0 else 0.0
    try:
        r = bpy.ops.object.sts_quad_remesh(blocking=True, density_source='MASK')
    except RuntimeError as exc:
        r = {'CANCELLED'} if "density" in str(exc) else {'ERROR'}
    check("density: QRemeshify's engine -> CANCELLED with an error", r == {'CANCELLED'} and result_of(o) is None)
    ok = os.path.isfile(os.path.join(STS_ENGINE, "lib_quadwild.dll"))
    check("STS engine present on this machine", ok, STS_ENGINE)
    if not ok:
        return
    os.environ["STS_QUADWILD_DIR"] = STS_ENGINE
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=1500, density_source='MASK', detail_ratio=2.5,
                                       fit_to_source=False)
    q = result_of(o)
    check("density (mask): finished, all quads", r == {'FINISHED'} and q is not None
          and all(len(p.vertices) == 4 for p in q.data.polygons))
    if q is None:
        use_engine(True)
        return
    ratio = _edge_ratio(q)
    check("density (mask): painted half has smaller quads (ratio >= 1.4)", ratio >= 1.4, f"{ratio:.2f}")
    n = len(q.data.polygons)
    check("density: total face count still near the target (+-30%)", 1050 <= n <= 1950, str(n))
    bpy.data.objects.remove(q)
    ca = o.data.color_attributes.new("Detail", 'FLOAT_COLOR', 'POINT')
    o.data.color_attributes.active_color = ca
    for i, v in enumerate(o.data.vertices):
        ca.data[i].color = (1, 1, 1, 1) if v.co.z > 0 else (0, 0, 0, 1)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    r = bpy.ops.object.sts_quad_remesh(blocking=True, target_faces=1500, density_source='COLOR', fit_to_source=False)
    q = result_of(o)
    ratio = _edge_ratio(q) if q else 0
    check("density (color attribute): bright half has smaller quads (ratio >= 1.4)",
          r == {'FINISHED'} and ratio >= 1.4, f"{ratio:.2f}")
    use_engine(True)


def _bumpy_source():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0)
    src = bpy.context.object
    src.name = "Src"
    for v in src.data.vertices:
        v.co *= 1.0 + 0.03 * math.sin(10 * v.co.x) * math.sin(10 * v.co.y)
    return src


def _quad_ball(name, half=False):
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = bpy.context.object
    o.name = name
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
    for v in bm.verts:
        v.co = v.co.normalized()
    if half:
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x < -1e-6], context='VERTS')
    bm.to_mesh(o.data)
    bm.free()
    return o


def _with_fit(o, src):
    m = o.modifiers.new("STS Fit", 'SHRINKWRAP')
    m.target = src
    m.wrap_method = 'NEAREST_SURFACEPOINT'
    return m


def test_project_detail():
    from mathutils.bvhtree import BVHTree
    P = bpy.ops.object.sts_quad_project_detail
    src = _bumpy_source()
    q = _quad_ball("Ball_Quad")
    bpy.context.view_layer.objects.active = q
    check("project detail: needs STS Fit (poll False without it)", not P.poll())
    _with_fit(q, src)
    other = q.modifiers.new("Bevel", 'BEVEL')
    r = P()
    check("project detail: another modifier -> CANCELLED", r == {'CANCELLED'} and q.modifiers.get("STS Fit") is not None)
    q.modifiers.remove(other)
    r = P(levels=2, rounds=6)
    mods = [(m.name, m.type) for m in q.modifiers]
    check("project detail: finished, only a Multires is left", r == {'FINISHED'} and len(mods) == 1
          and mods[0][1] == 'MULTIRES', str(mods))
    mr = q.modifiers[0]
    check("project detail: 2 levels, all shown", mr.total_levels == 2 and mr.levels == 2 and mr.sculpt_levels == 2)
    me = evaluated(q)
    bm = bmesh.new()
    bm.from_mesh(src.data)
    tree = BVHTree.FromBMesh(bm)
    dev = max((tree.find_nearest(v.co)[0] - v.co).length for v in me.vertices)
    check("project detail: the top level lies on the source", dev < 1e-3, f"{dev:.5f}")
    fb = bmesh.new()
    fb.from_mesh(me)
    fb.normal_update()
    folds = sum(1 for e in fb.edges if len(e.link_faces) == 2
                and e.link_faces[0].normal.dot(e.link_faces[1].normal) < -0.5)
    check("project detail: no folded faces", folds == 0, str(folds))
    check("project detail: helper object removed", bpy.data.objects.get("STS Detail Temp") is None)

    h = _quad_ball("Half_Quad", half=True)
    m = h.modifiers.new("STS Mirror", 'MIRROR')
    m.use_axis = (True, False, False)
    m.use_clip = True
    m.use_mirror_merge = True
    _with_fit(h, src)
    bpy.context.view_layer.objects.active = h
    r = P(levels=1, rounds=2)
    hb = bmesh.new()
    hb.from_mesh(h.data)
    check("project detail with STS Mirror: mirror applied (whole ball, no open seam)",
          r == {'FINISHED'} and h.modifiers.get("STS Mirror") is None and min(v.co.x for v in h.data.vertices) < -0.9
          and not any(e.is_boundary for e in hb.edges))


run([test_registered, test_no_engine, test_basic, test_symmetry, test_asymmetry_warning, test_edit_mode_selection,
     test_sharp_cube, test_open_surface, test_guide_lines, test_detect_creases, test_density_map, test_project_detail])
