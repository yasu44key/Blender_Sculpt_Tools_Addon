"""Find the QuadWild engine, hand a surface to the worker process and read its result.

The engine is the pair of QuadWild Bi-MDF DLLs that QRemeshify (GPL-3.0, free) installs.
This suite (MIT) does not ship them: it looks for an installed QRemeshify and runs them in
a separate background Blender (worker.py), so a crash or exit() inside QuadWild never takes
the user's session down.
"""

import json
import os
import subprocess
import sys
import tempfile

import bpy
import numpy as np

ENV_VAR = "STS_QUADWILD_DIR"   # override: a folder holding lib_quadwild / lib_quadpatches
_DLL = {"win32": "lib_quadwild.dll", "darwin": "liblib_quadwild.dylib"}.get(sys.platform, "liblib_quadwild.so")
WORKER = os.path.join(os.path.dirname(__file__), "worker.py")


def _is_engine(path):
    return bool(path) and os.path.isfile(os.path.join(path, _DLL)) \
        and os.path.isdir(os.path.join(path, "config"))


# Extension folders that hold an engine, best first: the STS build (density maps) before
# QRemeshify's own (same API, no density).
ENGINE_EXTENSIONS = (("sts_quadwild_engine", "lib"), ("qremeshify", "lib"))
FEATURES_FILE = "sts_engine.json"   # {"density": true} in the STS build


def find_engine():
    """Folder with the QuadWild DLLs and configs, or None."""
    env = os.environ.get(ENV_VAR)
    if _is_engine(env):
        return env
    roots = [r.directory for r in bpy.context.preferences.extensions.repos if r.enabled]
    for ext, sub in ENGINE_EXTENSIONS:
        for root in roots:
            lib = os.path.join(root, ext, sub)
            if _is_engine(lib):
                return lib
    return None


def supports_density(lib):
    try:
        with open(os.path.join(lib, FEATURES_FILE)) as f:
            return bool(json.load(f).get("density"))
    except (OSError, ValueError):
        return False


def density_values(me, source):
    """Per-vertex detail 0..1 from the mesh: 'MASK' = sculpt mask, 'COLOR' = brightness of the
    active color attribute. None when the mesh has no such data."""
    n = len(me.vertices)
    if source == 'MASK':
        att = me.attributes.get(".sculpt_mask")
        if att is None or att.domain != 'POINT':
            return None
        d = np.empty(n, np.float32)
        att.data.foreach_get("value", d)
        return np.clip(d, 0.0, 1.0)
    if source == 'COLOR':
        att = me.color_attributes.active_color
        if att is None:
            return None
        rgba = np.empty(len(att.data) * 4, np.float32)
        att.data.foreach_get("color", rgba)
        lum = rgba.reshape(-1, 4)[:, :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        if att.domain == 'POINT':
            return np.clip(lum, 0.0, 1.0)
        if att.domain == 'CORNER':
            vi = np.empty(len(me.loops), np.int32)
            me.loops.foreach_get("vertex_index", vi)
            acc = np.bincount(vi, weights=lum, minlength=n)
            cnt = np.maximum(np.bincount(vi, minlength=n), 1)
            return np.clip(acc / cnt, 0.0, 1.0).astype(np.float32)
    return None


def surface_arrays(obj, selected_only, density_source=None):
    """Triangles of the mesh in local coordinates: (verts float32 Nx3, tris int32 Mx3, density).

    Object Mode: the evaluated mesh (modifiers applied). Edit Mode: the base mesh, only the
    selected faces. density: float32 per vertex (0..1) or None (no source / no data).
    """
    if selected_only:
        obj.update_from_editmode()
        me = obj.data
        owner = None
    else:
        dg = bpy.context.evaluated_depsgraph_get()
        owner = obj.evaluated_get(dg)
        me = owner.to_mesh()
    try:
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        tris = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tris)
        tris = tris.reshape(-1, 3)
        verts = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", verts)
        verts = verts.reshape(-1, 3)
        density = density_values(me, density_source) if density_source else None
        if selected_only:
            poly = np.empty(nt, np.int32)
            me.loop_triangles.foreach_get("polygon_index", poly)
            sel = np.empty(len(me.polygons), bool)
            me.polygons.foreach_get("select", sel)
            tris = tris[sel[poly]]
            used, inverse = np.unique(tris, return_inverse=True)
            verts = verts[used]
            if density is not None:
                density = density[used]
            tris = inverse.reshape(-1, 3).astype(np.int32)
        return verts, tris, density
    finally:
        if owner is not None:
            owner.to_mesh_clear()


class Job:
    """One worker run. poll() reads new progress; the caller reads .state / .fraction / .message."""

    def __init__(self, verts, tris, settings, result_name="result.obj", density=None):
        self.dir = tempfile.mkdtemp(prefix="sts_quad_", dir=bpy.app.tempdir or None)
        np.save(os.path.join(self.dir, "verts.npy"), verts)
        np.save(os.path.join(self.dir, "tris.npy"), tris)
        if density is not None:
            np.save(os.path.join(self.dir, "density.npy"), density)
        with open(os.path.join(self.dir, "job.json"), "w") as f:
            json.dump(settings, f)
        self.result_name = result_name
        self.log_path = os.path.join(self.dir, "worker.log")
        self._log = open(self.log_path, "w")
        self._read = 0
        self.state = 'RUNNING'          # RUNNING / DONE / FAILED / CANCELLED
        self.fraction = 0.0
        self.message = "Starting"
        self.error = ""
        self.faces = 0
        self.got_result = False
        self.asymmetry = []             # (axis, distance, distance / quad edge) per lopsided axis
        env = dict(os.environ)
        env.pop("BLENDER_USER_SCRIPTS", None)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            [bpy.app.binary_path, "-b", "--factory-startup", "--python-exit-code", "1",
             "--python", WORKER, "--", self.dir],
            stdout=self._log, stderr=subprocess.STDOUT, env=env, creationflags=flags)

    @property
    def result_path(self):
        return os.path.join(self.dir, self.result_name)

    def _lines(self):
        self._log.flush()
        with open(self.log_path, encoding="utf-8", errors="replace") as f:
            f.seek(self._read)
            data = f.read()
            self._read = f.tell()
        return data.splitlines()

    def _parse(self, line):
        if line.startswith("STS_PROGRESS "):
            _, frac, msg = line.split(" ", 2)
            self.fraction, self.message = float(frac), msg
        elif line.startswith("STS_WARN "):
            _, axis, dist, rel = line.split()
            self.asymmetry.append((axis, float(dist), float(rel)))
        elif line.startswith("STS_RESULT "):
            self.faces = int(line.split()[1])
            self.got_result = True
        elif line.startswith("STS_ERROR "):
            self.error = line[len("STS_ERROR "):]

    def poll(self):
        if self.state != 'RUNNING':
            return self.state
        for line in self._lines():
            self._parse(line)
        if self.proc.poll() is None:
            return self.state
        for line in self._lines():   # whatever came after the last read
            self._parse(line)
        self._log.close()
        if self.faces is not None and self.got_result and os.path.isfile(self.result_path):
            self.state = 'DONE'
        else:
            self.state = 'FAILED'
            if not self.error:
                self.error = "The engine stopped without a result (see %s)" % self.log_path
        return self.state

    def wait(self):
        self.proc.wait()
        return self.poll()

    def cancel(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        if not self._log.closed:
            self._log.close()
        self.state = 'CANCELLED'


def read_result(path):
    """result.obj -> (verts list, faces list)."""
    verts, faces = [], []
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                verts.append(tuple(float(x) for x in line.split()[1:4]))
            elif line.startswith("f "):
                faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    return verts, faces
