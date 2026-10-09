"""The Draw NURBS Grid modal operator, its scene settings and the helpers.

Replaces: Draw_NURBS_Grid_Patch63.py, nurbs_hud_w.py

Started from the sidebar, so context.region is the sidebar: every mouse
position goes through core/view3d.py (window_region_under_mouse -> mouse_ray /
mouse_on_plane / surface_point). A click over the sidebar or a header places
nothing (PASS_THROUGH). The drawing callback is draw_hud — an Operator method
named draw would collide with Blender's reserved name.
"""

import blf
import gpu
from gpu_extras.batch import batch_for_shader

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Vector

from ...core import view3d
from . import logic

HELP_LINES = (
    "Click: add point",
    "Drag: add points continuously",
    "Up / Down: points per row (first row only)",
    "Ctrl + wheel: weight of the next points",
    "Backspace, Ctrl+Z: remove last point",
    "Enter: build the surface",
    "Esc, Right-click: cancel",
    "Middle mouse, wheel: navigate",
)

_WHEEL_UP = {'WHEELUPMOUSE', 'WHEELINMOUSE'}
_WHEEL_DOWN = {'WHEELDOWNMOUSE', 'WHEELOUTMOUSE'}

# Viewport navigation while drawing (mouse moves are handled in modal()).
_NAV_TYPES = {
    'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM', 'NDOF_MOTION',
}


class NurbsGridSettings(bpy.types.PropertyGroup):
    """Settings for the next Draw NURBS Grid session."""

    u_count: bpy.props.IntProperty(
        name="U Count", default=4, min=2, max=100,
        description="Points per row (Up / Down change it while drawing, until the first row is full)",
    )
    use_drag: bpy.props.BoolProperty(
        name="Use Drag", default=True,
        description="Hold the left button down to place points continuously",
    )
    drag_interval: bpy.props.FloatProperty(
        name="Drag Interval", default=0.5, min=0.001, max=100.0, unit='LENGTH',
        description="Minimum distance between the points placed while dragging",
    )
    snap: bpy.props.EnumProperty(
        name="Snap", default='NONE',
        items=(
            ('NONE', "None", "Place on a surface, or on the first point's depth when nothing is hit"),
            ('VERTEX', "Vertex", "Snap to the nearest vertex within 40 px on screen"),
            ('FACE', "Face", "Snap to the surface under the mouse"),
            ('GRID', "Grid", "Round to the 3D view's grid spacing"),
        ),
        description="Snap mode while drawing (Ctrl=Vertex, Alt=Face, Shift=Grid override it)",
    )
    snap_nurbs_only: bpy.props.BoolProperty(
        name="Snap NURBS Only", default=False,
        description="Vertex snap uses only NURBS control points, not mesh vertices",
    )
    weight: bpy.props.FloatProperty(
        name="Weight", default=1.0, min=0.1, max=10.0,
        description="Weight of the points placed next (Ctrl+wheel adjusts it while drawing)",
    )


class SURFACE_OT_sts_nurbs_grid_draw(bpy.types.Operator):
    """Click in the 3D view to place grid points row by row, then build a NURBS surface"""
    bl_idname = "surface.sts_nurbs_grid_draw"
    bl_label = "Draw NURBS Grid"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.mode == 'OBJECT')

    def invoke(self, context, _event):
        s = context.scene.sts_nurbs_grid
        self._points = []          # (Vector co, float weight), row after row
        self._u = s.u_count
        self._weight = s.weight
        self._dragging = False
        self._last_co = None
        self._ref_depth = None     # first placed point (its depth), else the 3D cursor
        self._current_loc = context.scene.cursor.location.copy()
        self._snap_state = 'NONE'
        self._region = None        # last WINDOW region under the mouse
        self._ended = False
        self._shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        self._handler = None

        context.window_manager.modal_handler_add(self)
        self._handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_hud, (context,), 'WINDOW', 'POST_PIXEL')
        context.window.cursor_modal_set('CROSSHAIR')
        return {'RUNNING_MODAL'}

    # ---------------------------------------------------------------- picking

    def _region_under_mouse(self, context, event):
        return view3d.window_region_under_mouse(context.area, event.mouse_x, event.mouse_y)

    def _grid_step(self, context):
        space = context.area.spaces.active if context.area else None
        if space is not None and hasattr(space, "overlay"):
            return space.overlay.grid_scale
        return 1.0

    def _nearest_vertex(self, context, event, region, hit_info):
        """World position of the nearest snap candidate within 40 px on screen.

        NURBS control points are few, so all of them are checked. Meshes can be
        dense sculpts: only the vertices of the face under the mouse are used
        (checking every vertex on every mouse move would freeze the view).
        """
        nurbs_only = context.scene.sts_nurbs_grid.snap_nurbs_only
        mouse = Vector((event.mouse_x - region.x, event.mouse_y - region.y))
        best, best_dist = None, 40.0
        if not nurbs_only and hit_info is not None:
            hit_obj, face_index, matrix, depsgraph = hit_info
            if hit_obj is not None and hit_obj.type == 'MESH':
                ev = hit_obj.evaluated_get(depsgraph)
                me = ev.data
                if 0 <= face_index < len(me.polygons):
                    for vi in me.polygons[face_index].vertices:
                        co = matrix @ me.vertices[vi].co
                        co2d = location_3d_to_region_2d(region, region.data, co)
                        if co2d is not None and (co2d - mouse).length < best_dist:
                            best_dist, best = (co2d - mouse).length, co
        for obj in context.view_layer.objects:
            if not obj.visible_get():
                continue
            mw = obj.matrix_world
            if obj.type == 'SURFACE':
                for spline in obj.data.splines:
                    if spline.type != 'NURBS':
                        continue
                    for pt in spline.points:
                        co = mw @ pt.co.xyz
                        co2d = location_3d_to_region_2d(region, region.data, co)
                        if co2d is None:
                            continue
                        d = (co2d - mouse).length
                        if d < best_dist:
                            best_dist, best = d, co
        return best

    def _pick(self, context, event, region):
        """World position under the mouse for the current snap mode."""
        s = context.scene.sts_nurbs_grid
        mode = s.snap
        if event.ctrl:
            mode = 'VERTEX'
        elif event.alt:
            mode = 'FACE'
        elif event.shift:
            mode = 'GRID'

        origin, direction = view3d.mouse_ray(region, event.mouse_x, event.mouse_y)
        depth = self._ref_depth if self._ref_depth is not None else context.scene.cursor.location
        fallback = view3d.mouse_on_plane(region, event.mouse_x, event.mouse_y, depth)
        co, hit = view3d.surface_point(context.scene, context.evaluated_depsgraph_get(),
                                       origin, direction, fallback)

        if mode == 'VERTEX':
            depsgraph = context.evaluated_depsgraph_get()
            hit_info = None
            res = context.scene.ray_cast(depsgraph, origin, direction)
            if res[0]:
                hit_info = (res[4], res[3], res[5], depsgraph)
            snapped = self._nearest_vertex(context, event, region, hit_info)
            if snapped is not None:
                self._snap_state = 'VERTEX'
                self._current_loc = snapped
                return snapped
            self._snap_state = 'NONE'
        elif mode == 'FACE':
            self._snap_state = 'FACE' if hit else 'NONE'
        elif mode == 'GRID':
            step = self._grid_step(context)
            if step > 0.0:
                co = Vector((round(co.x / step) * step,
                             round(co.y / step) * step,
                             round(co.z / step) * step))
            self._snap_state = 'GRID'
        else:
            self._snap_state = 'NONE'

        self._current_loc = co
        return co

    def _add_point(self, co):
        if self._ref_depth is None:
            self._ref_depth = co.copy()
        self._points.append((co.copy(), self._weight))
        self._last_co = co

    # ---------------------------------------------------------------- modal

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        # While the left button is held: every move far enough places the next
        # point. Checked before the navigation pass below.
        if self._dragging and event.type in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            region = self._region_under_mouse(context, event)
            if region is not None:
                self._region = region
                co = self._pick(context, event, region)
                interval = context.scene.sts_nurbs_grid.drag_interval
                if view3d.drag_far_enough(self._last_co, co, interval):
                    self._add_point(co)
            return {'RUNNING_MODAL'}

        if event.type in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            region = self._region_under_mouse(context, event)
            if region is not None:
                self._region = region
                self._pick(context, event, region)
            else:
                self._snap_state = 'NONE'
            return {'PASS_THROUGH'}

        if event.type in _WHEEL_UP | _WHEEL_DOWN:
            if event.ctrl:
                if event.type in _WHEEL_UP:
                    self._weight = round(self._weight + 0.1, 1)
                else:
                    self._weight = max(0.1, round(self._weight - 0.1, 1))
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}  # plain wheel keeps zooming the view

        if event.type in _NAV_TYPES or event.type.startswith('NDOF_'):
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if not self._dragging:
                return {'PASS_THROUGH'}  # release of a click the sidebar handled
            self._dragging = False
            return {'RUNNING_MODAL'}

        if event.value != 'PRESS':
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE':
            region = self._region_under_mouse(context, event)
            if region is None:
                return {'PASS_THROUGH'}  # click on the sidebar / header: not ours
            self._region = region
            self._add_point(self._pick(context, event, region))
            self._dragging = context.scene.sts_nurbs_grid.use_drag
            return {'RUNNING_MODAL'}

        if event.type in ('UP_ARROW', 'DOWN_ARROW'):
            # Only until the first row is full; after that the rows are fixed.
            if len(self._points) < self._u:
                if event.type == 'UP_ARROW':
                    self._u = min(100, self._u + 1)
                else:
                    self._u = max(2, self._u - 1)
            return {'RUNNING_MODAL'}

        if event.type == 'BACK_SPACE' or (event.type == 'Z' and event.ctrl):
            if self._points:
                self._points.pop()
                if not self._points:
                    self._ref_depth = None
            return {'RUNNING_MODAL'}

        if event.type in ('RET', 'NUMPAD_ENTER', 'SPACE'):
            if len(self._points) < self._u * 2:
                self.report({'WARNING'}, f"Need at least 2 full rows ({self._u * 2} points)")
                return {'RUNNING_MODAL'}
            self._cleanup(context)
            obj = logic.build_grid(context, self._points, self._u,
                                   view_vector=self._view_vector(context))
            return {'FINISHED'} if obj is not None else {'CANCELLED'}

        if event.type in ('ESC', 'RIGHTMOUSE'):
            self._cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _view_vector(self, context):
        """The direction the view looks in (region first, then the 3D space)."""
        if self._region is not None and self._region.data is not None:
            return self._region.data.view_rotation @ Vector((0, 0, -1))
        space = context.area.spaces.active if context.area else None
        if space is not None and getattr(space, "region_3d", None) is not None:
            return space.region_3d.view_rotation @ Vector((0, 0, -1))
        return None

    def _cleanup(self, context):
        self._ended = True
        if self._handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handler, 'WINDOW')
            self._handler = None
        try:
            context.window.cursor_modal_restore()
        except Exception:
            pass
        if context.area:
            context.area.tag_redraw()

    def cancel(self, context):
        """Cancelled from outside the modal: discard, like Esc."""
        if not self._ended:
            self._cleanup(context)

    # ---------------------------------------------------------------- HUD

    def _window_region(self, context):
        area = context.area
        if area is None:
            return None
        for r in area.regions:
            if r.type == 'WINDOW' and r.data is not None:
                return r
        return None

    def draw_hud(self, context):
        region = self._window_region(context)
        if region is not None:
            self._draw_marks(context, region)
        self._draw_text(context)

    def _draw_marks(self, context, region):
        pts2d = [location_3d_to_region_2d(region, region.data, co) for co, _w in self._points]
        cur2d = location_3d_to_region_2d(region, region.data, self._current_loc)

        lines = []
        u = self._u
        for i, p in enumerate(pts2d):
            if p is None:
                continue
            if (i % u) < u - 1 and i + 1 < len(pts2d) and pts2d[i + 1] is not None:
                lines.extend((p, pts2d[i + 1]))
            if i >= u and pts2d[i - u] is not None:
                lines.extend((p, pts2d[i - u]))
        if pts2d and cur2d is not None and (len(pts2d) % u) != 0 and pts2d[-1] is not None:
            lines.extend((pts2d[-1], cur2d))

        try:
            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(2)
            gpu.state.point_size_set(6)
        except Exception:
            pass

        self._shader.bind()
        valid = [p for p in pts2d if p is not None]
        if valid:
            batch = batch_for_shader(self._shader, 'POINTS', {"pos": valid})
            self._shader.uniform_float("color", (1.0, 0.5, 0.0, 1.0))
            batch.draw(self._shader)
        if lines:
            batch = batch_for_shader(self._shader, 'LINES', {"pos": lines})
            self._shader.uniform_float("color", (0.0, 1.0, 1.0, 0.8))
            batch.draw(self._shader)
        if cur2d is not None:
            colors = {'VERTEX': (0.2, 1.0, 0.2, 1.0), 'FACE': (0.2, 0.5, 1.0, 1.0),
                      'GRID': (1.0, 1.0, 0.0, 1.0)}
            try:
                gpu.state.point_size_set(8 + int(self._weight * 5))
            except Exception:
                pass
            batch = batch_for_shader(self._shader, 'POINTS', {"pos": [cur2d]})
            self._shader.uniform_float("color", colors.get(self._snap_state, (1.0, 0.2, 0.2, 1.0)))
            batch.draw(self._shader)
        try:
            gpu.state.blend_set('NONE')
            gpu.state.line_width_set(1)
            gpu.state.point_size_set(1)
        except Exception:
            pass

    def _draw_text(self, context):
        font_id = 0
        total = len(self._points)
        in_row = (total % self._u) + 1

        blf.position(font_id, 20, 150, 0)
        blf.size(font_id, 20)
        blf.color(font_id, 1, 1, 1, 1)
        blf.draw(font_id, f"Points per row (U): {self._u}")

        blf.position(font_id, 20, 122, 0)
        blf.size(font_id, 24)
        if in_row == 1:
            blf.color(font_id, 0.5, 1.0, 0.5, 1)
            blf.draw(font_id, f"New Row: {in_row} / {self._u}")
        else:
            blf.color(font_id, 1.0, 0.8, 0.2, 1)
            blf.draw(font_id, f"Next Point: {in_row} / {self._u}")

        blf.position(font_id, 20, 96, 0)
        blf.size(font_id, 20)
        blf.color(font_id, 0.2, 1.0, 1.0, 1)
        blf.draw(font_id, f"Weight: {self._weight:.2f}")

        snap = self._snap_state
        base = context.scene.sts_nurbs_grid.snap
        blf.position(font_id, 20, 72, 0)
        blf.color(font_id, 1, 1, 1, 1)
        blf.draw(font_id, f"Snap: {snap if snap != 'NONE' else base}")

        blf.position(font_id, 20, 48, 0)
        blf.size(font_id, 14)
        blf.color(font_id, 0.8, 0.8, 0.8, 0.8)
        blf.draw(font_id, "Up/Down: U (first row only) | Ctrl+wheel: weight | "
                          "Ctrl Vtx, Alt Face, Shift Grid")
        blf.position(font_id, 20, 30, 0)
        blf.draw(font_id, "Backspace / Ctrl+Z: remove last | Enter: build | Esc, right-click: cancel")


class OBJECT_OT_sts_nurbs_flip(bpy.types.Operator):
    """Flip the normals of the selected NURBS surfaces (reverse their V rows)"""
    bl_idname = "object.sts_nurbs_flip"
    bl_label = "Flip Surface Normal"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        targets = [o for o in context.selected_objects if o.type == 'SURFACE']
        if not targets:
            self.report({'WARNING'}, "Select NURBS surfaces to flip")
            return {'CANCELLED'}
        count = sum(1 for o in targets if logic.flip(o))
        self.report({'INFO'}, f"Flipped {count} surface(s)")
        return {'FINISHED'}


class SURFACE_OT_sts_nurbs_cyclic(bpy.types.Operator):
    """Toggle the U or V loop of every NURBS spline of the active surface"""
    bl_idname = "surface.sts_nurbs_cyclic"
    bl_label = "Toggle Loop"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Axis", default='U',
        items=(('U', "U", "Loop in the U direction"), ('V', "V", "Loop in the V direction")),
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'SURFACE'

    def execute(self, context):
        obj = context.active_object
        if not obj.data.splines:
            self.report({'WARNING'}, "The active surface has no splines")
            return {'CANCELLED'}
        attr = "use_cyclic_u" if self.axis == 'U' else "use_cyclic_v"
        on = not getattr(obj.data.splines[0], attr)   # one new state for every spline
        for spline in obj.data.splines:
            setattr(spline, attr, on)
        return {'FINISHED'}


class OBJECT_OT_sts_nurbs_join(bpy.types.Operator):
    """Join the selected NURBS surfaces into one object, then edit it"""
    bl_idname = "object.sts_nurbs_join"
    bl_label = "Join Surfaces"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        surfaces = [o for o in context.selected_objects if o.type == 'SURFACE']
        if len(surfaces) < 2:
            self.report({'WARNING'}, "Select 2 or more NURBS surfaces to join")
            return {'CANCELLED'}
        for o in context.selected_objects:     # never pull meshes etc. into the join
            o.select_set(o in surfaces)
        context.view_layer.objects.active = surfaces[0]
        bpy.ops.object.join()
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


classes = (
    NurbsGridSettings,
    SURFACE_OT_sts_nurbs_grid_draw,
    OBJECT_OT_sts_nurbs_flip,
    SURFACE_OT_sts_nurbs_cyclic,
    OBJECT_OT_sts_nurbs_join,
)
