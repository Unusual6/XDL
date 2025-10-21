from __future__ import annotations

import asyncio
import collections
import datetime
import json
import logging
import os
import re
import sys
import weakref
import xml.etree.ElementTree as ET  # noqa: DUO107,N817 # nosec B405
from collections import Counter
from typing import Any

import nest_asyncio
import tabulate

from xdl_master.xdl.constants import CORE_CONTEXT_ATTRS, XDL_1_ROOT, XDL_2_ROOT
from xdl_master.xdl.context import Context
from xdl_master.xdl.errors import (
    XDLReagentNotDeclaredError,
    XDLVesselNotDeclaredError,
    XDLAttrDuplicateID,
    XDLDoubleCompilationError,
    XDLDurationBeforeCompilationError,
    XDLEquivReferenceNotInReagents,
    XDLError,
    XDLExecutionBeforeCompilationError,
    XDLFileNotFoundError,
    XDLInvalidArgsError,
    XDLInvalidEquivalentsInput,
    XDLInvalidFileTypeError,
    XDLInvalidInputError,
    XDLInvalidPlatformControllerError,
    XDLInvalidPlatformError,
    XDLInvalidSaveFormatError,
    XDLLanguageUnavailableError,
    XDLNoPlatformSuppliedError,
    XDLPlatformMismatchError,
    XDLReagentVolumesBeforeCompilationError,
    XDLStepIndexError,
    XDLStepNotInStepsListError,
    XDLXMLInvalidRoot,
)
from xdl_master.xdl.hardware import Hardware
from xdl_master.xdl.metadata import Metadata
from xdl_master.xdl.parameters import Parameter
from xdl_master.xdl.platforms.abstract_platform import AbstractPlatform
from xdl_master.xdl.readwrite.json import xdl_from_json, xdl_from_json_file, xdl_to_json
from xdl_master.xdl.readwrite.utils import read_file
from xdl_master.xdl.readwrite.xml_generator import xdl_to_xml_string
from xdl_master.xdl.readwrite.xml_interpreter import (
    apply_step_record,
    extract_tags,
    get_full_step_record,
    metadata_from_xdl,
    steps_from_xml,
    synthesis_attrs_from_xdl,
    xml_to_blueprint,
    xml_to_component,
    xml_to_parameter,
    xml_to_reagent,
)
from xdl_master.xdl.reagents import Reagent
from xdl_master.xdl.steps.core import AbstractBaseStep, Step
from xdl_master.xdl.steps.utils import FTNDuration
from xdl_master.xdl.utils.localisation import get_available_languages
from xdl_master.xdl.utils.logging import get_logger
from xdl_master.xdl.utils.misc import (
    reagent_volumes_table,
    resolve_working_directory,
    steps_are_equal,
    xdl_elements_are_equal,
)
from xdl_master.xdl.utils.steps import steps_into_sections
from xdl_master.xdl.utils.vessels import VesselSpec
from xdl_master.xdl.variables import Variable

from xdl_master.xdl.blueprints import Blueprint  # isort: skip  # Import after Metadata!


class XDL:
    """Object for inspecting and manipulating XDL procedure.

    One of ``xdl`` or (``steps``, ``hardware`` and ``reagents``) must be given
    to ``__init__``.

    Args:
        xdl(Union[str, Dict]): Path to XDL file  (.json, .xdl or .xdlexe), XDL
            XML string, or XDL JSON dict.
        steps (List[Step]): List of Step objects.
        hardware (Hardware): Hardware object containing all
            components in XDL.
        parameters (Dict[Str, Any]): Dict of Parameter id's and corresponding
            values, to be used to overwrite any default parameter values.
        reagents (List[Reagent]): List of Reagent objects containing reagents
            used in ``steps``.
        logging_level (int): Logging level to use when creating
            :py:attr:`logger`. Defaults to ``logging.INFO``.
        log_folder (str): Folder to save log files in. If ``None``, logs will
            not be saved to a file.
        platform (AbstractPlatform): Optional. Target platform.
        working_directory (str): working directory for loading XDL blueprints
            from other files. If None, working directory will be set based on
            XDL file location or using the environment variable XDLPATH.

    Raises:
        ValueError: If insufficient args provided to instantiate object.

    Attributes:
        steps (List[Step]): List of Step subclass objects representing
            procedure.
        reagents (List[Reagent]): List Reagent objects representing reagents
            used in :py:attr:`steps`.
        parameters (List[Parameter]): List of Parameter objects that may be used
            in steps with the relevant id.
        platform (AbstractPlatform): Target platform for XDL. Even if not
            physically executing, platform is used to create step trees.
        _xdl_file (str): File name XDL was initialized from. ``None`` if object
            not initialized from file.
        compiled (bool): ``True`` if XDL procedure has been compiled and is
            ready to execute, otherwise ``False``.
        graph_sha256 (str): Graph hash of the graph the procedure was compiled
            with. If procedure has not been compiled, ``None``.
        logger (logging.Logger): Logger object for all your logging needs.
        context (Context): Container for objects required by steps.
        working_directory (str): working directory for loading XDL blueprints
            from other files. If None, working directory will be set based on
            XDL file location or using the environment variable XDLPATH.
    """

    # File name XDL was initialised from
    _xdl_file = None

    # Graph hash contained in <Synthesis> tag if XDL object is from xdlexe file
    graph_sha256 = None

    # True if XDL is loaded from xdlexe, or has been compiled, otherwise False
    # self.compiled == True implies that procedure is ready to execute
    compiled = False

    # is set to False if dynamic steps (e.g. Repeat using iteration)
    # are detected
    write_xexe = True

    def __init__(
        self,
        xdl: str | dict = None,
        steps: list[Step] = None,
        hardware: Hardware = None,
        reagents: list[Reagent] = None,
        parameters: dict[str, Any] = None,
        variables: list[Variable] = None,
        logging_level: int = logging.INFO,
        platform: AbstractPlatform = "chemputer",
        working_directory: str = None,
        **kwargs,
    ) -> None:
        self._initialize_logging(logging_level)
        self._internal_platform = kwargs.get("internal_platform") or platform
        self._load_platform(platform)

        self.context = Context(
            parent_context=None, xdl=weakref.ref(self), platform=self.platform
        )

        self.task_groups = None

        self.working_directory = resolve_working_directory(
            xdl=xdl, working_directory=working_directory
        )
        self.context.update(working_directory=self.working_directory)

        #  assume no blueprints in XDL unless found
        self.blueprints = None
        self._load_xdl(
            xdl,
            steps=steps,
            hardware=hardware,
            reagents=reagents,
            parameters=parameters,
            variables=variables,
        )
        self.executor = self.platform.executor(self)
        self.compiled = self.graph_sha256 is not None

        self.context.update(reagents=self.reagents, parameters=self.parameters)

        self._validate_loaded_xdl()

    @property
    def _loop(self) -> asyncio.AbstractEventLoop:
        try:
            _loop = asyncio.get_running_loop()
        except RuntimeError:
            _loop = asyncio.new_event_loop()
        return _loop

    ##################
    # Initialization #
    ##################

    def _initialize_logging(self, logging_level: int) -> None:
        """Initialize logger with given logging level."""
        self.logger = get_logger()
        self.logger.setLevel(logging_level)
        self.logging_level = logging_level

    def _load_platform(self, platform) -> None:
        """Initialise given platform. If ``None`` given then initialise
        ``ChemputerPlatform`` otherwise platform should be a subclass of
        ``AbstractPlatform``.

        Raises:
            XDLNoPlatformSuppliedError: No platform given
            XDLInvalidPlatformError: If platform is not ``None`` or a
                subclass of ``AbstractPlatform``.
        """
        # if self._internal_platform is None:
        #     raise XDLNoPlatformSuppliedError()
        # elif issubclass(self._internal_platform, AbstractPlatform):
        #     self.platform = self._internal_platform()
        # else:
        #     raise XDLInvalidPlatformError(self._internal_platform)
        if platform == "chemputer":
            from chemputerxdl.chemputerxdl import ChemputerPlatform

            self.platform = ChemputerPlatform()
        elif issubclass(platform, AbstractPlatform):
            self.platform = platform()
        else:
            raise XDLInvalidPlatformError(platform)

    def _load_xdl(
        self,
        xdl: str | dict,
        steps: list[Step],
        reagents: list[Reagent],
        hardware: Hardware,
        parameters: list[Parameter],
        variables: list[Variable],
    ) -> None:
        """Load XDL from given arguments. Valid argument combinations are
        just xdl, or all of steps, reagents and hardware. xdl can be a path to a
        .xdl, .xdlexe or .json file, or an XML string of the XDL.

        Args:
            xdl (str): Path to .xdl, .xdlexe or .json XDL file, XML string, or
                JSON dict.
            steps (List[Step]): List of Step objects to instantiate XDL with.
            reagents (List[Reagent]): List of Reagent objects to instantiate XDL
                with.
            hardware (Hardware): Hardware object to instantiate XDL with.
            parameters (List[Parameter]): List of Parameter objects to
                instantiate XDL with.
            variables (List[Variable]): List of Variable objects to
                instantiate XDL with.

        Raises:
            XDLFileNotFoundError: xdl file given, but file not found.
            XDLInvalidInputError: xdl is not file or valid XML string.
            XDLInvalidArgsError: Invalid combination of arguments given.
                Valid argument combinations are just xdl, or all of steps,
                reagents and hardware.
        """
        # Fallback metadata if not loaded from file
        self.metadata = Metadata()

        self.parameters = []

        if parameters:
            self.parameters = [Parameter(id=p, value=parameters[p]) for p in parameters]

        # Load from XDL file or string
        if xdl:
            # Load from JSON dict
            if type(xdl) == dict:
                self._load_xdl_from_json_dict(xdl)

            elif type(xdl) == str:

                # Load from file
                if os.path.exists(xdl):

                    if len(xdl) > 260 and sys.platform.startswith("win"):
                        self.logger.warning(
                            f"WARNING: some Windows machines have \
filepath limits of 260, length of current xdl filepath = {len(xdl)}"
                        )

                    self._load_xdl_from_file(xdl)

                # Incorrect file path, raise error.
                elif xdl.endswith((".xdl", ".xdlexe", ".json")):
                    raise XDLFileNotFoundError(xdl)

                # Load XDL from string, check string is not mismatched file path
                elif "<Synthesis" in xdl and "<Procedure>" in xdl:
                    self._load_xdl_from_xml_string(xdl)

            # Invalid input, raise error
            else:
                raise XDLInvalidInputError(xdl)

        # Initialise XDL from lists of Step, Reagent and Component objects
        elif steps is not None and reagents is not None and hardware is not None:
            self.hardware, self.reagents = hardware, reagents

            self.steps, self.sections = steps_into_sections(steps)
            self.executor = self.platform.executor(self)

        # Invalid combination of arguments given, raise error
        else:
            raise XDLInvalidArgsError()

    def _load_xdl_from_json_dict(self, xdl_json):
        """Load XDL from JSON dict.

        Args:
            xdl_json (Dict): XDL JSON dict.
        """
        parsed_xdl = xdl_from_json(
            xdl_json=xdl_json, platform=self.platform, context=self.context
        )
        self.steps, self.sections = steps_into_sections(parsed_xdl["steps"])
        self.hardware = parsed_xdl["hardware"]
        self.reagents = parsed_xdl["reagents"]
        self.metadata = parsed_xdl["metadata"]
        self.parameters = parsed_xdl["parameters"]
        self.variables = parsed_xdl["variables"]

    def _load_xdl_from_file(self, xdl_file):
        """Load XDL from .xdl, .xdlexe or .json file.

        Args:
            xdl_file (str): .xdl, .xdlexe or .json file to load XDL from.

        Raises:
            XDLInvalidFileTypeError: If given file is not .xdl, .xdlexe or .json
        """
        file_ext = os.path.splitext(xdl_file)[1]

        # Load from XML .xdl or .xdlexe file
        if file_ext == ".xdl" or file_ext == ".xdlexe":
            self._xdl_file = xdl_file
            xdl_str = read_file(xdl_file)
            self._load_xdl_from_xml_string(xdl_str)

        # Load from .json file
        elif file_ext == ".json":
            parsed_xdl = xdl_from_json_file(
                xdl_json_file=xdl_file, platform=self.platform, context=self.context
            )

            self.steps, self.sections = steps_into_sections(parsed_xdl["steps"])
            self.hardware = parsed_xdl["hardware"]
            self.reagents = parsed_xdl["reagents"]
            self.metadata = parsed_xdl["metadata"]
            self.parameters = parsed_xdl["parameters"]
            self.variables = parsed_xdl["variables"]
            self.blueprints = parsed_xdl["blueprints"]

        # Invalid file type, raise error
        else:
            raise XDLInvalidFileTypeError(file_ext)

    def _load_xdl_from_xml_string(self, xdl_str):
        """Load XDL from XML string.

        Args:
            xdl_str (str): XML string of XDL.
        """
        if type(xdl_str) == str:
            xdl_str = ET.ElementTree(ET.fromstring(xdl_str))  # nosec B314

        root = xdl_str.getroot().tag

        if root not in [XDL_1_ROOT, XDL_2_ROOT]:
            raise XDLXMLInvalidRoot(
                invalid_root=root, valid_roots=[XDL_1_ROOT, XDL_2_ROOT]
            )

        synthesis_tree = xdl_str

        #  check for XDL2 synthesis
        for element in xdl_str.findall("*"):
            if element.tag == "Synthesis":
                for child in element.findall("*"):
                    if child.tag == "Procedure":
                        synthesis_tree = ET.ElementTree(element)

        xdl_elems = {
            "procedures": extract_tags(synthesis_tree, "Procedure"),
            "reagents": extract_tags(synthesis_tree, "Reagents/Reagent"),
            "variables": extract_tags(synthesis_tree, "Variables/*"),
            "parameters": extract_tags(synthesis_tree, "Parameters/Parameter"),
            "hardware": extract_tags(synthesis_tree, "Hardware/Component"),
            "blueprints": extract_tags(xdl_str, "Blueprint"),
        }

        if not xdl_elems["procedures"]:
            raise XDLError("No Procedure defined in XDL file.")

        self.hardware = Hardware([xml_to_component(c) for c in xdl_elems["hardware"]])
        self.reagents = [xml_to_reagent(r) for r in xdl_elems["reagents"]]
        self.metadata = metadata_from_xdl(xdl_str)

        constructor_parameters = {p.id: p for p in self.parameters}
        self.parameters = [xml_to_parameter(p) for p in xdl_elems["parameters"]]

        # overwrite parameter value
        for param in self.parameters:
            if param.id in constructor_parameters:
                param.value = constructor_parameters[param.id].value

        # or create new parameter
        for param in constructor_parameters:
            if param not in [p.id for p in self.parameters]:
                self.parameters.append(constructor_parameters[param])

        self.variables = [
            self.platform.variable_library[v.tag](**v.attrib)
            for v in xdl_elems["variables"]
        ]
        blueprint_classes = [
            xml_to_blueprint(
                xml_blueprint_element=bp,
                context=self.context,
                step_type_dict=self.context.platform.step_library,
            )
            for bp in xdl_elems["blueprints"]
        ]

        # ensure no duplicate blueprint names
        bp_counts = Counter([bp.id for bp in blueprint_classes])
        for bp_id, count in bp_counts.items():
            if count > 1:
                raise XDLAttrDuplicateID(id=bp_id, target_class="Blueprint")

        self.blueprints = {bp.id: bp for bp in blueprint_classes}

        self.procedure_attrs = synthesis_attrs_from_xdl(xdl_str)

        steps = steps_from_xml(
            procedure=xdl_elems["procedures"][0],
            context=self.context,
            blueprints=self.blueprints,
            parameters=self.parameters,
        )

        step_record = get_full_step_record(xdl_elems["procedures"][0])

        # Loading xdlexe if graph_sha256 in synthesis_attrs
        if "graph_sha256" in self.procedure_attrs:
            self.graph_sha256 = self.procedure_attrs["graph_sha256"]
            if len(steps["no_section"]) != len(step_record):
                raise AssertionError  # TODO: raise more specific exception
            for i, step in enumerate(steps["no_section"]):
                step.logger.info(
                    "Following the XDL2 release, use of xdlexe containing"
                    " Repeat steps is no longer supported (Repeat execution is"
                    " now dynamic). However, backwards compatability is still"
                    " maintained."
                )
                apply_step_record(step, step_record[i])

        self.steps, self.sections = steps_into_sections(steps)

    def _load_graph_hash(self, xdl_str: str) -> str | None:
        """Obtain graph hash from given xdl string. If xdl string is not xdlexe,
        there will be no graph hash so return ``None``.
        """
        graph_hash_search = re.search(r'graph_sha256="([a-z0-9]+)"', xdl_str)
        if graph_hash_search:
            self.graph_sha256 = graph_hash_search[1]

    def _validate_loaded_xdl(self):
        """Validate loaded XDL at end of ``__init__``

        Validate that all vessels and reagents used in procedure are declared
        in corresponding sections of XDL.

        Raises:
            XDLReagentNotDeclaredError: If reagent used in step but not declared
            XDLVesselNotDeclaredError: If vessel used in step but not declared
        """
        # Validate all vessels and reagents used in procedure are declared in
        # corresponding sections of XDL. Don't do this if XDL object is compiled
        # (xdlexe) as there will be lots of undeclared vessels from the graph.
        if not self.compiled:

            reagent_ids = [reagent.id for reagent in self.reagents]
            vessel_ids = [vessel.id for vessel in self.hardware]
            parameter_ids = (
                [param.id for param in self.parameters] if self.parameters else []
            )

            # make sure no IDs are duplicated across different sections
            all_ids = [*reagent_ids, *vessel_ids, *parameter_ids]
            # print(self.reagents[0].name)
            # print(all_ids)
            if sorted(set(all_ids)) != sorted(all_ids):
                duplicates = {i for i in all_ids if all_ids.count(i) > 1}
                raise XDLAttrDuplicateID(
                    id=str(duplicates), target_class="Reagents, Hardware and Parameter"
                )

            for step in self.steps:
                self._validate_vessel_and_reagent_props_step(
                    step=step, reagent_ids=reagent_ids, vessel_ids=vessel_ids
                )

    def _validate_vessel_and_reagent_props_step(self, step, reagent_ids, vessel_ids):
        """Validate that all vessels and reagents used in given step are
        declared in corresponding sections of XDL.

        Args:
            step (Step): Step to validate all vessels and reagents declared.
            reagent_ids (List[str]): List of all declared reagent ids.
            vessel_ids (List[str]): List of all declared vessel ids.

        Raises:
            XDLReagentNotDeclaredError: If reagent used in step but not declared
            XDLVesselNotDeclaredError: If vessel used in step but not declared
        """
        for prop, prop_type in step.PROP_TYPES.items():
            # Check vessel has been declared
            if prop_type == "vessel":
                vessel = step.properties[prop]
                if vessel and vessel not in vessel_ids:
                    raise XDLVesselNotDeclaredError(vessel)

            # Check reagent has been declared
            elif prop_type == "reagent":
                reagent = step.properties[prop]
                if reagent and reagent not in reagent_ids:
                    raise XDLReagentNotDeclaredError(reagent)

        # Check child steps, don't need to check substeps as they aren't
        # obligated to have all vessels used explicitly declared.
        if hasattr(step, "children"):
            for substep in step.children:
                self._validate_vessel_and_reagent_props_step(
                    substep, reagent_ids, vessel_ids
                )

    ###############
    # Information #
    ###############

    def human_readable(self, language="en") -> str:
        """Return human-readable English description of XDL procedure.

        Arguments:
            language (str): Language code corresponding to language that should
                be used. If language code not supported error message will be
                logged and no human_readable text will be logged.

        Returns:
            str: Human readable description of procedure.
        """
        s = ""
        # Get available languages
        available_languages = get_available_languages(self.platform.localisation)

        # Print human readable for every step.
        if language in available_languages:
            for i, step in enumerate(self.steps):
                s += f"{i+1}) {step.human_readable(language=language)}\n"

        # Language unavailable, raise error
        else:
            raise XDLLanguageUnavailableError(language, available_languages)

        return s

    def duration(self, fmt=False) -> int | str:
        """Estimated duration of procedure. It is approximate but should give a
        give a rough idea how long the procedure should take.

        Returns:
            int: Estimated runtime of procedure in seconds.
        """
        # If not compiled, raise error
        if not self.compiled:
            raise XDLDurationBeforeCompilationError()

        # Calculate duration
        duration = FTNDuration(0, 0, 0)
        for step in self.steps:
            duration += step.duration(self.executor._graph)

        # Return formatted time string
        if fmt:
            min_duration = datetime.timedelta(seconds=duration.min)
            most_likely_duration = datetime.timedelta(seconds=duration.most_likely)
            max_duration = datetime.timedelta(seconds=duration.max)
            return tabulate.tabulate(
                [
                    ["Min duration", min_duration],
                    ["Estimated duration", most_likely_duration],
                    ["Max duration", max_duration],
                ],
                tablefmt="plain",
            )

        # Return duration in seconds
        return duration

    def reagent_volumes(self, fmt=False) -> dict[str, float]:
        """Compute volumes used of all liquid reagents in procedure and return
        as dict.

        Returns:
            Dict[str, float]: Dict of ``{ reagent_name: volume_used... }``
        """
        # Not compiled, raise error
        if not self.compiled:
            raise XDLReagentVolumesBeforeCompilationError()

        # Calculate volume of liquid reagents consumed by procedure
        reagents_consumed = {}

        for step in self.steps:
            step_reagents_consumed = step.reagents_consumed(self.executor._graph)
            for reagent, volume in step_reagents_consumed.items():
                if volume:
                    if reagent in reagents_consumed:
                        reagents_consumed[reagent] += volume
                    else:
                        reagents_consumed[reagent] = volume

        # Return pretty printed table str
        if fmt:
            return reagent_volumes_table(reagents_consumed)

        # Return Dict[str, float] of reagent volumes consumed by procedure.
        return reagents_consumed

    @property
    def base_steps(self) -> list[AbstractBaseStep]:
        """List of base steps of XDL procedure.

        Returns:
            List[AbstractBaseStep]: List of base steps of XDL procedure.
        """
        base_steps = []
        for step in self.steps:
            base_steps.extend(step.base_steps)
        return base_steps

    @property
    def vessel_specs(self) -> dict[str, VesselSpec]:
        """Get specification of every vessel in procedure."""
        vessel_specs = {}
        for step in self.steps:
            for prop, spec in step.vessel_specs.items():
                vessel = step.properties[prop]
                if vessel in vessel_specs:
                    vessel_specs[vessel] += spec
                else:
                    vessel_specs[vessel] = spec
        return vessel_specs

    #########
    # Tools #
    #########

    def scale_procedure(self, scale: float) -> None:
        """Scale all volumes and masses in procedure.

        Args:
            scale (float): Number to scale all volumes and masses by.
        """
        for step in self.steps:
            step.scale(scale)

    def graph(self, graph_template=None, save=None, **kwargs):
        """Return graph to run procedure with, built on template.

        Returns:
            Dict: JSON node link graph as dictionary.
        """
        return self.platform.graph(self, template=graph_template, save=save, **kwargs)

    def prepare_for_execution(
        self,
        graph_file: str = None,
        interactive: bool = True,
        save_path: str = None,
        sanity_check: bool = True,
        equiv_reference: str = None,
        equiv_amount: str = None,
        **kwargs,
    ) -> None:
        """Check hardware compatibility and prepare XDL for execution on given
        setup.

        Args:
            graph_file (str, optional): Path to graph file. May be GraphML file,
                JSON file with graph in node link format, or dict containing
                graph in same format as JSON file.
            interactive (bool, optional): Ask the user for input on step
                information. Defaults to True.
            save_path (str, optional): filepath to location where compiled
                procedure (.xdlexe) should be saved.
            sanity_check (bool): If true, will run sanity checks on Steps and
                check that their attributes are valid. Defaults to True.
            equiv_reference (str, optional): reagent to act as a reference
                when calculating equivalents.
            equiv_amount (str, optional): amount of reference reagent equal to
                one equivalent (including units) e.g "2.0 g".
                Valid units include mol, g, mL.
        """

        # Not already compiled, try to compile procedure.
        if not self.compiled:

            # Get XDLEXE save path from name of _xdl_file used to instantiate
            # XDL object.
            if self._xdl_file:
                save_path = self._xdl_file.replace(".xdl", ".xdlexe")

            if (equiv_amount and not equiv_reference) or (
                not equiv_amount and equiv_reference
            ):
                raise XDLInvalidEquivalentsInput(equiv_amount, equiv_reference)

            #  equiv_reference must be in reagents
            if equiv_reference and equiv_reference not in [
                r.name for r in self.reagents
            ]:
                raise XDLEquivReferenceNotInReagents(self.reagents, equiv_reference)

            # update context with equivalence amount and reference, if supplied
            if equiv_amount and equiv_reference:
                self.context.update(
                    equiv_reference=equiv_reference,
                    equiv_amount=equiv_amount,
                    reagents=self.reagents,
                )

            # Compile procedure
            self.executor.prepare_for_execution(
                graph_file, interactive=interactive, sanity_check=sanity_check, **kwargs
            )

            # Save XDLEXE, switch self.compiled flag to True, and log reagent
            # volumes consumed by procedure and estimated duration.
            if self.executor._prepared_for_execution:

                # Save XDLEXE
                self.graph_sha256 = self.executor._graph_hash()
                if save_path and self.write_xexe:
                    xdlexe = xdl_to_xml_string(
                        self,
                        graph_hash=self.graph_sha256,
                        full_properties=True,
                        full_tree=True,
                    )
                    with open(save_path, "w") as fd:
                        fd.write(xdlexe)

                # Switch self.compiled flag to True and log procedure info
                self.compiled = True
                self.logger.info(
                    f"Reagents Consumed\n{self.reagent_volumes(fmt=True)}\n"
                )

                # for step in self.steps:
                #     step.context.update(parent_context=self.context)

        else:
            raise XDLDoubleCompilationError()

    def _lookup_blueprint(self, blueprint_id: str) -> Blueprint:
        """Lookup Blueprint object from str id.

        Args:
            blueprint_id (str): id for target Blueprint object.

        Returns:
            Blueprint: Blueprint object.
        """
        for blueprint in self.blueprints:
            if blueprint.id == blueprint_id:
                return blueprint

    def execute(
        self,
        platform_controller: Any,
        step: int = None,
        interactive: bool = True,
        tracer: list[tuple[type, dict]] = None,
        block: bool | None = True,
    ) -> None:
        """Execute XDL using given platform controller object.
        XDL object must either be loaded from a xdlexe file, or it must have
        been prepared for execution.

        Args:
            platform_controller (Any): Platform controller object instantiated
            with modules and graph to run XDL on.
            step (int): index of XDL Step (from XDL.steps) to execute.
            interactive (bool, optional): Ask the user for input on step
                information. Defaults to True.
            tracer ([List]): List to record executed Steps and their
                properties at the point of execution.
            lock_controller (bool): If True, platform controller will be locked
                throughout duration of XDL execution (will not allow multiple
                XDL objects to use the same hardware / platform_controller
                object at the same time).
        """
        self.tracer = tracer if tracer is not None else []
        self.task_groups = collections.defaultdict(list)
        # need to patch asyncio so we can run nested loops
        nest_asyncio.apply()

        if block:
            run = self._loop.run_until_complete
        else:
            run = self._loop.create_task

        # Check step not accidentally passed as platform controller
        if type(platform_controller) in [int, str, list, dict]:
            raise XDLInvalidPlatformControllerError(platform_controller)

        # Check XDL object has been compiled
        if self.compiled:
            # Execute full procedure
            if step is None:
                # self.task = run(
                self.executor.execute(
                    platform_controller,
                    # interactive,
                    # tracer=self.tracer,
                )
            # )

            # Execute individual step.
            else:
                # Step index given
                if type(step) == int:
                    step_index = step

                    # Check step index is valid.
                    try:
                        step = self.steps[step_index]
                    except IndexError:
                        raise XDLStepIndexError(step_index, len(self.steps))

                # Step object given.
                elif isinstance(step, Step):
                    try:
                        step_index = self.steps.index(step)
                    except ValueError:
                        raise XDLStepNotInStepsListError(step)

                # Execute step, empty locks and dependencies as executing one
                # step at a time
                self.task = run(
                    step.execute_step(
                        platform_controller=platform_controller,
                        locks={},
                        step_indexes=[step_index],
                        tracer=self.tracer,
                    )
                )

        # XDL object not compiled, raise error
        else:
            raise XDLExecutionBeforeCompilationError()

    ##########
    # Output #
    ##########

    def as_string(self) -> str:
        """Return XDL str of procedure."""
        return xdl_to_xml_string(self)

    def as_json(self) -> dict:
        """Return JSON dict of procedure."""
        return xdl_to_json(self)

    def as_json_string(self, pretty=True) -> str:
        """Return JSON str of procedure."""
        xdl_json = xdl_to_json(self)
        if pretty:
            return json.dumps(xdl_json, indent=2)
        return json.dumps(xdl_json)

    def save(self, save_file: str, file_format: str = "xml") -> str:
        """Save as XDL file.

        Args:
            save_file (str): File path to save XDL to.
            full_properties (bool): If True, all properties will be included.
                If False, only properties that differ from their default values
                will be included.
                Including full properties is recommended for making XDL files
                that will stand the test of time, as defaults may change in new
                versions of XDL.
        """
        # Save XML
        if file_format == "xml":
            xml_string = xdl_to_xml_string(self)
            with open(save_file, "w") as fd:
                fd.write(xml_string)

        # Save JSON
        elif file_format == "json":
            with open(save_file, "w") as fd:
                json.dump(xdl_to_json(self), fd, indent=2)

        # Invalid file format given, raise error
        else:
            raise XDLInvalidSaveFormatError(file_format)

    #################
    # Magic Methods #
    #################

    def __setattr__(self, name: str, value: Any):
        """Overwrite of setattr for XDL object to ensure that certain attrs
        (listed in `CORE_CONTEXT_ATTRS`) are always kept up-to-date in context.
        This way there is no need to worry about continuously updating context
        for these attrs.

        Args:
            name (str): attr.
            value (Any): value for attribute.
        """

        #  set the attribute as normal - both for core context attrs and
        #  regularattrs
        object.__setattr__(self, name, value)

        #  update context if attr is one of the core context attributes
        if name in CORE_CONTEXT_ATTRS:
            self.context.update(**{name: value})

    def __str__(self):
        return self.as_string()

    def __add__(self, other: XDL) -> XDL:
        """Allow two XDL objects to be added together. Steps, reagents and
        components of this object are added to the new object lists first,
        followed by the same lists of the other object.

        The final XDL reagents and components will be a set of the two original
        XDL objects.
        """
        # Two platforms do not match, raise error
        if type(self.platform) != type(other.platform):  # noqa: E721
            raise XDLPlatformMismatchError

        reagents, steps, components, parameters = [], [], [], []
        for xdl_obj in [self, other]:
            reagents.extend(xdl_obj.reagents)
            steps.extend(xdl_obj.steps)
            components.extend(list(xdl_obj.hardware))
            parameters.extend(xdl_obj.parameters)

        reagents = list(set(reagents))
        components = list(set(components))
        parameters = list(set(parameters))

        # Adding 2 XDL objects together should have the same platform
        # so just use the __class__ of the current instance
        new_xdl_obj = XDL(
            steps=steps,
            reagents=reagents,
            hardware=components,
            parameters=parameters,
            platform=self.platform.__class__,
        )
        return new_xdl_obj

    def __eq__(self, other: XDL) -> bool:
        """Compare equality of XDL objects based on steps, reagents and
        hardware. Steps are compared based step types and properties, including
        all substeps and child steps. Reagents and Components are compared
        based on properties.
        """
        if type(other) != XDL:
            # Don't raise NotImplementedError here as it causes unnecessary
            # crashes for example `if xdl_obj == None: ...`.
            return False

        # Compare lengths of lists first.
        if len(self.steps) != len(other.steps):
            return False
        if len(self.reagents) != len(other.reagents):
            return False
        if len(self.hardware.components) != len(other.hardware.components):
            return False

        # Detailed comparison of all step types and properties, including all
        # substeps and children.
        for i, step in enumerate(self.steps):
            if not steps_are_equal(step, other.steps[i]):
                return False

        # Compare properties of all reagents
        for i, reagent in enumerate(self.reagents):
            if not xdl_elements_are_equal(reagent, other.reagents[i]):
                return False

        # Compare properties of all components
        for i, component in enumerate(self.hardware.components):
            if not xdl_elements_are_equal(component, other.hardware.components[i]):
                return False

        return True
