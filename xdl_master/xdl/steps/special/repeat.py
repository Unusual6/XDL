from __future__ import annotations

import asyncio
import itertools
import logging
from typing import Any, Generator, List, Union

from networkx import MultiDiGraph

from xdl_master.xdl.blueprints import Blueprint
from xdl_master.xdl.constants import DONE
from xdl_master.xdl.errors import (
    XDLAttrDuplicateID,
    XDLError,
    XDLReagentNotDeclaredError,
    XDLVesselNotDeclaredError,
)
from xdl_master.xdl.hardware import Component
from xdl_master.xdl.reagents import Reagent
from xdl_master.xdl.steps import (
    AbstractAsyncStep,
    AbstractBaseStep,
    AbstractDynamicStep,
    AbstractStep,
    Step,
)
from xdl_master.xdl.steps.special.mock_measure import MockMeasure
from xdl_master.xdl.steps.special.monitor import AbstractMonitorStep
from xdl_master.xdl.utils.logging import get_logger
from xdl_master.xdl.utils.misc import SanityCheck
from xdl_master.xdl.utils.steps import steps_from_step_templates

# Steps that don't contain step.steps
NON_RECURSIVE_ABSTRACT_STEPS: list[type] = (
    AbstractBaseStep,
    AbstractDynamicStep,
    AbstractAsyncStep,
)


class Repeat(AbstractStep):
    """Repeat children of this step ``self.repeats`` times.

    Args:
        repeats (int): Number of times to repeat children.
        children (List[Step]): Child steps to repeat.
        loop_variables (Dict[str, Tuple[str, str]]): dictionary of variables
            to be matched to specific values during execution. Key is string of
            of variable to be matched, value is tuple of
            (Reagent or Component attribute, value to match to attribute).
        iterative (bool): if true, will iterate through matches for general
            variables and execute all children of Repeat with those variables.
    """

    PROP_TYPES = {
        "repeats": int,
        "children": Union[Step, List[Step]],
    }

    DEFAULT_PROPS = {
        "repeats": None,
    }

    INTERNAL_PROPS = []

    def __init__(
        self, children: Step | list[Step], repeats: int | None = "default", **kwargs
    ) -> None:
        super().__init__(locals())
        if not children:
            raise XDLError("Repeat: No children specified.")
        if type(children) != list:
            self.children = [children]

        self.loop_variables, self.bindings = self.parse_loop_variables(kwargs)

        # update XDL object to not write xdlexe during prepare for execution
        if self.loop_variables:
            self.context.root_context.xdl().write_xexe = False

        self.prep_functions = []

    def locks(self, platform_controller: Any) -> list:
        """Returns locks that are nodes that are used while the step is executing.

        Args:
            platform_controller (Any): Platform controller to use for
                calculating which nodes in graph are used by step.

        Returns:
            List: List of step locks.
        """
        return []

    def parse_loop_variables(self, attrs: dict[str, str]) -> dict[str, Any]:
        """Parses loop variables of format:
            loop_variable.specification = specification_value

        Finds Reagent or Component object that matches the specification and
        specification value for each loop variable and stores all loop variable
        matches in a dictionary.

        Args:
            attrs (dict[str, str]): Repeat step attributes from
                step declaration.

        Raises:
            XDLAttrDuplicateID: Raises an error if the loop variable name is
                not unique (is also used for id of Reagent, Component or
                Parameter).

        Returns:
            Dict[str, Any]: Dictionary of loop variables and their matched
                Reagent or Component objects.
        """
        loop_variables = {}
        bindings = {}
        for attr, val in attrs.items():
            if "." not in attr:
                if isinstance(val, str):
                    bindings[attr] = val
                continue
            # account for 'param.' prefix
            arg, spec = attr.split(".")

            if spec in {
                **Reagent.PROP_TYPES,
                **Component.PROP_TYPES,
                "type": str,
                "kind": str,
                "comment": str,
            }:
                # TODO: These need to be resolved syntactically,
                # i.e. from context.xdl()
                reagent_ids = [r.name for r in self.context.reagents]
                component_ids = [c.id for c in self.context.hardware]
                parameter_ids = [p.id for p in self.context.parameters]

                all_ids = [*reagent_ids, *parameter_ids, *component_ids]

                if arg in all_ids:
                    raise XDLAttrDuplicateID(
                        arg,
                        f"{arg} used as a general \
variable in Repeat but also found as an id in Reagents, Parameters or Hardware.\
 Loop variable",
                    )
                if arg in loop_variables:
                    loop_variables[arg].append((spec, val))
                else:
                    loop_variables[arg] = [(spec, val)]

        return loop_variables, bindings

    def sanity_checks(self, graph: MultiDiGraph) -> list[SanityCheck]:
        """Gets a list of Sanity checks to perform for the step

        Args:
            graph (MultiDiGraph): Chemputer graph to check

        Returns:
            List[SanityCheck]: List of checks to perform
        """
        uses_measure = any(
            [
                isinstance(step, MockMeasure) or isinstance(step, AbstractMonitorStep)
                for step in self.steps
            ]
        )

        return [
            SanityCheck(
                condition=not (self.repeats and self.loop_variables),
                error_msg="Repeat step cannot have both repeats and general \
variables.",
            ),
            SanityCheck(
                condition=not (uses_measure and self.repeats),
                error_msg="Repeat step cannot have both repeats and a \
measurement.",
            ),
            SanityCheck(
                condition=not (uses_measure and self.loop_variables),
                error_msg="Repeat step cannot have both loop variables and a\
 measurement.",
            ),
        ]

    async def execute(
        self,
        platform_controller,
        logger: logging.Logger = None,
        level: int = 0,
        step_indexes: list[int] = None,
        tracer: list[tuple[type, dict]] = None,
    ) -> bool:
        """Execute self with given platform controller object.

        Args:
            platform_controller (platform_controller): Initialised platform
                controller object.
            logger (logging.Logger): Logger to handle output step output.
            level (int): Level of recursion in step execution.
            step_indexes (List[int]): Indexes into steps list and substeps
                lists.
            tracer (List[(str, Dict)]): Tracer with all steps that have been
                executed and their properties at execution time.
                Defaults to None.

        Returns:
            bool: ``True`` if execution should continue, ``False`` if execution
            should stop.
        """
        if logger is None:
            logger = get_logger()

        # Get default step indexes if they are not passed
        step_indexes = step_indexes if step_indexes is not None else [0]

        # Break down steps into batches of size len(self.children)
        batch_size = len(self.children)
        steps = self.get_steps(truncate=False)
        batches = itertools.zip_longest(*([steps] * batch_size))

        # Bump recursion level
        level += 1

        # Add a placeholder for the next batch
        step_indexes = step_indexes[:]
        step_indexes.append(0)  # batch idx
        step_indexes.append(0)  # step idx

        for batch_idx, step_batch in enumerate(batches):
            batch_ids = [id(step) for step in step_batch]
            # Add a placeholder for the next index so that it can be assigned to
            # using `step_indexes[level]`
            batch_indexes = step_indexes[:]  # needed?
            batch_indexes[level] = batch_idx

            monitor_step_count = 0

            # schedule steps
            for step_idx, step in enumerate(step_batch):
                if isinstance(step, (AbstractMonitorStep, MockMeasure)):
                    monitor_step_count += 1
                if not isinstance(step, Repeat):
                    step.final_sanity_check(graph=platform_controller.graph)

                # Update step indexes for current sub step
                substep_indexes = batch_indexes[:]
                substep_indexes[level + 1] = step_idx

                deps = step.get_deps(self.task_groups)
                step_locks = step.locks(platform_controller)

                task = asyncio.create_task(
                    step.execute_step(
                        platform_controller=platform_controller,
                        deps=deps,
                        locks=step_locks,
                        tracer=tracer,
                        step_indexes=substep_indexes,
                        level=level + 1,
                    )
                    # name=step.name  # python >= 3.8
                )

                self.task_groups[step.queue].append((step, task))

            # Await steps in this current batch immediately if Monitor step
            # within steps (a continuous loop)
            if monitor_step_count:
                all_tasks = itertools.chain(*self.task_groups.values())
                all_steps, all_tasks = zip(
                    *[(step, task) for step, task in all_tasks if id(step) in batch_ids]
                )
                monitor_done_count = 0

                for t in asyncio.as_completed(all_tasks):
                    keep_going = await t

                    if not keep_going:
                        # If keep_going is False break execution. This is used
                        # by the Confirm step to stop execution if the user
                        # doesn't wish to continue.
                        return False

                    if keep_going == DONE:
                        # Monitor steps return DONE, if condition was met
                        monitor_done_count += 1

                # only exit loop if all Monitor steps are DONE
                if monitor_done_count == monitor_step_count:
                    return True

        # await all scheduled steps
        if self.task_groups:
            all_steps, all_tasks = zip(*itertools.chain(*self.task_groups.values()))
            for t in asyncio.as_completed(all_tasks):
                keep_going = await t

                if not keep_going:
                    # If keep_going is False break execution. This is used by
                    # the Confirm step to stop execution if the user doesn't
                    # wish to continue.
                    return False

        # Return `keep_going` flag as `True`.
        return True

    def iter_bindings(self) -> Generator[list[Step]]:
        """Generates batches of substeps to be executed.

        If repeats are static (an integer), the number of batches will be
        the repeat number (n) and each batch will contain the Repeat children
        (the repeat children will be executed n times).

        If repeat is iterative (repeats = 0 but loop variables specified), it
        will generate a batch for each set of loop variable matches.

        Returns:
            generator: yields batch of Steps.
        """
        if self.repeats is not None:
            loop_counter = range(self.repeats)
        else:
            loop_counter = itertools.count()

        # counter is used by MockMeasure steps to keep track of how many times
        # the MockMeasure step has been executed (can be used for Monitor steps
        # in the same way).
        matched_variables = [(("_counter", i) for i in loop_counter)]

        for attr, val in self.bindings.items():
            matched_variables.append(itertools.repeat((attr, val)))

        # resolve any loop_variables from current Reagents and Components
        for v, specs in self.loop_variables.items():

            all_matches = []

            for spec in specs:
                prop, val = spec

                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False

                if val in ["Hardware", "Reagent"]:
                    if prop == "kind":
                        if val == "Hardware":
                            matches = [r.id for r in self.context.hardware]
                            self.logger.info(
                                f"All hardware matched during \
iterative Repeat for variable {v}"
                            )

                        elif val == "Reagent":
                            matches = [r.name for r in self.context.reagents]
                            self.logger.info(
                                f"All reagents matched during \
iterative repeat for variable {v}"
                            )

                        else:
                            raise XDLError(
                                f"{val} was used as a loop variable \
alongside 'kind', only 'Hardware' or 'Reagent' can be used alongside kind to \
iterate over all Hardware or Reagent objects respectively."
                            )
                    else:
                        raise XDLError(
                            f"{val} was used as a loop variable \
alongside 'Hardware' or 'Reagent'. 'kind' must be used to iterate over all \
Hardware or Reagent objects respectively."
                        )

                elif prop in Reagent.PROP_TYPES:

                    # match blueprint reagents from original Reagent properties
                    # (those present in blueprint)
                    bp_ref = self.context.xdl()
                    if isinstance(bp_ref, Blueprint):
                        unmapped_matches = [
                            r.id
                            for r in bp_ref.reagent_templates
                            if (r.properties[prop] == val)
                        ]
                        matches = [
                            bp_ref.init_props[m]
                            for m in unmapped_matches
                            if (m in bp_ref.init_props)
                        ]
                    else:
                        matches = [
                            r.name
                            for r in self.context.reagents
                            if (r.properties[prop] == val)
                        ]

                elif prop in {*Component.PROP_TYPES, "type", "comment"}:

                    if prop == "type":
                        prop = "component_type"

                    # match blueprint components from original
                    # Component properties (those present in blueprint)
                    bp_ref = self.context.xdl()
                    if isinstance(bp_ref, Blueprint):
                        unmapped_matches = [
                            h.id
                            for h in bp_ref.hardware_templates
                            if (h.properties[prop] == val)
                        ]
                        matches = [
                            bp_ref.init_props[m]
                            for m in unmapped_matches
                            if (m in bp_ref.init_props)
                        ]
                    else:
                        matches = [
                            c.id
                            for c in self.context.hardware
                            if (c.properties[prop] == val)
                        ]

                if all_matches and matches:
                    all_matches = [m for m in all_matches if m in matches]
                else:
                    all_matches.extend(matches)

            if all_matches:
                matched_variables.append([(v, m) for m in all_matches])

            # if no matches for loop variables, don't execute any child steps
            elif not all_matches and self.loop_variables:
                formatted_gv = [
                    f"{g} ({s[0]} = {s[1]})" for g, s in (self.loop_variables.items())
                ]
                self.logger.warning(f"No matches for loop variables: {formatted_gv}")
                return ()

        return (dict(m) for m in zip(*matched_variables))

    def get_steps(self, truncate=True) -> Generator[Step, None, None]:
        """For steps with children, their steps are instantiated as 'Step'
        objects and need to be converted from step templates to steps.

        Repeat iterates through bindings (loop variable matches) and yields
        steps in batches.

        If truncate = True, it will not iterate - this is to stop infinite loop
        expansion.

        Prep functions are applied to steps (steps are prepared for execution)
        before yielding them.
        """
        for matches in self.iter_bindings():
            # steps created by Python have no context
            self.context.update(_counter=matches.pop("_counter"))

            step_batch = steps_from_step_templates(
                self,
                self.children,
                bindings=matches,
            )

            for step in step_batch:
                for function, graph in self.prep_functions:
                    step.register_prep_function(function, graph)
            yield from step_batch

            # if one these is specified the loop is finite
            # therefore safe to fully expand
            if self.loop_variables:
                continue
            elif truncate:
                break

    def human_readable(self, language="en"):

        repeats = ""

        if self.repeats:
            repeats = f"{self.repeats} times"

        if self.loop_variables:
            formatted_gv = [
                f"{clause[0]} = {clause[1]}"
                for lv in self.loop_variables.values()
                for clause in lv
            ]
            repeats = f"whilst iterating over {', '.join(formatted_gv)}"

        monitoring = any(
            [isinstance(s, (AbstractMonitorStep, MockMeasure)) for s in self.steps]
        )

        if monitoring:
            repeats = repeats + " until done"

        human_readable = f"Repeat {repeats}:\n"
        for step in self.steps:
            human_readable += f"    {step.human_readable()}\n"
        return human_readable

    def _validate_vessel_and_reagent_props_step(self, step, reagent_ids, vessel_ids):
        """Validate that all vessels and reagents used in Repeat are
        declared in corresponding sections of XDL.

        Args:
            step (Step): Step to validate all vessels and reagents declared.
            reagent_ids (List[str]): List of all declared reagent ids.
            vessel_ids (List[str]): List of all declared vessel ids.

        Raises:
            XDLReagentNotDeclaredError: If reagent used in step but not declared
            XDLVesselNotDeclaredError: If vessel used in step but not declared
        """

        if step.loop_variables:
            reagent_ids = [*reagent_ids, *list(step.loop_variables.keys())]
            vessel_ids = [*vessel_ids, *list(step.loop_variables.keys())]

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
                substep._validate_vessel_and_reagent_props_step(
                    step=substep, reagent_ids=reagent_ids, vessel_ids=vessel_ids
                )

    def final_sanity_check(self, graph: MultiDiGraph) -> None:
        """Run all ``SanityCheck`` objects returned by ``sanity_checks``. Can be
        extended if necessary but ``super().final_sanity_check()`` should always
        be called.
        """
        for sanity_check in self.sanity_checks(graph):
            sanity_check.run(self)

    def register_prep_function(self, function, graph):
        """Registration of function to be called to prepare the step for execution.

        if loop_variables (variables that need to be resolved just before
        execution), store the function until execution.
        """
        self.prep_functions.append((function, graph))

    def scale(self, scale: float) -> None:
        """Defers scaling by registering as prep function.

        Args:
            scale (float): Scale factor to scale substeps by.
        """
        self.register_prep_function(lambda graph, step: step.scale(scale), None)

    def reagents_consumed(self, graph: MultiDiGraph) -> dict[str, float]:
        """Return dictionary of reagents and volumes consumed in mL like this:
        ``{ reagent: volume... }`` if reagent is present in Reagents section
        of XDL (retrieved via context).

        Will not return reagents consumed of iterative / general reagents.

        Args:
            graph (MultiDiGraph): Graph to use when calculating volumes of
                reagents consumed by step.

        Returns:
            Dict[str, float]: Dict of reagents volumes consumed by step in
            format ``{reagent_id: reagent_volume...}``.
        """
        reagents_consumed = {}

        for step in self.steps:

            try:
                consumed = step.reagents_consumed(graph=graph)

            # for reagents that are determined during execution
            # (loop_variable)
            except (KeyError, TypeError):
                consumed = {}

            for reagent, volume in consumed.items():

                if self.loop_variables:
                    if reagent in [r.name for r in self.context.reagents]:
                        if reagent in reagents_consumed:
                            reagents_consumed[reagent] += volume
                        else:
                            reagents_consumed[reagent] = volume

                else:
                    # show one iteration if continuous loop
                    repeats = self.repeats if self.repeats is not None else 1
                    if reagent in reagents_consumed:
                        reagents_consumed[reagent] += volume * repeats
                    else:
                        reagents_consumed[reagent] = volume * repeats

        return reagents_consumed
