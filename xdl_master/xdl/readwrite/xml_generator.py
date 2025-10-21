from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: DUO107,N817 # nosec B405

from xdl_master.xdl.blueprints import Blueprint
from xdl_master.xdl.constants import XDL_VERSION
from xdl_master.xdl.hardware import Hardware
from xdl_master.xdl.metadata import Metadata
from xdl_master.xdl.reagents import Reagent
from xdl_master.xdl.steps import Step
from xdl_master.xdl.utils.misc import format_property
from xdl_master.xdl.utils.sanitisation import convert_val_to_std_units
from xdl_master.xdl.utils.steps import steps_from_step_templates

if False:
    from xdl import XDL


def xdl_to_xml_string(
    xdl_obj: XDL,
    full_properties: bool = False,
    full_tree: bool = False,
    graph_hash: str = None,
) -> str:
    """Convert given XDL object to XML string.

    Args:
        xdl_obj (XDL): XDL object to convert to XML string.
    full_properties (bool): If ``True`, all properties will be written.
            If ``False`` only mandatory, non default values and always write
            properties will be written.
        full_tree (bool): If ``True``, full step tree will be written as is the
            case in xdlexe files.
        graph_hash (str): Hash of graph to include in xdlexe files.

    Returns:
        str: Pretty printed XML string of procedure.
    """
    xml_tree = get_xdl_tree(xdl_obj, full_properties, full_tree, graph_hash)
    return _get_xdl_string(xdltree=xml_tree)


def step_to_xml_string(
    step: Step,
    full_properties: bool = False,
    full_tree: bool = False,
) -> str:
    """Get pretty printed XML string of given step.

    Args:
        step (Step): Step to get XDLEXE string for.
        full_properties (bool): If ``True``, all properties will be written.
            If ``False`` only mandatory, non default values and always write
            properties will be written.
        full_tree (bool): If ``True``, full step tree will be written as is the
            case in xdlexe files.
    """
    step_tree = _get_step_tree(step, full_properties, full_tree)[0]
    return _get_element_xdl_string(step_tree)


#######################
# XML Tree Generation #
#######################


def get_xdl_tree(
    xdl_obj: XDL,
    full_properties: bool = False,
    full_tree: bool = False,
    graph_hash: str = None,
) -> ET.Element:
    """Get XDL element tree ready for saving as XML.

    Args:
        xdl_obj (XDL): XDL object to convert to XML tree.
        full_properties (bool): If ``True`` include all properties regardless of
            whether they are internal props or the same as the default props.
            Defaults to ``False``.
        full_tree (bool): If ``True`` include all substeps, i.e. for a xdlexe
            file. Defaults to ``False``.
        graph_hash (str): Hash of graph used to produce xdlexe for including in
            ``<Synthesis>`` tag.

    Returns:
        ET.ElementTree: XML tree of ``xdl_obj`` ready to save to XML file.
    """
    reagents = xdl_obj.reagents
    hardware = xdl_obj.hardware

    # Create <Synthesis> tag with graph hash if given.
    xdltree = ET.Element("Synthesis")
    if graph_hash:
        xdltree.attrib["graph_sha256"] = graph_hash

    _append_metadata(xdltree, xdl_obj.metadata)

    # Add <Hardware /> section to tree
    _append_hardware_tree(xdltree, hardware)

    # Add <Reagents /> section to tree
    _append_reagents_tree(xdltree, reagents)

    # Add <Procedure  /> section to tree
    _append_procedure_tree(
        xdltree, xdl_obj, full_properties=full_properties, full_tree=full_tree
    )

    return xdltree


def _append_metadata(xdltree: ET.ElementTree, metadata: Metadata) -> None:
    """Create and add Metadata section to XDL tree. Only add if Metadata has
    been used.

    Args:
        xdltree (ET.ElementTree): Full XDL XML tree to add hardware to.
        metadata (Metadata): Metadawta to add to XML tree.
    """
    props = metadata.properties
    # Metadata used
    if any(props.values()):
        metadata_tree = ET.Element("Metadata")
        for k, v in props.items():
            if v:
                metadata_tree.attrib[k] = v
        xdltree.append(metadata_tree)


def _append_hardware_tree(xdltree: ET.ElementTree, hardware: Hardware) -> None:
    """Create and add Hardware section to XDL tree.

    Args:
        xdltree (ET.ElementTree): Full XDL XML tree to add hardware to.
        hardware (Hardware): Hardware to add to XML tree.
    """
    hardware_tree = ET.Element("Hardware")
    for component in hardware:
        component_tree = ET.Element("Component")
        for prop in component.PROP_TYPES:
            val = component.properties[prop]
            if val is not None:
                if prop == "component_type":
                    component_tree.attrib["type"] = str(val)
                # Don't write empty comment field.
                elif val:
                    component_tree.attrib[prop] = str(val)
        hardware_tree.append(component_tree)
    xdltree.append(hardware_tree)


def _append_reagents_tree(xdltree: ET.ElementTree, reagents: list[Reagent]) -> None:
    """Create and add Reagents section to XDL tree.

    Args:
        xdltree (ET.ElementTree): Full XDL XML tree to add reagents to.
        reagents (List[Reagent]): Reagents to add to XML tree.
    """
    reagents_tree = ET.Element("Reagents")
    for reagent in reagents:
        reagent_tree = ET.Element("Reagent")
        for prop in reagent.PROP_TYPES:
            val = reagent.properties[prop]
            if val:
                reagent_tree.attrib[prop] = str(val)
        reagents_tree.append(reagent_tree)
    xdltree.append(reagents_tree)


def _append_procedure_tree(
    xdltree: ET.ElementTree,
    xdl_obj: XDL,
    full_properties: bool = False,
    full_tree: bool = False,
) -> None:
    """Create and add Procedure section to XDL tree.

    Args:
        xdltree (ET.ElementTree): Full XDL XML tree to add steps to.
        steps (List[Step]): Steps to add to XML tree.
        full_properties (bool): If ``True``, all properties will be written.
            If ``False`` only mandatory, non default values and always write
            properties will be written.
        full_tree (bool): If ``True``, full step tree will be written as is the
            case in xdlexe files.
    """
    sections = {k: v for k, v in xdl_obj.sections.items() if k != "no_section"}
    procedure_tree = ET.Element("Procedure")
    section_trees = {section.capitalize(): None for section in sections}

    for step in xdl_obj.steps:
        step_tree = _get_step_tree(
            step, full_properties=full_properties, full_tree=full_tree
        )
        # XDLEXE, don't worry about procedure sections.
        if full_tree:
            procedure_tree.extend([*step_tree])

        # Just XDL, generate with procedure sections
        else:
            for section, section_steps in sections.items():
                section = section.capitalize()
                if step.uuid in section_steps:
                    if section_trees[section] is None:
                        section_trees[section] = ET.Element(section)
                    section_trees[section].extend([*step_tree])
                    break
            else:
                # step is no_section
                procedure_tree.extend([*step_tree])

    for _section, section_tree in section_trees.items():
        if section_tree is not None:
            procedure_tree.append(section_tree)
    xdltree.append(procedure_tree)


def _get_step_tree(
    step: Step,
    full_properties: bool = False,
    full_tree: bool = False,
) -> ET.Element:
    """Get XML tree associated with given step.

    Args:
        step (Step): Step to generate XML tree for.
        full_properties (bool): If ``True``, all properties will be written.
            If ``False`` only mandatory, non default values and always write
            properties will be written.
        full_tree (bool): If ``True``, full step tree will be written as is the
            case in xdlexe files.
    """
    root_node = ET.Element("root")

    if isinstance(step, Blueprint):
        step_tree = root_node
    else:
        step_node = ET.Element(step.name)
        root_node.append(step_node)
        step_tree = step_node

    children = False
    for prop in step.PROP_TYPES:
        # Find out if step has children, and if they should be written (xdlexe)
        if prop == "children" and step.properties[prop] and full_properties:
            children = True

        # Add property to step tree
        _add_step_property(
            step_tree, step, prop, full_properties=full_properties, full_tree=full_tree
        )

    if full_tree:
        # children already added in _add_step_property
        if children:
            pass
        else:
            for substep in step.steps:
                subtree = _get_step_tree(
                    substep,
                    full_properties=full_properties,
                    full_tree=full_tree,
                )
                step_tree.extend([*subtree])
    return root_node


def _add_step_property(
    step_tree: ET.Element,
    step: Step,
    prop: str,
    full_properties: bool = False,
    full_tree: bool = False,
) -> None:
    """Add given property to step tree of given step.

    Args:
        step_tree (ET.Element): Step tree to add property to.
        step (Step): Step corresponding to ``step_tree``.
        prop (str): Property to add to ``step_tree``.
        full_properties (bool): If ``True``, all properties will be written.
            If ``False`` only mandatory, non default values and always write
            properties will be written.
        full_tree (bool): If ``True``, full step tree will be written as is the
            case in xdlexe files. This applies to ``'children'`` property.
    """
    val = step.properties[prop]

    if prop == "children" and val:
        if full_properties:
            children_tree = ET.Element("Children")

            # need to instantiate children 'Step' objects before writing them
            # val = steps_from_step_templates(step, val, bindings={}, validate=False)

            for child in val:
                child_tree = _get_step_tree(
                    child, full_properties=full_properties, full_tree=full_tree
                )
                children_tree.extend([*child_tree])
            step_tree.extend([*children_tree])
        else:
            for child in val:
                child_tree = _get_step_tree(
                    child, full_properties=full_properties, full_tree=full_tree
                )
                step_tree.extend([*child_tree])
    else:
        if val is not None or full_properties:
            # if self.full_properties is False ignore some properties.
            if not full_properties:

                # Don't write properties that are the same as the
                # default.
                if (
                    prop in step.DEFAULT_PROPS
                    and convert_val_to_std_units(step.DEFAULT_PROPS[prop]) == val
                ):

                    # Some things should always be written even if they
                    # are default.
                    if prop not in step.ALWAYS_WRITE:
                        return

                # Don't write internal properties.
                if prop in step.INTERNAL_PROPS:
                    return
            # Convert value to nice units and add to element attrib.
            formatted_property = format_property(
                prop,
                val,
                step.PROP_TYPES[prop],
                step.PROP_LIMITS.get(prop, None),
                human_readable=False,
            )

            if formatted_property is None:
                formatted_property = str(formatted_property)

            step_tree.attrib[prop] = formatted_property


###############################
# String Generation from Tree #
###############################


def _get_element_xdl_string(
    element: ET.ElementTree, indent_level=0, indent="  "
) -> str:
    """Return given Step, Reagent or Component XML tree as pretty printed XML
    string.

    Args:
        element (ET.ElementTree): Step, Reagent or Component XML tree to
            convert to string.
        indent_level (int): Defaults to 0. Used by this function to handle
            indendation during recursive calls.
        indent (str): Defaults to ``'  '``. Indent to use for pretty printing
            XML string.

    Returns:
        str: Pretty printed XML string of given XML tree.
    """
    s = ""
    s += f"{indent * indent_level}<{element.tag}\n"
    has_children = list(element.findall("*"))
    indent_level += 1
    # Element Properties
    for attr, val in element.attrib.items():
        if val is not None:
            if attr == "context":
                continue
            s += f'{indent * indent_level}{attr}="{val}"\n'

    if has_children:
        s = s[:-1] + ">\n"
    else:
        s = s[:-1] + " />\n"
    for subelement in element.findall("*"):
        s += _get_element_xdl_string(
            subelement, indent_level=indent_level, indent=indent
        )

    indent_level -= 1
    if has_children:
        s += f"{indent * indent_level}</{element.tag}>\n"
    return s


def _get_xdl_string(xdltree: ET.ElementTree) -> str:
    """Convert XDL element tree to pretty XML string.

    Args:
        xdltree (ET.ElementTree): element tree of XDL

    Returns:
        str: XML string
    """
    indent = "  "
    # Synthesis tag
    s = f'<?xdl version="{XDL_VERSION}" ?>\n'
    s += "<XDL>\n\n"
    s += "<Synthesis"
    if xdltree.attrib:
        s += "\n"
        for prop in xdltree.attrib:
            s += f'{indent}{prop}="{xdltree.attrib[prop]}"\n'
    s += ">\n\n"
    indent_level = 1
    # Hardware, Reagents and Procedure tags
    for element in xdltree.findall("*"):

        # Metadata section
        if element.tag == "Metadata":
            s += _get_element_xdl_string(
                element, indent=indent, indent_level=indent_level
            )
            s += "\n"

        # Procedure, Reagents or Hardware section start
        else:
            s += f"{indent * indent_level}<{element.tag}>\n"

        indent_level += 1
        # Component, Reagent and Step tags
        for element2 in element.findall("*"):
            s += _get_element_xdl_string(
                element2, indent=indent, indent_level=indent_level
            )
        indent_level -= 1

        # Procedure, Reagents or Hardware section end
        if element.tag != "Metadata":
            s += f"{indent * indent_level}</{element.tag}>\n\n"
    s += "</Synthesis>\n\n"
    s += "</XDL>\n"
    return s
