# Std
import asyncio
import collections
import logging
from abc import ABC, abstractmethod
from itertools import chain
from typing import Any, Dict, Iterator, List, Tuple

# Other
from networkx import MultiDiGraph

from xdl_master.xdl.constants import DONE
from xdl_master.xdl.steps.core.abstract_base_step import AbstractBaseStep
from xdl_master.xdl.steps.core.step import Step
from xdl_master.xdl.steps.utils import FTNDuration
from xdl_master.xdl.utils.logging import get_logger, log_duration


def get_base_steps(step: Step) -> List[AbstractBaseStep]:
    """Return list of given step's base steps. Recursively descends step tree
    to find base steps. Here rather than in utils as uses ``AbstractBaseStep``
    type so would cause circular import.

    Args:
        step (Step): Step to get base steps from.

    Returns:
        List[AbstractBaseStep]: List of step's base steps.
    """
    base_steps = []
    for step in step.steps:  # noqa: B020
        if isinstance(step, AbstractBaseStep):
            base_steps.append(step)
        else:
            base_steps.extend(get_base_steps(step))
    return base_steps


class AbstractStep(Step, ABC):
    """Abstract base class for all steps that contain other steps.
    Subclasses must implement steps and human_readable, and can also override
    vessel_specs if necessary.

    Attributes:
        properties (dict): Dictionary of step properties.
        human_readable (str): Description of actions taken by step.

    Args:
        param_dict (Dict[str, Any]): Step properties dict to initialize step
            with.
    """

    _steps = []
    _context = None

    def __init__(self, param_dict: Dict[str, Any]) -> None:
        super().__init__(param_dict)
        self._last_props = {}

        if "context" in param_dict:
            self.context = param_dict["context"]

        self._task_groups = collections.defaultdict(list)

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        self._context = value
        self._update_substep_context()

    @property
    def task_groups(self):
        return self._task_groups

    @property
    def steps(self):
        """The internal steps list is calculated only when it is asked for, and
        only when ``self.properties`` different to the last time steps was asked
        for. This is for performance reasons since during
        ``prepare_for_execution`` the amount of updates to ``self.properties``
        is pretty large.

        ::

            # steps updated
            step = Step(**props)

            # self.properties updated but steps not updated
            step.volume = 15

            # steps updated and returned
            print(step.steps)

            # steps not updated and returned, since properties haven't change
            # since last steps update
            print(step.steps)
        """
        # Only update self._steps if self.properties has changed.
        #
        # Optimization note: This may seem long winded compared to
        # self.properties != self._last_props but in Python 3.7 at least this is
        # faster.
        should_update = False
        for k, v in self.properties.items():
            if (k in self._last_props) and (self._last_props[k] != v):
                should_update = True
                break

            if k not in self._last_props:
                should_update = True
                break

        # If self.properties has changed, update self._steps
        if should_update:
            self._update_steps()
            self._last_props = self._copy_props()

        return self._steps

    def _update_steps(self):
        """Add context to steps and substeps when adding new steps."""
        self._steps = list(self.get_steps())
        self._update_substep_context()

    def _update_substep_context(self):
        """Update substeps contexts making substeps parent_context point
        to own context.
        """
        for substep in self._steps:
            substep.context.update(parent_context=self.context)

    def _copy_props(self) -> Dict[str, Any]:
        """Return copy of ``self.properties`` for use when deciding whether
        to use cached :py:attr:`_steps` or not.

        Returns:
            Dict[str, Any]: copy of ``self.properties`` for use when
                deciding whether to use cached :py:attr:`_steps` or not.
        """
        return self.properties.copy()

    @abstractmethod
    def get_steps(self) -> List[Step]:
        """Abstract method that must be overridden when creating non base steps.
        Should return a list of steps to be sequentially executed when the step
        is executed. No properties should be changed during this method. This is
        a one way street to return a list of steps based on the current
        properties of the step.

        Returns:
            List[Step]: List of steps to be sequentially executed when the step
                is executed.
        """
        return []

    def locks(self, platform_controller: Any) -> List:
        """Returns the set of locks that are required by all base steps of the
        Step during execution.

        Args:
             platform_controller (Any): Platform controller object.

        Returns:
            List: List of all locks required to execute all base steps.
        """
        locks = []
        for step in self.base_steps:
            child_locks = step.locks(platform_controller)
            for lock in child_locks:
                locks.append(lock)

        return list(set(locks))

    async def execute(
        self,
        platform_controller,
        logger: logging.Logger = None,
        level: int = 0,
        step_indexes: List[int] = None,
        tracer: List[Tuple[type, Dict]] = None,
    ) -> bool:
        """Execute self with given platform controller object.

        Schedules each Step as a task. Once all Step's are scheduled, they will
        be executed once their requirements are met (appropriate locks acquired
        and Step's they are dependent on are completed).

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

        # Log step start timestamp
        log_duration(self, "start")

        # Bump recursion level
        level += 1

        # Add a placeholder for the next index so that it can be assigned to
        # using `step_indexes[level]`
        step_indexes = step_indexes[:]
        step_indexes.append(0)

        for step_idx, step in enumerate(self.steps):
            # Update step indexes for current sub step
            substep_indexes = step_indexes[:]
            substep_indexes[level] = step_idx

            # Execute step
            deps = step.get_deps(self.task_groups)
            step_locks = step.locks(platform_controller)

            # step index needs to be a copy so it does not change during
            # execution (for logging)
            task = asyncio.create_task(
                step.execute_step(
                    platform_controller=platform_controller,
                    deps=deps,
                    locks=step_locks,
                    tracer=tracer,
                    step_indexes=substep_indexes,
                    level=level,
                )
                # name=step.name  # python >= 3.8
            )
            self.task_groups[step.queue].append((step, task))

        result = True

        if self.task_groups:
            all_steps, all_tasks = zip(*chain(*self.task_groups.values()))
            for t in asyncio.as_completed(all_tasks):
                keep_going = await t
                if not keep_going:
                    # If keep_going is False break execution. This is used by
                    # the Confirm step to stop execution if the user doesn't
                    # wish to continue.
                    return False
                elif keep_going is DONE:
                    result = keep_going

        # Log step end timestamp
        log_duration(self, "end")

        return result

    @property
    def base_steps(self) -> List[AbstractBaseStep]:
        """Return list of step's base steps.

        Returns:
            List[AbstractBaseStep]: Step's base steps.
        """
        base_steps = []
        for step in self.steps:
            if isinstance(step, AbstractBaseStep):
                base_steps.append(step)
            else:
                base_steps.extend(get_base_steps(step))
        return base_steps

    def duration(self, graph: MultiDiGraph) -> FTNDuration:
        """Return approximate duration in seconds of step calculated as sum of
        durations of all substeps. This method should be overridden where an
        exact or near exact duration is known. The fallback duration for base
        steps is 1 second.

        Args:
            graph (MultiDiGraph): Graph to use when calculating step duration.

        Returns:
            FTNDuration: Estimated duration of step in seconds.
        """
        duration = FTNDuration(0, 0, 0)
        for step in self.steps:
            duration += step.duration(graph)
        return duration

    def reagents_consumed(self, graph: MultiDiGraph) -> Dict[str, float]:
        """Return dictionary of reagents and volumes consumed in mL like this:
        ``{ reagent: volume... }``. Can be overridden otherwise just recursively
        adds up volumes used by base steps.

        Args:
            graph (MultiDiGraph): Graph to use when calculating volumes of
                reagents consumed by step.

        Returns:
            Dict[str, float]: Dict of reagents volumes consumed by step in
            format ``{reagent_id: reagent_volume...}``.
        """
        reagents_consumed = {}
        for substep in self.steps:
            step_reagents_consumed = substep.reagents_consumed(graph)
            for reagent, volume in step_reagents_consumed.items():
                if reagent in reagents_consumed:
                    reagents_consumed[reagent] += volume
                else:
                    reagents_consumed[reagent] = volume
        return reagents_consumed

    @property
    def step_tree(self) -> Iterator[Step]:
        """Iterator yielding all substeps in steptree in depth first fashion."""
        for substep in self.steps:
            yield substep
            if isinstance(substep, AbstractStep):
                yield from substep.step_tree
