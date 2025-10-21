from __future__ import annotations

import os
import xml.etree.ElementTree as ET  # noqa: DUO107,N817 # nosec B405
from typing import Any

from xdl_master.xdl.blueprints import Blueprint, create_blueprint
from xdl_master.xdl.constants import STEP_SECTIONS, SYNTHESIS_ATTRS
from xdl_master.xdl.context import Context
from xdl_master.xdl.errors import XDLDuplicateParameterID, XDLError
from xdl_master.xdl.hardware import Component
from xdl_master.xdl.metadata import Metadata
from xdl_master.xdl.parameters import Parameter
from xdl_master.xdl.readwrite.utils import read_file
from xdl_master.xdl.readwrite.validation import check_attrs_are_valid
from xdl_master.xdl.reagents import Reagent
from xdl_master.xdl.steps import AbstractBaseStep, Repeat, Step
from xdl_master.xdl.variables import Variable

# For type annotations
if False:
    from xdl.platforms import AbstractPlatform


def apply_step_record(step: Step, step_record_step: tuple[str, dict]):
    if step.name != step_record_step[0]:
        raise AssertionError  # TODO: raise more specific exception
    for prop in step.properties:

        # Comments or context don't need to be applied to step record.
        # No point adding comment or context to substep in xdlexe.
        if prop in ["comment", "context"]:
            continue

        if prop != "children" and prop != "uuid":
            if prop not in step_record_step[1]:
                raise XDLError(
                    f"Property {prop} missing from\
Step {step_record_step[0]}\nThis file was most likely generated from an\
older version of XDL. Regenerate the XDLEXE file using the latest\
version of XDL."
                )
            step.properties[prop] = step_record_step[1][prop]
    step.update()

    if isinstance(step, Repeat):
        return

    if not isinstance(step, AbstractBaseStep):
        if not len(step.steps) == len(step_record_step[2]):
            raise AssertionError(
                f"{step.steps}\n\n"
                f"{step_record_step[2]} {len(step.steps)}"
                f" {len(step_record_step[2])}"
            )
        for j, substep in enumerate(step.steps):
            apply_step_record(substep, step_record_step[2][j])


def synthesis_attrs_from_xdl(xdl_tree: ET.ElementTree) -> dict[str, Any]:
    """Return attrs from ``<Synthesis>`` tag.

    Arguments:
        xdl_tree (ET.ElementTree): ElementTree constructed from XML string.

    Returns:
        Dict[str, Any]: Attr dict from ``<Synthesis>`` tag.
    """
    raw_attr = {}
    for element in xdl_tree.iter():
        raw_attr.update(element.attrib)
    processed_attr = {}
    for attr in SYNTHESIS_ATTRS:
        if attr["name"] in raw_attr:
            processed_attr[attr["name"]] = raw_attr[attr["name"]]
    return processed_attr


def metadata_from_xdl(xdl_tree: ET.ElementTree) -> Metadata:
    """Given XDL str return Metadata object.

    Arguments:
        xdl_tree (ET.ElementTree): ElementTree constructed from XML string.

    Returns:
        Hardware: Metadata object with any parameters included in XDL loaded
    """
    for element in xdl_tree.findall("*"):
        if element.tag == "Metadata":
            return Metadata(**element.attrib)
    for element in xdl_tree.find("*"):
        if element.tag == "Metadata":
            return Metadata(**element.attrib)
    return Metadata()


def steps_from_xml(
    procedure: ET.ElementTree,
    context: Context,
    blueprints: list[Blueprint] | None = None,
    parameters: list[Parameter] | None = None,
) -> list[Step]:
    """Given standard, non-blueprint XDL ElementTree return list of
    Step objects.

    Arguments:
        procedure (ET.ElementTree): ElementTree constructed from XML string.
        blueprints (List[Blueprint], optional): list of Blueprint objects
            used to instantiate XDL2 blueprint steps.
        parameters (List[Parameter], optional): list of Parameter objects
            from XDL file.

    Returns:
        List[Step]: List of Step objects corresponding to procedure described
        in ``xdl_str``.
    """

    if not blueprints:
        blueprints = getattr(context, "blueprints")  # noqa: B009

    steps = {
        "no_section": [],
        "prep": [],
        "reaction": [],
        "workup": [],
        "purification": [],
    }

    for child in procedure.findall("*"):
        if child.tag in STEP_SECTIONS:
            steps[child.tag.lower()] = steps_from_xml(
                child, context, blueprints, parameters
            )["no_section"]
        else:
            steps["no_section"].append(
                xml_to_step(
                    xdl_step_element=child,
                    step_type_dict=context.platform.step_library,
                    context=context,
                    blueprints=blueprints,
                    parameters=parameters,
                )
            )
    return steps


def extract_tags(
    xdl_tree: ET.ElementTree, xpath: str, recursive=False
) -> tuple[str, dict]:
    """Parse XDL XML tree for a given XPath (part of the XML document).

    Args:
        xdl_tree (ET.ElementTree): ElementTree constructed from XML string.
        xpath (str): path to extract.
        recursive (bool, optional): If true, will look for 'children'
            within element and save them as an element attribute.
            Defaults to False.

    Returns:
        Tuple[str, Dict]: [description]
    """
    result = []
    for element in xdl_tree.findall(xpath):
        attrib = dict(element.attrib)
        if recursive:
            children = extract_tags(element, "*", recursive=True)
            if children:
                attrib["children"] = children
        # result.append((element.tag, attrib))
        result.append(element)
    return result


def blueprints_from_xdl(
    xdl_tree: ET.ElementTree, step_type_dict: dict[str, Step], context: Context
) -> list[Blueprint]:
    #  iterate through elements in tree, parsing blueprints and steps
    elements = xdl_tree.iter()
    blueprints = []
    for element in elements:
        if element.tag == "Blueprint":
            blueprints.append(
                xml_to_blueprint(
                    xml_blueprint_element=element,
                    context=context,
                    step_type_dict=step_type_dict,
                )
            )
    return blueprints


def get_base_steps(step: ET.Element) -> list[AbstractBaseStep]:
    """Return all base steps from step XML tree, recursively.

    Args:
        step (ET.Element): Step XML tree to get base steps from.
    """
    base_steps = []
    children = step.findall("*")
    if children:
        for child in children:
            base_steps.extend(get_base_steps(child))
    else:
        return [step]
    return base_steps


def find_element(
    xml_obj: ET.Element | ET.ElementTree,
    tag: str = "Synthesis",
    recursive: bool = False,
) -> ET.Element | None:
    """Searches XML Element or ElementTree for child element with matching
    tag. Currently used to get `Synthesis` element from XDL2 XMLs.

    Args:
        xml_obj (Union[ET.Element, ET.ElementTree]): XML Element or
            ElementTree.
        tag (str, optional): tag to search for in xml_obj.
            Defaults to 'Synthesis'.
        recursive (bool, optional): True to search recursively through whole
            tree. False to look only at direct children. Defaults to False.
    Returns:
        Optional[ET.Element]: `Synthesis` Element if found in xml_obj;
            otherwise NoneType.
    """
    #  for recursive search, flag this in ElementPath
    if recursive:
        tag = f".//{tag}"

    return xml_obj.find(tag)


def xml_to_step_template(
    element: ET.Element,
    step_type_dict: dict[str, type],
    context: Context,
) -> Step:
    """Generate a blueprint Step template from XML blueprint step element.

    Args:
        element (ET.Element): XML Element.

    Returns:
        Step: Step object. This will later be replaced with fully instantiated,
            final step(s) upon compilation.
    """
    attrib = dict(element.attrib)

    if element.tag in step_type_dict:

        step_type = step_type_dict[element.tag]

        check_attrs_are_valid(
            {k: v for k, v in attrib.items() if not k.startswith("param.")},
            step_type,
        )

    elif context.blueprints is not None and (element.tag not in context.blueprints):
        if not context.invalid_steps:
            context.update(invalid_steps=[element.tag])
        elif element.tag not in context.invalid_steps:
            context.invalid_steps.append(element.tag)

    children = [
        xml_to_step_template(
            element=child,
            step_type_dict=step_type_dict,
            context=context,
        )
        for child in element.findall("*")
    ]

    if children:
        attrib["children"] = children

    return Step(
        param_dict={
            **{
                "template_name": element.tag,
                "context": Context(parent_context=context),
            },
            **attrib,
        },
    )


def xml_to_blueprint(
    xml_blueprint_element: ET.Element, step_type_dict: dict[str, Step], context: Context
) -> type[Blueprint]:
    """Given XDL blueprint element return corresponding Blueprint object.

    Arguments:
        xml_blueprint_element (ET.Element): XDL step lxml element.
        step_type_dict (dict): library of valid step classes.

    Returns:
        Blueprint: Blueprint object for spawning steps as required.
    """
    element_attrs = xml_blueprint_element.attrib
    blueprint_dict = {
        "steps": {**{section: [] for section in STEP_SECTIONS}, **{"no_section": []}},
        "hardware": [],
        "reagents": [],
        "parameters": [],
        "id": element_attrs["id"],
        "props": element_attrs,
        "base_scale": None,
    }

    for child in xml_blueprint_element.findall("*"):
        if child.tag == "Hardware":
            for grandchild in child.findall("*"):
                blueprint_dict[child.tag.lower()].append(xml_to_component(grandchild))
        if child.tag == "Parameters":
            for grandchild in child.findall("*"):
                blueprint_dict[child.tag.lower()].append(xml_to_parameter(grandchild))
        elif child.tag == "Reagents":
            for grandchild in child.findall("*"):
                blueprint_dict[child.tag.lower()].append(xml_to_reagent(grandchild))
        elif child.tag == "Procedure":
            if "base_scale" in child.attrib:
                blueprint_dict["base_scale"] = child.attrib["base_scale"]
            for grandchild in child.findall("*"):
                if grandchild.tag in STEP_SECTIONS:
                    step_section = blueprint_dict["steps"][grandchild.tag]
                    for great_grandchild in grandchild.findall("*"):
                        step_section.append(
                            xml_to_step_template(
                                element=great_grandchild,
                                step_type_dict=step_type_dict,
                                context=context,
                            )
                        )
                else:
                    step_section = blueprint_dict["steps"]["no_section"]
                    step_section.append(
                        xml_to_step_template(
                            element=grandchild,
                            step_type_dict=step_type_dict,
                            context=context,
                        )
                    )
    return create_blueprint(**blueprint_dict, platform=context.platform)


def xml_to_step(
    xdl_step_element: ET.Element,
    step_type_dict: dict[str, type],
    context: Context,
    blueprints: list[Blueprint] | None = None,
    parameters: list[Parameter] | None = None,
) -> Step:
    """Given XDL step element return corresponding Step object.

    Arguments:
        xdl_step_element (ET.Element): XDL step lxml element.
        step_type_dict: Dict[str, type]: Dict of step names to step classes,
            e.g. ``{ 'Add': Add... }``
        context (Context): Context container class for bringing root XDL
            attributes (e.g. reagents, hardware) in scope within steps.
        blueprint (bool, False): specifies whether step can be instantiated as
            is, or if it is part of a blueprint XDL. Defaults to False.
        blueprints (List[Blueprint]): list of blueprints associated with the
            xdl file. Defaults to None.
        parameters (List[Parameter]): list of parameters associated with the
            xdl file. Defaults to None.

    Returns:
        Step: Step object corresponding to step in ``xdl_step_element``.
    """
    blueprints = blueprints or {}

    #  valid XML tags corresponding to a step can either be a standard step or
    #  a blueprint (from which standard steps can later be spawned)
    tag = xdl_step_element.tag
    valid_tags = {**step_type_dict, **blueprints}

    if not context.invalid_steps:
        context.update(invalid_steps=[])

    # Check if step name is valid and get step class.
    if tag not in valid_tags:
        context.invalid_steps.append(tag)

    children_steps = []
    children = xdl_step_element.findall("*")
    children_steps.extend(children)

    # Check all attributes are valid.
    attrs = dict(xdl_step_element.attrib)

    # treat invalid as blueprint steps and try to resolve them
    if (tag in blueprints) or (tag not in step_type_dict):

        if tag not in blueprints:
            resolved_bps = [
                retrieve_blueprint(name=s, context=context)
                for s in context.invalid_steps
            ]
            blueprints.update({b.id: b for b in resolved_bps})
        step_type = blueprints[tag]
    else:
        step_type = step_type_dict[tag]

    final_attrs = {}
    parameter_ids = [p.id for p in parameters]

    for attr in attrs:
        final_attrs[attr] = attrs[attr]

        if attrs[attr].lower() == "none":
            final_attrs[attr] = None

        # resolve any parameter values
        if attr.startswith("param.") or attrs[attr] in parameter_ids:
            value = attrs[attr]
            if attr.startswith("param."):
                attr = attr.split(".")[-1]

            final_attrs[attr] = map_xdl_to_parameter(value=value, parameters=parameters)

    # resolve child steps
    children_steps = [
        xml_to_step_template(
            element=c,
            step_type_dict=step_type_dict,
            context=context,
        )
        for c in children_steps
    ]

    check_attrs_are_valid(final_attrs, step_type)

    final_attrs["context"] = Context(parent_context=context)

    if (
        not issubclass(step_type, AbstractBaseStep)
        and "children" in step_type.__init__.__annotations__
    ):
        final_attrs["children"] = children_steps

    final_attrs["param_dict"] = {}

    # Try to instantiate step, any invalid values given will throw an error
    # here.
    step = step_type(**final_attrs)

    return step


def xml_to_component(xdl_component_element: ET.Element) -> Component:
    """Given XDL component element return corresponding Component object.

    Arguments:
       xdl_component_element (ET.Element): XDL component lxml element.

    Returns:
        Component: Component object corresponding to component in
        ``xdl_component_element``.
    """
    attrs = dict(xdl_component_element.attrib)

    # Check 'id' is in attrs..
    if "id" not in attrs:
        raise XDLError("'id' attribute not specified for component.")

    #  Check 'type' is in attrs.
    if "type" not in attrs:
        raise XDLError(f"'type' attribute not specified for {attrs['id']} component.")
    check_attrs_are_valid(attrs, Component)

    # Rename 'type' attr to 'component_type' to avoid conflict with Python
    # built-in function type.
    attrs["component_type"] = attrs["type"]
    del attrs["type"]

    # Try to instantiate components, any invalid values given will throw an
    # error here.
    component = Component(**attrs)
    return component


def xml_to_parameter(xdl_parameter_element: ET.Element) -> Parameter:
    """Given XDL parameter element return corresponding Parameter object.

    Arguments:
       xdl_parameter_element (ET.Element): XDL component lxml element.

    Returns:
        Parameter: Parameter object corresponding to parameter in
        ``xdl_parameter_element``.
    """
    attrs = dict(xdl_parameter_element.attrib)
    # Check 'id' is in attrs..
    if "id" not in attrs:
        raise XDLError("'id' attribute not specified for parameter.")

    check_attrs_are_valid(attrs, Parameter)

    # Rename 'type' attr to 'parameter_type' to avoid conflict with Python
    # built-in function type.
    attrs["parameter_type"] = attrs["type"]
    del attrs["type"]

    # Try to instantiate components, any invalid values given will throw an
    # error here.
    parameter = Parameter(**attrs)
    return parameter


def xml_to_variable(
    xdl_variable_element: ET.Element, platform: AbstractPlatform
) -> Variable:
    """Given XDL variable element return corresponding Variable object.

    Arguments:
       xdl_variable_element (ET.Element): XDL component lxml element.

    Returns:
        Variable: Variable object corresponding to variable in
        ``xdl_variable_element``.
    """
    attrs = dict(xdl_variable_element.attrib)

    vars_dict = platform.variable_library
    step_type = vars_dict[xdl_variable_element.tag]

    return step_type(**attrs)


def xml_to_reagent(xdl_reagent_element: ET.Element) -> Reagent:
    """Given XDL reagent element return corresponding Reagent object.

    Arguments:
        xdl_reagent_element (ET.Element): XDL reagent lxml element.

    Returns:
        Reagent: Reagent object corresponding to reagent in
        ``xdl_reagent_element``.
    """
    # Check attrs are valid for Reagent
    attrs = dict(xdl_reagent_element.attrib)
    # Try to instantiate Reagent object and return it.
    reagent = Reagent(**attrs)

    return reagent


def map_xdl_to_parameter(value: str, parameters: list[Parameter]) -> Any:
    """Map a non-blueprint (global) parameter to a Parameter value.

    Args:
        value (str): string to be mapped to a Parameter (must match a parameter
        id to be matched).
        parameters (List[Parameter]): List of Parameter objects to map to.

    Returns:
        parameter.value (Any): final mapped parameter value
    """

    if not parameters:
        return None

    parameter_match = [p for p in parameters if p.id == value]

    if not parameter_match:
        return None

    if len(parameter_match) > 1:
        XDLDuplicateParameterID(parameter=value, matches=parameter_match)

    parameter = parameter_match[0]

    return parameter.value


def retrieve_blueprint(name: str, context: Context, folder: str = None):
    """Given a blueprint name (str), this function searches that given folder
    for any .xdl files containing that blueprint.
    If no folder is specified, it will use the working directory.


    Args:
        name (str): blueprint id to be resolved.
        context (Context): Context container class for bringing root XDL
            attributes (e.g. reagents, hardware) in scope within steps.
            Must contain 'platform' as a minimum.
        folder (str): Folder containing xdl files to search through.

    Returns:
        List[Blueprint]: list of blueprints associated with the xdl files
         in the folder.
    """
    if folder is None:
        folder = context.working_directory

    xdl_files = [
        os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".xdl")
    ]

    all_blueprints = []

    if xdl_files:

        for xdl_file in xdl_files:

            xdl_tree = ET.ElementTree(ET.fromstring(read_file(xdl_file)))  # nosec B314
            file_bps = blueprints_from_xdl(
                xdl_tree=xdl_tree,
                step_type_dict=context.platform.step_library,
                context=context,
            )

            # update context blueprints with all bps from the same file as
            # the required one
            if name in [bp.id for bp in file_bps]:

                c_bps = context.blueprints if context.blueprints else {}
                context.update(blueprints={**c_bps, **{bp.id: bp for bp in file_bps}})

            all_blueprints.extend(file_bps)

    matching_bps = [bp for bp in all_blueprints if (bp.id == name)]

    if matching_bps:

        # add context to blueprints here, if passed in above, all resolved
        # blueprints will be added to context invalid context..
        for bp in matching_bps:
            bp.context = Context(parent_context=context)

        # raise error if more than 1 matching blueprint is found
        if len(matching_bps) > 1:
            raise XDLError(
                f"More than one blueprint found ({matching_bps}) for\
 {name} in {context.working_directory}."
            )

    # raise error if step cannot be resolved from blueprints
    else:
        raise XDLError(f"{name} is not a valid step type.")

    return matching_bps[0]


##########################
# .xdlexe interpretation #
##########################


def get_full_step_record(procedure_tree: ET.Element) -> list[tuple]:
    """Get the full step record for the procedure section of a xdlexe file.
    The step record is a nested representation of all steps and properties.
    It is needed so that top level steps can be initialised, and then properties
    of lower level steps are applied afterwards directly to the lower level
    steps. This allows editing of the xdlexe.

    Args:
        procedure_tree (ET.Element): XML tree of procedure section of XDL.

    Returns:
        List[Tuple]: Returns step record in format
        ``[(step_name, step_properties, substeps)...]``
    """
    step_record = []
    for step in procedure_tree.findall("*"):
        step_record.append(get_single_step_record(step))
    return step_record


def get_single_step_record(step_element: ET.Element) -> tuple[str, dict, list]:
    """Get step record for a single step.

    Args:
        step_element (ET.Element): XML tree for single step.

    Returns:
        Tuple[str, Dict, List]: Step record in the form
        ``(step_name, step_properties, substeps)``
    """
    children = []
    for step in step_element.findall("*"):
        children.append(get_single_step_record(step))
    return (step_element.tag, step_element.attrib, children)
