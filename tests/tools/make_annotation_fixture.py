"""Rebuild tests/data/annotation.blend (needs Blender 5.2+: Python can add annotation strokes only from 5.2).

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --factory-startup -b --python tests/tools/make_annotation_fixture.py -- tests/data/annotation.blend
"""
import bpy, math, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene
ann = bpy.data.annotations.new("Annotations"); sc.annotation = ann
def stroke(fr, pts):
    st = fr.strokes.new(); st.points.add(len(pts))
    for p, c in zip(st.points, pts): p.co = c
# layer 0 "Other": one stroke (should be ignored by ACTIVE)
a = ann.layers.new("Other"); f = a.frames.new(1); stroke(f, [(0, -2, 0), (1, -2, 0)])
# layer 1 "Notes" (active): an L with a sharp corner (dense), a smooth arc, and a one-point dot
b = ann.layers.new("Notes"); f = b.frames.new(1)
L = [(x * 0.05, 0, 0) for x in range(21)] + [(1.0, y * 0.05, 0) for y in range(1, 21)]
stroke(f, L)
arc = [(3 + math.cos(t / 40 * math.pi), math.sin(t / 40 * math.pi), 0.5) for t in range(41)]
stroke(f, arc)
stroke(f, [(5, 5, 5)])
# layer 2 "Hidden": hidden, one stroke
c = ann.layers.new("Hidden"); c.annotation_hide = True; f = c.frames.new(1); stroke(f, [(0, 4, 0), (1, 4, 0)])
ann.layers.active_index = 1
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SAVED")
