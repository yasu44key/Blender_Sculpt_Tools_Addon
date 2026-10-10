"""Quad Remesh operators.

object.sts_quad_remesh          settings dialog -> worker process (modal, Esc cancels) -> new object
                                "<name>_Quad" with "STS Mirror" (symmetry) and "STS Fit" (shrinkwrap
                                onto the source, so the light proxy's lost detail comes back).
                                Strokes of the visible annotation layers are guide lines: the quads
                                lay a row of edges on each of them
object.sts_quad_detect_creases  worker finds ridge / valley lines -> annotation layers "STS Ridge" /
                                "STS Valley" (5.2+: Python can write strokes only from 5.2). Erase or
                                add strokes by hand, then remesh
object.sts_quad_draw_guides     annotate tool on the surface, layer "STS Guide" (the manual mode)
object.sts_quad_cancel          stop the running job (the panel's Cancel button)

A run takes tens of seconds, so it is modal instead of F9-redoable; the dialog remembers the
last values. Scripts and tests pass blocking=True to wait in place.
"""

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

from ...core import annotation
from . import engine

iface = bpy.app.translations.pgettext_iface

# The one running job (the engine is heavy: one at a time).
RUN = {"job": None, "cancel": False, "last": None}   # last: the finished job (for its warnings)

MIRROR = "STS Mirror"
FIT = "STS Fit"
RIDGE = "STS Ridge"
VALLEY = "STS Valley"
GUIDE = "STS Guide"
RIDGE_COLOR = (0.95, 0.25, 0.1)
VALLEY_COLOR = (0.1, 0.55, 1.0)
GUIDE_COLOR = (1.0, 0.85, 0.1)


def running():
    return RUN["job"] is not None


def target_label(context):
    return "Selected faces" if context.mode == 'EDIT_MESH' else "Whole object"


def guide_strokes(context, obj):
    """Strokes of the visible annotation layers in obj's local space: [{points, closed}]."""
    ann = context.scene.annotation
    inv = obj.matrix_world.inverted()
    out = []
    for layer in annotation.visible_layers(ann):
        for pts in annotation.stroke_positions(layer, context.scene.frame_current):
            local = [inv @ p for p in pts]
            length = sum((b - a).length for a, b in zip(local, local[1:]))
            closed = len(local) > 3 and (local[0] - local[-1]).length < 0.08 * length
            out.append({"points": [list(p) for p in local], "closed": closed})
    return out


class _EngineRun:
    """Shared by the operators that run the worker: start, poll from a timer, finish."""

    _timer = None
    _job = None
    job_title = "Quad Remesh"

    def start_job(self, context, verts, tris, settings, result_name="result.obj", density=None):
        self._src_name = context.active_object.name
        self._job = engine.Job(verts, tris, settings, result_name, density)
        RUN["job"], RUN["cancel"] = self._job, False
        if self.blocking or bpy.app.background:
            return self._finish(context, self._job.wait())
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.25, window=context.window)
        wm.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        job = self._job
        text = "%s: %s  %d%%   Esc: cancel" % (iface(self.job_title), iface(job.message), int(job.fraction * 100))
        context.workspace.status_text_set(text)
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'ESC' or RUN["cancel"]:
            self._job.cancel()
            return self._finish(context, 'CANCELLED')
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        state = self._job.poll()
        if state == 'RUNNING':
            self._status(context)
            return {'PASS_THROUGH'}
        return self._finish(context, state)

    def _finish(self, context, state):
        job = self._job
        RUN["job"], RUN["last"] = None, job
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if context.workspace is not None:
            context.workspace.status_text_set(None)
        if state == 'CANCELLED':
            self.report({'INFO'}, iface(self.job_title) + ": " + iface("cancelled"))
            return {'CANCELLED'}
        if state != 'DONE':
            self.report({'ERROR'}, iface(self.job_title) + ": " + iface("failed") + ": " + job.error)
            return {'CANCELLED'}
        src = bpy.data.objects.get(self._src_name)
        if src is None:
            self.report({'ERROR'}, "The source object is gone")
            return {'CANCELLED'}
        return self.done(context, src, job)

    def cancel(self, context):
        if self._job is not None and self._job.state == 'RUNNING':
            self._job.cancel()
        RUN["job"] = None
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


def _engine_or_report(op):
    lib = engine.find_engine()
    if lib is None:
        op.report({'ERROR'}, "QRemeshify is not installed (it provides the QuadWild engine)")
    return lib


def _proxy_settings(lib, target_faces, proxy):
    return {
        "engine": lib,
        "target_faces": target_faces,
        "proxy": proxy,
        "voxel_div": 4.0,          # voxel = quad edge / 4
        "proxy_per_face": 4.0,     # proxy triangles per wanted quad
        "proxy_min": 8000,
        "proxy_max": 120000,       # QuadWild slows down sharply above ~100k
        "symmetry": [False, False, False],
    }


PROXY_ITEMS = [('AUTO', "Auto", "Voxel remesh for closed surfaces, decimate for open ones"),
               ('VOXEL', "Voxel", "Voxel remesh then decimate (fast on huge scans; closes holes)"),
               ('DECIMATE', "Decimate", "Decimate only (keeps holes and open borders; slow on huge meshes)")]


class OBJECT_OT_sts_quad_remesh(_EngineRun, bpy.types.Operator):
    """Rebuild the mesh as clean quads with QuadWild (runs in the background, Esc cancels)"""
    bl_idname = "object.sts_quad_remesh"
    bl_label = "Quad Remesh"
    bl_options = {'REGISTER', 'UNDO'}

    target_faces: IntProperty(
        name="Target Faces", description="About how many quads the result should have (after mirroring)",
        default=8000, min=100, max=500000, soft_max=100000)
    symmetry_x: BoolProperty(name="X", description="Mirror the topology across local X", default=False)
    symmetry_y: BoolProperty(name="Y", description="Mirror the topology across local Y", default=False)
    symmetry_z: BoolProperty(name="Z", description="Mirror the topology across local Z", default=False)
    use_guides: BoolProperty(
        name="Follow Guide Lines",
        description="Lay a row of quad edges on every stroke of the visible annotation layers", default=True)
    guide_mode: EnumProperty(
        name="Guide Mode", description="How the quads follow the guide lines",
        items=[('SOFT', "Steer", "Turn the edge flow along the lines (robust, keeps the face count)"),
               ('HYBRID', "Steer + Snap Long", "Closed and long lines also get a row of edges exactly on them"),
               ('HARD', "Snap All", "Every line gets a row of edges exactly on it (open lines can fold at their ends)")],
        default='SOFT')
    density_source: EnumProperty(
        name="Density Map", description="Where to read the painted detail from",
        items=[('NONE', "None", "Even quad size"),
               ('MASK', "Sculpt Mask", "Masked areas get smaller quads"),
               ('COLOR', "Color Attribute", "Bright areas of the active color attribute get smaller quads")],
        default='NONE')
    detail_ratio: FloatProperty(
        name="Detail Ratio", description="How many times smaller the quads are where the map is fully painted",
        default=2.5, min=1.0, max=8.0)
    density_edges: BoolProperty(
        name="Split at Density Edges",
        description="Put a patch border on the edge of the painted area (quad size can only change across patch borders)",
        default=True)
    detect_sharp: BoolProperty(
        name="Keep Sharp Edges",
        description="Edges sharper than the angle become feature lines the quads follow "
                    "(for hard surfaces; short creases are ignored)",
        default=False)
    sharp_angle: FloatProperty(
        name="Sharp Edge Angle", subtype='ANGLE', default=math.radians(35.0),
        min=math.radians(1.0), max=math.radians(179.0))
    smoothing: BoolProperty(name="Relax Result", description="Smooth the quads after building them", default=True)
    proxy: EnumProperty(name="Proxy Surface", description="How the light stand-in surface the engine works on is made",
                        items=PROXY_ITEMS, default='AUTO')
    fit_to_source: BoolProperty(
        name="Fit to Source", description="Add a Shrinkwrap modifier that snaps the quads onto the original surface",
        default=True)
    hide_source: BoolProperty(name="Hide Source", default=False)
    blocking: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}, default=False)

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o is not None and o.type == 'MESH' and context.mode in {'OBJECT', 'EDIT_MESH', 'SCULPT'} \
            and not running()

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.label(text=iface("Target: ") + iface(target_label(context)))
        layout.prop(self, "target_faces")
        row = layout.row(heading="Symmetry", align=True)
        row.prop(self, "symmetry_x", toggle=True)
        row.prop(self, "symmetry_y", toggle=True)
        row.prop(self, "symmetry_z", toggle=True)
        n = len(guide_strokes(context, context.active_object))
        layout.prop(self, "use_guides", text=iface("Follow Guide Lines") + " (%d)" % n)
        sub = layout.row()
        sub.active = self.use_guides and n > 0
        sub.prop(self, "guide_mode")
        layout.prop(self, "density_source")
        sub = layout.row()
        sub.active = self.density_source != 'NONE'
        sub.prop(self, "detail_ratio")
        sub = layout.row()
        sub.active = self.density_source != 'NONE'
        sub.prop(self, "density_edges")
        layout.prop(self, "detect_sharp")
        sub = layout.row()
        sub.active = self.detect_sharp
        sub.prop(self, "sharp_angle")
        layout.prop(self, "smoothing")
        layout.prop(self, "fit_to_source")
        layout.prop(self, "hide_source")
        layout.prop(self, "proxy")

    def invoke(self, context, _event):
        if _engine_or_report(self) is None:
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=360)

    def execute(self, context):
        lib = _engine_or_report(self)
        if lib is None:
            return {'CANCELLED'}
        src = context.active_object
        selected_only = context.mode == 'EDIT_MESH'
        verts, tris, density = engine.surface_arrays(
            src, selected_only, None if self.density_source == 'NONE' else self.density_source)
        if len(tris) < 20:
            self.report({'WARNING'}, "Not enough faces to remesh" if not selected_only else "Select faces to remesh")
            return {'CANCELLED'}
        if self.density_source != 'NONE' and density is None:
            self.report({'WARNING'}, "No sculpt mask on this mesh" if self.density_source == 'MASK'
                        else "No color attribute on this mesh")
            return {'CANCELLED'}
        if density is not None and not engine.supports_density(lib):
            self.report({'ERROR'}, "This engine cannot use a density map (needs the STS QuadWild engine)")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        settings = _proxy_settings(lib, self.target_faces, self.proxy)
        settings.update({
            "symmetry": [self.symmetry_x, self.symmetry_y, self.symmetry_z],
            "sharp": self.detect_sharp,
            "sharp_angle": self.sharp_angle,
            "sharp_min_quads": 4.0,    # drop sharp chains shorter than 4 quad edges (scan noise)
            "guides": guide_strokes(context, src) if self.use_guides else [],
            "guide_mode": self.guide_mode.lower(),
            "hard_min_quads": 10.0,    # HYBRID: open lines this long (in quad edges) are snapped too
            "alpha": 0.005,
            "time_limit": 200,
            "smooth": self.smoothing,
            "passes": 3,               # extra quadrangulation passes to land near the target
            "tolerance": 0.10,
        })
        settings["detail_ratio"] = self.detail_ratio
        settings["density_edges"] = self.density_edges and density is not None
        if density is not None:
            settings["alpha"] = 0.2    # size fidelity over regularity, or QuadWild evens the sizes out
        return self.start_job(context, verts, tris, settings, density=density)

    def done(self, context, src, job):
        obj = self._build(context, src, job)
        for axis, dist, rel in job.asymmetry:
            self.report({'WARNING'}, iface("Not symmetric on %s: the mirrored side is up to %.3g off (%d%% of a quad). "
                                           "Turn that axis off or align the model first") % (axis, dist, rel * 100))
        if not job.asymmetry:
            self.report({'INFO'}, "Quad Remesh: %d faces" % len(obj.data.polygons))
        return {'FINISHED'}

    def _build(self, context, src, job):
        verts, faces = engine.read_result(job.result_path)
        me = bpy.data.meshes.new(src.data.name + "_Quad")
        me.from_pydata(verts, [], faces)
        me.update()
        obj = bpy.data.objects.new(src.name + "_Quad", me)
        coll = src.users_collection[0] if src.users_collection else context.scene.collection
        coll.objects.link(obj)
        obj.matrix_world = src.matrix_world.copy()
        axes = (self.symmetry_x, self.symmetry_y, self.symmetry_z)
        if any(axes):
            m = obj.modifiers.new(MIRROR, 'MIRROR')
            m.use_axis = axes
            m.use_clip = True
            m.use_mirror_merge = True
            m.merge_threshold = max(src.dimensions) * 1e-4 / max(max(src.scale), 1e-9)
        if self.fit_to_source:
            m = obj.modifiers.new(FIT, 'SHRINKWRAP')
            m.target = src
            m.wrap_method = 'NEAREST_SURFACEPOINT'
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        if self.hide_source:
            src.hide_set(True)
        return obj


class OBJECT_OT_sts_quad_detect_creases(_EngineRun, bpy.types.Operator):
    """Find ridge and valley lines and draw them as annotation strokes (edit them, then remesh)"""
    bl_idname = "object.sts_quad_detect_creases"
    bl_label = "Detect Crease Lines"
    bl_options = {'REGISTER', 'UNDO'}
    job_title = "Detect Crease Lines"

    target_faces: IntProperty(
        name="Target Faces", description="Use the face count you will remesh with: it sets how fine a crease counts",
        default=8000, min=100, max=500000, soft_max=100000)
    crease_angle: FloatProperty(
        name="Crease Angle", description="How sharp a fold must be on the light proxy to count",
        subtype='ANGLE', default=math.radians(35.0), min=math.radians(5.0), max=math.radians(170.0))
    min_quads: FloatProperty(
        name="Minimum Length", description="Drop lines shorter than this many quad edges",
        default=4.0, min=1.0, max=50.0)
    replace: BoolProperty(name="Replace Previous Lines", description="Clear the STS Ridge / STS Valley layers first",
                          default=True)
    proxy: EnumProperty(name="Proxy Surface", items=PROXY_ITEMS, default='AUTO')
    blocking: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}, default=False)

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return annotation.CAN_WRITE and o is not None and o.type == 'MESH' \
            and context.mode in {'OBJECT', 'SCULPT'} and not running()

    def invoke(self, context, _event):
        if _engine_or_report(self) is None:
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=340)

    def execute(self, context):
        lib = _engine_or_report(self)
        if lib is None:
            return {'CANCELLED'}
        verts, tris, _d = engine.surface_arrays(context.active_object, False)
        if len(tris) < 20:
            self.report({'WARNING'}, "Not enough faces to remesh")
            return {'CANCELLED'}
        settings = _proxy_settings(lib, self.target_faces, self.proxy)
        settings.update({"mode": "detect", "crease_angle": self.crease_angle, "crease_min_quads": self.min_quads})
        return self.start_job(context, verts, tris, settings, result_name="creases.json")

    def done(self, context, src, job):
        import json
        with open(job.result_path) as f:
            lines = json.load(f)
        mw = src.matrix_world
        counts = {RIDGE: 0, VALLEY: 0}
        for name, color in ((RIDGE, RIDGE_COLOR), (VALLEY, VALLEY_COLOR)):
            layer, frame = annotation.ensure_layer(context.scene, name, color)
            layer.annotation_hide = False
            if self.replace:          # every frame of the layer, not only the one shown now
                for fr in layer.frames:
                    for st in list(fr.strokes):
                        fr.strokes.remove(st)
        for line in lines:
            name = RIDGE if line["convex"] else VALLEY
            _layer, frame = annotation.ensure_layer(context.scene, name)
            annotation.add_stroke(frame, [mw @ _v(p) for p in line["points"]])
            counts[name] += 1
        self.report({'INFO'}, iface("Crease lines: %d ridges, %d valleys") % (counts[RIDGE], counts[VALLEY]))
        return {'FINISHED'}


def _v(p):
    from mathutils import Vector
    return Vector(p)


class OBJECT_OT_sts_quad_draw_guides(bpy.types.Operator):
    """Draw guide lines on the surface with the annotate tool (layer "STS Guide")"""
    bl_idname = "object.sts_quad_draw_guides"
    bl_label = "Draw Guide Lines"

    erase: BoolProperty(name="Erase", description="Switch to the annotation eraser instead", default=False,
                        options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode in {'OBJECT', 'SCULPT'}

    def execute(self, context):
        context.scene.tool_settings.annotation_stroke_placement_view3d = 'SURFACE'
        if not self.erase:
            layer, _frame = annotation.ensure_layer(context.scene, GUIDE, GUIDE_COLOR)
            layer.annotation_hide = False
            ann = context.scene.annotation
            ann.layers.active_index = list(ann.layers).index(layer)
        bpy.ops.wm.tool_set_by_id(name="builtin.annotate_eraser" if self.erase else "builtin.annotate")
        return {'FINISHED'}


class OBJECT_OT_sts_quad_clear_guides(bpy.types.Operator):
    """Delete guide line layers (the detected lines cannot be edited point by point: delete and detect again)"""
    bl_idname = "object.sts_quad_clear_guides"
    bl_label = "Clear Guide Lines"
    bl_options = {'REGISTER', 'UNDO'}

    layer: bpy.props.StringProperty(
        name="Layer", description="Annotation layer to delete; empty = both detected layers (STS Ridge, STS Valley)",
        default="", options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.scene.annotation is not None

    def execute(self, context):
        ann = context.scene.annotation
        names = [self.layer] if self.layer else [RIDGE, VALLEY]
        gone = [ann.layers.get(n) for n in names if ann.layers.get(n) is not None]
        if not gone:
            self.report({'WARNING'}, "No such guide layer")
            return {'CANCELLED'}
        for layer in gone:
            ann.layers.remove(layer)
        for area in context.screen.areas if context.screen else ():
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class OBJECT_OT_sts_quad_cancel(bpy.types.Operator):
    """Stop the running Quad Remesh"""
    bl_idname = "object.sts_quad_cancel"
    bl_label = "Cancel Quad Remesh"

    @classmethod
    def poll(cls, _context):
        return running()

    def execute(self, _context):
        RUN["cancel"] = True
        return {'FINISHED'}


classes = (OBJECT_OT_sts_quad_remesh, OBJECT_OT_sts_quad_detect_creases, OBJECT_OT_sts_quad_draw_guides,
           OBJECT_OT_sts_quad_clear_guides, OBJECT_OT_sts_quad_cancel)
