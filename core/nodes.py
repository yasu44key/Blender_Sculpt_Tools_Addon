"""Geometry Nodes helpers that differ between Blender versions."""


def set_modifier_input(modifier, identifier, value):
    """Set a Geometry Nodes modifier input by its socket identifier ("Socket_2").

    Blender 5.2 exposes inputs as modifier.properties.inputs.<identifier>.value
    and refuses modifier["Socket_2"] = value; 5.1 only has the ID-property form.
    """
    props = getattr(modifier, "properties", None)
    if props is not None and hasattr(props.inputs, identifier):
        getattr(props.inputs, identifier).value = value
    else:
        modifier[identifier] = value
    # Written from Python, neither form re-evaluates the object by itself.
    modifier.id_data.update_tag()


def get_modifier_input(modifier, identifier):
    props = getattr(modifier, "properties", None)
    if props is not None and hasattr(props.inputs, identifier):
        return getattr(props.inputs, identifier).value
    return modifier[identifier]


def socket_identifier(node_group, name, in_out='INPUT'):
    """Identifier ("Socket_n") of a node group interface socket by its name."""
    for item in node_group.interface.items_tree:
        if getattr(item, "in_out", None) == in_out and item.name == name:
            return item.identifier
    raise KeyError(name)


def draw_modifier_input(layout, modifier, identifier, text):
    """Draw a Geometry Nodes modifier input in a panel (5.2 and 5.1 forms)."""
    props = getattr(modifier, "properties", None)
    if props is not None and hasattr(props.inputs, identifier):
        layout.prop(getattr(props.inputs, identifier), "value", text=text)
    else:
        layout.prop(modifier, f'["{identifier}"]', text=text)
