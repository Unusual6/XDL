from __future__ import annotations

from xdl_master.xdl.context import Context
from xdl_master.xdl.errors import XDLInvalidStepsTypeError, XDLNoParameterValue
from xdl_master.xdl.steps import Step


def steps_into_sections(steps: list[Step] | dict[str, list[Step]]):
    """Load steps. Called from constructor. If procedure sections are used
    steps are flattened into :py:attr:`steps`, but UUIDs are linked to
    sections so that steps can be saved into correct sections when
    generating files.

    Args:
        steps (Union[List[Step], Dict[str, List[Step]]]): EIther a simple
            list of steps if procedure sections are not being used.
            Otherwise a dict with keys 'no_section', 'prep', 'reaction',
            'workup', 'purification', and values of lists of steps.
    """
    if not isinstance(steps, (list, dict)):
        raise XDLInvalidStepsTypeError(type(steps))

    if isinstance(steps, list):
        steps = {
            "no_section": steps,
            "prep": [],
            "reaction": [],
            "workup": [],
            "purification": [],
        }

    all_steps = []
    sections = {}
    for section in steps:
        sections[section] = []
        for step in steps[section]:
            all_steps.append(step)
            if isinstance(step, Step):
                sections[section].append(step.uuid)

    return all_steps, sections


def steps_from_step_templates(
    parent,
    step_templates: list[Step],
    bindings: dict[str, str],
    validate: bool = False,
) -> list[Step]:
    """Takes a list of blueprint step tuples and returns list of final,
    instantiated Step objects.

    Args:
        step_templates (List[Tuple[str, Dict]]): list of Blueprint step
            templates.
    Returns:
        List[Step]: list of instantiated steps.
    """
    steps = []

    pc = parent.context

    if pc is None or pc.platform is None:
        # just return step_templates if contexts has no platform
        # steps (created in Python)
        return step_templates

    reagents = pc.reagents or []
    hardware = pc.hardware or []
    parameters = pc.parameters or []
    blueprints = pc.blueprints or {}

    step_lib = {**blueprints, **pc.platform.step_library}

    parameter_ids = [p.id for p in parameters]

    #  iterate through BP step tuples, retrieving step type from step
    #  library and parsing final step props
    for step_template in step_templates:
        if type(step_template) is not Step:
            # not a step template; use step as is
            steps.append(step_template)
            continue

        step_type = step_lib[step_template.name]

        #  final props for step instantiation - ensure step has proper
        #  validation of props by flagging as full, non-blueprint step
        final_props = {
            "context": Context(parent_context=parent.context),
            "parent": parent,
        }

        for prop, prop_value in step_template.init_props.items():
            if prop.startswith("param.") or prop_value in parameter_ids:
                #  parse parameter prop
                prop = prop.split(".")[-1]
                try:
                    if prop_value in parameter_ids:
                        prop_value = pc.resolve(prop_value).value
                    else:
                        prop_value = getattr(parent, prop_value)

                except AttributeError:
                    raise XDLNoParameterValue(parameter_id=prop_value)
            elif isinstance(prop_value, str):
                prop_value = bindings.get(prop_value, prop_value)

            final_props[prop] = prop_value

        step = step_type(**{**bindings, **final_props})

        if validate:
            step._validate_vessel_and_reagent_props_step(
                step=step,
                reagent_ids=[
                    *[r.id for r in reagents],
                    *[r.name for r in reagents if r.name],
                ],
                vessel_ids=[h.id for h in hardware],
            )

        steps.append(step)

    return steps
