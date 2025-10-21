from __future__ import annotations

import asyncio
import contextlib
import copy
import inspect
import uuid
from itertools import chain
from typing import Any

import termcolor
from networkx import MultiDiGraph

from xdl_master.xdl.context import Context
from xdl_master.xdl.errors import (
    XDLReagentNotDeclaredError,
    XDLUndeclaredAlwaysWriteError,
    XDLUndeclaredDefaultPropError,
    XDLUndeclaredInternalPropError,
    XDLUndeclaredPropLimitError,
    XDLVesselNotDeclaredError,
)
from xdl_master.xdl.localisation import LOCALISATIONS
from xdl_master.xdl.steps.logging import (
    finished_executing_step_msg,
    start_executing_step_msg,
)
from xdl_master.xdl.steps.utils import FTNDuration, pretty_props_table
from xdl_master.xdl.utils import XDLBase
from xdl_master.xdl.utils.localisation import conditional_human_readable
from xdl_master.xdl.utils.logging import log_duration
from xdl_master.xdl.utils.misc import SanityCheck, format_property
from xdl_master.xdl.utils.tracer import update_tracer
from xdl_master.xdl.utils.vessels import VesselSpec


class Step(XDLBase):
    """Base class for all step objects.

    Attributes:
        properties (dict): Dictionary of step properties. Should be implemented
            in step ``__init__`` method.
        uuid (str): Step unique universal identifier, generated automatically.
        localisation: Dict[str, str]: Provides localisation for all steps
            specified by the XDL cross platform templates. Can be overridden if
            localisation needed for other steps or steps do not conform to cross
            platform standard.

    Args:
        param_dict (Dict[str, Any]): Step properties dict to initialize step
            with.
    """

    # This provides localisation for all steps specified by the XDL cross
    # platform templates. Can be overridden if localisation needed for other
    # steps or steps do not conform to cross platform standard.
    localisation: dict[str, str] = LOCALISATIONS

    def __init__(
        self,
        param_dict: dict[str, Any],
    ) -> None:
        if "kwargs" in param_dict:
            self.init_props = {**param_dict.pop("kwargs"), **param_dict}
        else:
            self.init_props = param_dict

        self.template_name = self.init_props.get("template_name")

        self.uuid = str(uuid.uuid4())

        self.context = (
            self.init_props.pop("context")
            if "context" in self.init_props
            else Context()
        )

        self.parent = None

        # recursively look up stack frames to find the parent Step of the
        # current step (until 'self' is found in stack trace)
        if "parent" in self.init_props:
            self.parent = self.init_props["parent"]
        else:
            frame = inspect.currentframe().f_back
            while frame:
                caller_locals = frame.f_locals
                if "self" not in caller_locals or caller_locals["self"] is self:
                    frame = frame.f_back
                elif isinstance(caller_locals["self"], Step):
                    self.parent = caller_locals["self"]
                    break
                else:
                    break

        self._construct_validate(param_dict=self.init_props)

        # store the queue name that this step belongs to
        self.queue = self.init_props.get("queue", None)

    def _construct_validate(self, param_dict: dict[str, Any]):
        """Validate and sanitise props for step.

        Args:
            param_dict (Dict[str, Any]): dict of step properties.
        """
        super().__init__(param_dict)

        # Validate prop types
        self._validate_prop_types()
        self._validated_prop_types = True

    def _validate_prop_types(self):
        """Make sure that all props specified in ``DEFAULT_PROPS``,
        ``INTERNAL_PROPS``, ``ALWAYS_WRITE`` and ``PROP_LIMITS`` are specified
        in ``PROP_TYPES``.

        Raises:
            XDLUndeclaredDefaultPropError: Prop used in ``DEFAULT_PROPS`` that
                is not in ``PROP_TYPES``.
            XDLUndeclaredInternalPropError: Prop used in ``INTERNAL_PROPS`` that
                is not in ``PROP_TYPES``.
            XDLUndeclaredPropLimitError: Prop used in ``PROP_LIMITS`` that is
                not in ``PROP_TYPES``.
            XDLUndeclaredAlwaysWriteError: Prop used in ``ALWAYS_WRITE`` that is
                not used in ``PROP_TYPES``.
        """
        # Default Props
        for default_prop in self.DEFAULT_PROPS:
            if default_prop not in self.PROP_TYPES:
                raise XDLUndeclaredDefaultPropError(self.name, default_prop)

        # Internal Props
        for internal_prop in self.INTERNAL_PROPS:
            if internal_prop not in self.PROP_TYPES:
                raise XDLUndeclaredInternalPropError(self.name, internal_prop)

        # Prop Limits
        for prop_limit in self.PROP_LIMITS:
            if prop_limit not in self.PROP_TYPES:
                raise XDLUndeclaredPropLimitError(self.name, prop_limit)

        # Always Write
        for always_write in self.ALWAYS_WRITE:
            if always_write not in self.PROP_TYPES:
                raise XDLUndeclaredAlwaysWriteError(self.name, always_write)

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
                    raise XDLVesselNotDeclaredError(step)

            # Check reagent has been declared
            elif prop_type == "reagent":
                reagent = step.properties[prop]
                if reagent and reagent not in reagent_ids:
                    raise XDLReagentNotDeclaredError(step)

        # Check child steps, don't need to check substeps as they aren't
        # obligated to have all vessels used explicitly declared.
        if hasattr(step, "children") and step.context.xdl:
            parent = step.context.xdl()

            # include both reagent id's and default reagent names in list of
            # valid reagent ids
            reagent_ids = [
                *[r.id for r in parent.reagents],
                *[r.name for r in parent.reagents if r.name],
            ]
            vessel_ids = [h.id for h in parent.hardware]

            for substep in step.steps:
                substep._validate_vessel_and_reagent_props_step(
                    step=substep, reagent_ids=reagent_ids, vessel_ids=vessel_ids
                )

    def compile_step(self, graph: MultiDiGraph):
        if not self._compiled:
            self.on_prepare_for_execution(graph)
        self._compiled = True

    def update_step(self, graph: MultiDiGraph):
        self.on_prepare_for_execution(graph)
        self._compiled = True

    def on_prepare_for_execution(self, graph: MultiDiGraph) -> None:
        """Abstract method to be overridden with logic to set internal
        properties during procedure compilation. Doesn't use ``@abstractmethod``
        decorator as it's okay to leave this blank if there are no internal
        properties.

        This method is called during procedure compilation. Sanity checks are
        called after this method, and are there to validate the internal
        properties added during this stage.

        Args:
            graph (MultiDiGraph): networkx MultiDiGraph of graph that procedure
                is compiling to.
        """
        pass

    def register_prep_function(self, function, graph):
        """Registration of function to be called to prepare the step for
        execution.
        """
        function(graph, self)

    def sanity_checks(self, graph: MultiDiGraph) -> list[SanityCheck]:
        """Abstract methods that should return a list of ``SanityCheck`` objects
        to be checked by final_sanity_check. Not compulsory so not using
        ``@abstractmethod`` decorator.
        """
        return []

    def final_sanity_check(self, graph: MultiDiGraph) -> None:
        """Run all ``SanityCheck`` objects returned by ``sanity_checks``. Can be
        extended if necessary but ``super().final_sanity_check()`` should always
        be called.
        """
        for sanity_check in self.sanity_checks(graph):
            sanity_check.run(self)

    def formatted_properties(self) -> dict[str, str]:
        """Return properties as dictionary of ``{ prop: formatted_val }``.
        Used when generating human readables.
        """
        # Copy properties dict
        formatted_props = copy.deepcopy(self.properties)

        # Add formatted properties for all properties
        for prop, val in formatted_props.items():

            # Ignore children
            if prop != "children":
                formatted_props[prop] = format_property(
                    prop,
                    val,
                    self.PROP_TYPES[prop],
                    self.PROP_LIMITS.get(prop, None),
                )

            # Convert None properties to empty string
            if formatted_props[prop] in ["None", None]:
                formatted_props[prop] = ""

        return formatted_props

    def human_readable(self, language: str = "en") -> str:
        """Return human readable sentence describing step.

        Args:
            language (str): Language code for human readable sentence. Defaults
                to ``'en'``.

        Returns:
            str: Human readable sentence describing actions taken by step.
        """
        # Look for step name in localisation dict
        if self.name in self.localisation:

            # Get human readable template from localisation dict
            step_human_readables = self.localisation[self.name]
            if language in step_human_readables:
                language_human_readable = step_human_readables[language]

                # Traditional human readable template strings
                if type(language_human_readable) == str:

                    # If step has a comment add comment to template.
                    if self.comment:
                        language_human_readable += ". {comment}"

                    return (
                        language_human_readable.format(**self.formatted_properties())
                        + "."
                    )

                # New conditional JSON object human readable format
                else:
                    # If step has a comment add comment to template.
                    if self.comment:
                        language_human_readable["full"] += ". {comment}"

                    return conditional_human_readable(self, language_human_readable)

        # Return step name as a fallback if step not in localisation dict
        return self.name

    def reagents_consumed(self, graph: MultiDiGraph) -> dict[str, float]:
        """Method to override if step consumes reagents. Used to recursively
        calculate volume of reagents consumed by procedure.

        Args:
            graph (MultiDiGraph): Graph to use when calculating volume of
                reagents consumed by step.

        Returns:
            Dict[str, float]: Dict of volumes of reagents consumed in format
            ``{ reagent_id: volume_consumedxdl.. }``.
        """
        return {}

    def duration(self, graph: MultiDiGraph) -> FTNDuration:
        """Method to override to give approximate duration of step. Used to
        recursively determine duration of procedure.

        Args:
            graph (MultiDiGraph): Graph to use when calculating step duration.

        Returns:
            FTNDuration: Estimated duration of step in seconds as FTN.
        """
        # Default duration for steps that don't override this method. Duration
        # used is an estimate of the duration of steps that are virtually
        # instantaneous, such as starting stirring.
        return FTNDuration(0.5, 1, 2)

    def locks(self, platform_controller: Any) -> list:
        """Returns locks that are nodes that are used while the step is
        executing.

        Args:
            platform_controller (Any): Platform controller to use for
                calculating which nodes in graph are used by step.

        Returns:
            List: List of step locks.
        """
        return []

    @property
    def name(self) -> str:
        """Get class name."""
        if self.template_name:
            return self.template_name
        return type(self).__name__

    @property
    def vessel_specs(self) -> dict[str, VesselSpec]:
        """Return dictionary of required specifications of vessels used by the
        step. ``{ prop_name: vessel_specxdl.. }``

        Returns:
            Dict[str, VesselSpec]: Dict of required specification of vessels
            used by the step. Should be overridden if the step has any special
            requirement on a vessel used.
        """
        return {}

    @property
    def requirements(self) -> dict:
        """Return dictionary of requirements of vessels used by the step.
        Currently only used bySynthReader. This will soon be deprecated and
        completely replaced by ``vessel_specs``.
        """
        return {}

    @property
    def equiv_reference(self) -> str | None:
        if hasattr(self, "context"):
            if hasattr(self.context, "equiv_reference"):
                return self.context.equiv_reference
        return None

    @property
    def equiv_amount(self) -> str | None:
        if hasattr(self, "context"):
            if hasattr(self.context, "equiv_amount"):
                return self.context.equiv_amount
        return None

    @property
    def base_scale(self) -> str | None:
        if hasattr(self, "context"):
            if hasattr(self.context, "base_scale"):
                return self.context.base_scale
        return None

    def scale(self, scale: float) -> None:
        """If step has children, scales children of step.

        Scales children instead of step.steps as children are used as templates
        to generate Steps at various points during compilation for certain steps
        e.g. Repeat.

        Args:
            scale (float): Scale factor to scale substeps by.
        """
        if hasattr(self, "children") and self.children:
            for substep in self.children:
                substep.scale(scale)

    def tree_locks(self, platform_controller: Any) -> list[str]:
        """Returns all locks required by self and substeps during execution.

        Args:
            platform_controller (Any):  Platform controller to use for
                calculating which nodes in graph are used by step.

        Returns:
            List[str]: list of step locks required to execute self and all
                substeps.
        """
        self_locks = self.locks(platform_controller)
        if self.parent:
            return list(set(self.parent.tree_locks(platform_controller) + self_locks))
        else:
            return self_locks

    async def execute(
        self,
        platform_controller: Any,
        *args,
        **kwargs,
    ) -> bool:
        """Should be overwritten by higher Step classes. Raises an error if
        not overwritten.

        Args:
            platform_controller (Any): Platform controller object.

        Raises:
            NotImplementedError: Prompts user to write execute function for
                Step.
        """
        raise NotImplementedError("Execution reached Step.execute(...).")

    async def execute_step(
        self,
        platform_controller: Any,
        locks: dict[str | None, asyncio.Lock],
        tracer: list[tuple[type, dict]],
        step_indexes: list[int],
        deps: list[tuple[Step, asyncio.Task]] | None = None,
        level: int = 0,
    ) -> bool:
        """First acquires any locks required to execute the Step
        (that have not already been acquired by the parent step) and waits for
        any Steps to finish that the current step is dependent on. After these
        requirements are met, the step is executed.

        This function handles the logging and updates the tracer once the step
        has been executed, meaning that no additional logging is required within
        the Step's execute function.

        Args:
            platform_controller (Any): Platform controller object instantiated
                with modules and graph to run XDL on.
            deps (List[Tuple[Step, asyncio.Task]]): List of steps current Step
               is dependent on. The current step requires these steps to finish
               before it can be executed.
            locks (List[str]): List of names of the Locks that need to be
                acquired to execute the step.
            tracer ([List[Tuple[str, Dict]]): List of previously executed Steps
                and their properties at the point of execution.
            step_indexes (List[int]): Indexes into steps list and substeps
                lists.
            level (int, optional): Level of recursion in step execution.
                Defaults to 0.

        Returns:
            bool: ``True`` if execution should continue, ``False`` if execution
            should stop.
        """
        deps = deps if deps is not None else []

        if self.parent:
            parent_locks = self.parent.tree_locks(platform_controller)
        else:
            parent_locks = []

        locks = {
            lock: platform_controller._locks[lock]
            for lock in locks
            if lock not in parent_locks
        }

        async with self.await_requirements(deps, locks) as keep_going:
            if not keep_going:
                return keep_going

            # Log base step start timestamp here, as it is easier than adding to
            # all base step `execute` methods. Only base step logged here as
            # normal step start / end timestamps logged at start / end of this
            # method.
            log_duration(self, "start")
            self.logger.info(start_executing_step_msg(self, step_indexes))

            # Execute step, don't pass `step_indexes` to base step, and log step
            # completion here. Step completion isn't needed to be logged for
            # normal steps as it is done recursively at the end of this
            # function.
            keep_going = await self.execute(
                platform_controller,
                self.logger,
                level=level,
                step_indexes=step_indexes,
                tracer=tracer,
            )

            update_tracer(tracer, self)

            # Log base step end timestamp here, as it is easier
            # than adding to all base step `execute` methods.
            log_duration(self, "end")
            self.logger.info(finished_executing_step_msg(self, step_indexes))

            return keep_going

    @contextlib.asynccontextmanager
    async def await_requirements(
        self,
        deps: list[tuple[Step, asyncio.Task]],
        locks: dict[str | None, asyncio.Lock],
    ):
        """Waits for list of dependencies (Steps) to be executed then acquires
        locks from given list. Once finished, it will release the locks
        acquired.

        Args:
           deps (List): List of steps current Step is dependent on. The current
                step requires these steps to finish before it can be executed.
            locks (List[str]): List of names of the Locks that need to be
                acquired to execute the step.

        Yields:
            False: yields False until all dependencies are met and locks are
                acquired. This will prevent Step execution until requirements
                are met.
        """
        # Wait for all dependencies to finish
        if not await self.await_deps(deps):
            yield False

        await self.acquire_locks(locks)

        try:
            yield True
        except Exception as e:
            step_failed_msg = termcolor.colored(
                "Step failed", color="red", attrs=["bold"]
            )
            step_name = termcolor.colored(self.name, color="cyan", attrs=["bold"])
            props_table = termcolor.colored(
                pretty_props_table(self.properties), color="cyan"
            )
            self.logger.exception(
                "%s %s\n%s %s\n",
                step_failed_msg,
                step_name,
                self.human_readable(),
                props_table,
            )
            raise e
        finally:
            Step.release_locks(locks)

    def __eq__(self, other: Step) -> bool:
        """Allow ``step == other_step`` comparisons."""

        # Different type, not equal
        if type(other) != type(self):
            return False

        # Different name, not equal
        if other.name != self.name:
            return False

        # Different length of properties, not equal
        if len(self.properties) != len(other.properties):
            return False

        # Compare properties
        for k, v in other.properties.items():

            # Compare children
            if k == "children":

                # Different length of children, not equal
                if len(v) != len(self.steps):
                    return False

                # Compare individual children
                for i, other_child in enumerate(v):

                    # Children are different, not equal
                    if other_child != self.steps[i]:
                        return False

            # Property key is not in self.properties, not equal
            elif k not in self.properties:
                return False

            # Different values for property, not equal
            elif v != self.properties[k]:
                return False

        # Passed all equality tests, steps are equal
        return True

    def __ne__(self, other: Any) -> bool:
        """Recommended to include this just to show that non equality has been
        considered and it is simply ``not __eq__(other)``.
        """
        return not self.__eq__(other)

    def get_deps(
        self, task_groups: dict[str | None, list[asyncio.Task]]
    ) -> list[asyncio.Task]:
        if self.queue is None:
            # depend on all queues
            return list(chain(*task_groups.values()))
        else:
            return (
                # task_groups in own queue
                task_groups[self.queue]
                # task_groups in root queue
                + task_groups[None]
            )

    async def await_deps(self, deps: list[tuple[Step, asyncio.Task]]) -> bool:
        """Waits for the given tasks (deps) to be completed.

        Args:
            deps (List[asyncio.Task]): List of tasks to await.

        Returns:
            bool: Returns true once dependencies are met.
        """
        if not deps:
            return True

        steps, tasks = zip(*deps)
        for task in asyncio.as_completed(tasks):
            # cancel execution if a dependency failed
            keep_going = await task
            if not keep_going:
                return False
        return True

    async def acquire_locks(self, locks: dict[str | None, asyncio.Lock]) -> None:
        """Acquires locks for step.

        Args:
            locks (Dict[Union[str, None], asyncio.Lock]): Dictionary of Lock
                objects (values) to acquire.
        """
        if not locks:
            return

        def msg(locks: dict[str | None, asyncio.Lock], acquiring: bool = False):
            color_map = {
                True: "red" if not acquiring else "green",
                False: "green" if not acquiring else "red",
            }
            msg = ", ".join(
                [
                    f"[{color_map[lock_obj.locked()]}]{lock}[/]"
                    for lock, lock_obj in locks.items()
                ]
            )
            return msg

        while True:
            unlocked_states = [not lock.locked() for lock in locks.values()]
            if all(unlocked_states):
                break
            await asyncio.sleep(0.5)

        tasks = [lock.acquire() for lock in locks.values()]
        for task in asyncio.as_completed(tasks):
            await task

    @staticmethod
    def release_locks(locks: dict[str | None, asyncio.Lock]) -> None:
        """Releases given locks.

        Args:
            locks (Dict[Union[str, None], asyncio.Lock]): Dictionary of Lock
                objects (values) to acquire.
        """
        for lock in locks.values():
            lock.release()
