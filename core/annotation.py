"""Reading and writing the scene's annotation (5.x: scene.annotation, bpy.data.annotations).

Python can add strokes only from Blender 5.2 (frame.strokes.new); reading works in 5.1 too.
"""

import bpy

CAN_WRITE = bpy.app.version >= (5, 2, 0)


def frame_for(layer, current_frame):
    """The frame shown at the current frame: the newest frame at or below it,
    else the first one (layer.active_frame can be None right after opening)."""
    if not layer.frames:
        return None
    best = None
    for frame in layer.frames:
        if frame.frame_number <= current_frame and (best is None or frame.frame_number > best.frame_number):
            best = frame
    return best if best is not None else layer.frames[0]


def stroke_positions(layer, current_frame):
    """World-space point lists of the layer's strokes, chains with < 2 points skipped."""
    frame = frame_for(layer, current_frame)
    if frame is None:
        return []
    strokes = []
    for stroke in frame.strokes:
        points = [p.co.copy() for p in stroke.points]
        if len(points) >= 2:
            strokes.append(points)
    return strokes


def visible_layers(ann):
    return [layer for layer in ann.layers if not layer.annotation_hide] if ann is not None else []


def ensure_annotation(scene):
    if scene.annotation is None:
        scene.annotation = bpy.data.annotations.new("Annotations")
    return scene.annotation


def ensure_layer(scene, name, color=None):
    """The annotation layer `name` (made if missing) and its frame at the current frame."""
    ann = ensure_annotation(scene)
    layer = ann.layers.get(name)
    if layer is None:
        layer = ann.layers.new(name)
        if color is not None:
            layer.color = color
    frame = frame_for(layer, scene.frame_current)
    if frame is None:
        frame = layer.frames.new(scene.frame_current)
    return layer, frame


def add_stroke(frame, points):
    """Append one stroke of world-space points (Blender 5.2+)."""
    st = frame.strokes.new()
    st.points.add(len(points))
    for p, c in zip(st.points, points):
        p.co = c
    return st
