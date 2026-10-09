"""Sculpt mask helpers shared by modules (the mask lives in the point attribute .sculpt_mask).

Geometry Nodes cannot read internal attributes such as .sculpt_mask (a Named
Attribute node returns 0 for it), so modifiers get the mask through a vertex group.
"""

SCULPT_MASK = ".sculpt_mask"


def mask_values(mesh):
    """The sculpt mask per vertex, or None when the mesh has none."""
    attr = mesh.attributes.get(SCULPT_MASK)
    if attr is None or attr.domain != 'POINT':
        return None
    values = [0.0] * len(mesh.vertices)
    attr.data.foreach_get("value", values)
    return values


def values_to_group(obj, name, values):
    """Write per-vertex weights into the vertex group `name` (made if missing; 0 = not in it)."""
    vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    vg.remove(list(range(len(obj.data.vertices))))
    by_weight = {}
    for i, w in enumerate(values):
        if w > 0.0:
            by_weight.setdefault(w, []).append(i)
    for w, idx in by_weight.items():
        vg.add(idx, w, 'REPLACE')
    return vg


def mask_to_group(obj, name):
    """Copy the sculpt mask into the vertex group `name`; None when there is no mask."""
    values = mask_values(obj.data)
    if values is None:
        return None
    return values_to_group(obj, name, values)
