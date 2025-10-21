# Std
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from xdl_master.xdl.steps.core.step import Step
from xdl_master.xdl.steps.logging import (
    finished_executing_step_msg,
    start_executing_step_msg,
)
from xdl_master.xdl.utils.logging import log_duration
from xdl_master.xdl.utils.tracer import update_tracer


class AbstractBaseStep(Step, ABC):
    """Abstract base class for all steps that do not contain other steps and
    instead have an execute method that takes a ``platform_controller`` object.

    Subclasses must implement execute.

    Args:
        param_dict (Dict[str, Any]): Step properties dict to initialize step
            with.
    """

    def __init__(self, param_dict: Dict[str, Any]) -> None:
        super().__init__(param_dict)
        self.steps = []

    @abstractmethod
    async def execute(self, platform_controller, *args, **kwargs) -> bool:
        """Execute method to be overridden for all base steps. Take platform
        controller and use it to execute the step. Return ``True`` if procedure
        should continue after the step is completed, return ``False`` if the
        procedure should break for some reason.
        """
        return False

    async def execute_step(
        self,
        platform_controller: Any,
        locks: Dict[Union[str, None], asyncio.Lock],
        tracer: List[Tuple[type, Dict]],
        step_indexes: List[int],
        deps: Optional[List[Tuple[Step, asyncio.Task]]] = None,
        level: int = 0,
        **kwargs,
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
            tracer ([List]): List of previously executed Steps and their
                properties at the point of execution.
            step_indexes (List[int]): Indexes into steps list and substeps
                lists.
            level (int, optional): Level of recursion in step execution.
                Defaults to 0.

        Returns:
            bool: ``True`` if execution should continue, ``False`` if execution
            should stop.
        """
        deps = deps if deps is not None else []

        # get list of locks that parent Step has already acquired
        if self.parent:
            parent_locks = self.parent.tree_locks(platform_controller)
        else:
            parent_locks = []

        # get locks that still need to be acquired
        locks = {
            lock: platform_controller._locks[lock]
            for lock in locks
            if lock not in parent_locks
        }

        async with super().await_requirements(deps, locks) as keep_going:
            if not keep_going:
                return keep_going

            # Log base step start timestamp here, as it is easier than
            # adding to all base step `execute` methods. Only base step
            # logged here as normal step start / end timestamps logged
            # at start / end of this method.
            log_duration(self, "start")

            # Log step start
            self.logger.info(start_executing_step_msg(self, step_indexes))

            # Execute step, don't pass `step_indexes` to base step,
            # and log step completion here. Step completion isn't
            # needed to be logged for normal steps as it is done
            # recursively at the end of this function.
            keep_going = await self.execute(
                platform_controller, logger=self.logger, level=level
            )

            update_tracer(tracer, self)

            # Log base step end timestamp here, as it is easier
            # than adding to all base step `execute` methods.
            log_duration(self, "end")

            # Log step completion
            self.logger.info(finished_executing_step_msg(self, step_indexes))

            return keep_going

    @property
    def base_steps(self):
        """Just return self as the base_steps. Used by recursive ``base_steps``
        method of ``AbstractStep``. No need to override this.
        """
        return [self]
