from xdl.steps import Step


def deep_copy_step(step: Step):
    """Deprecated. Step.__deepcopy__ now implemented so you can just do
    ``copy.deepcopy(step)``. This remains here for backwards compatibility
    but should eventually be removed.

    Return a deep copy of a step. Written this way with children handled
    specially for compatibility with Python 3.6.
    """
    # Copy children
    children = []
    if "children" in step.properties and step.children:
        for child in step.steps:
            children.append(deep_copy_step(child))

    # Copy properties
    copy_props = {}
    for k, v in step.properties.items():
        if k != "children":
            copy_props[k] = v
    copy_props["children"] = children

    # Make new step
    copied_step = type(step)(**copy_props)

    return copied_step
