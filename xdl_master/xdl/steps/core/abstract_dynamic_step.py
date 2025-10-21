# Std
import asyncio
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Tuple

from networkx import MultiDiGraph

from xdl_master.xdl.errors import XDLError
from xdl_master.xdl.steps.core.abstract_async_step import AbstractAsyncStep
from xdl_master.xdl.steps.core.abstract_base_step import AbstractBaseStep
from xdl_master.xdl.steps.core.step import Step
from xdl_master.xdl.steps.utils import FTNDuration
from xdl_master.xdl.utils.logging import get_logger

if False:
    from xdl.execution import AbstractXDLExecutor


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


class AbstractDynamicStep(Step):
    """Step for containing dynamic experiments in which feedback from analytical
    equipment controls the flow of the experiment.

    Provides abstract methods :py:meth:`on_start`, :py:meth:`on_continue` and
    :py:meth:`on_finish` that each return lists of steps to be performed at
    different stages of the experiment. :py:meth:`on_continue` is called
    repeatedly until it returns an empty list.

    What steps are to be returned should be decided base on the state attribute.
    The state can be updated from any of the three lifecycle methods or from
    :py:class:`AbstractAsyncStep` callback functions.

    Args:
        param_dict (Dict[str, Any]): Step properties dict to initialize step
            with.
    """

    def __init__(self, param_dict: Dict[str, Any]) -> None:
        super().__init__(param_dict)
        self.state = {}
        self.async_steps = []
        self.steps = []

        # None instead of empty list so that you can tell if its been
        # intialized or not. Start block can just be [].
        self.start_block = None
        self.started = False

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

    @abstractmethod
    def on_start(self) -> List[Step]:
        """Returns list of steps to be executed once at start of step.

        Returns:
            List[Step]: List of  steps to be executed once at start of step.
        """
        return []

    @abstractmethod
    def on_continue(self) -> List[Step]:
        """Returns list of steps to be executed in main loop of step, after
        on_start and before on_finish. Is called repeatedly until empty list is
        returned at which point the steps returned by on_finish are executed
        and the step ends.

        Returns:
            List[Step]: List of steps to execute in main loop based on
                self.state.
        """
        return []

    @abstractmethod
    def on_finish(self) -> List[Step]:
        """Returns list of steps to be executed once at end of step.

        Returns:
            List[Step]: List of steps to be executed once at end of step.
        """
        return []

    def reset(self) -> None:
        """Reset state of step. Should be overridden but doesn't have to be."""
        return

    def resume(
        self, platform_controller: Any, logger: logging.Logger = None, level: int = 0
    ) -> None:
        """Resume execution after a pause.

        Args:
            platform_controller (Any): Platform controller to execute step with.
            logger (logging.Logger): Logger to log execution info with.
            level (int): Recursion level of step execution.
        """
        self.started = False  # Hack to avoid reset.
        self.start_block = []  # Go straight to on_continue
        self.execute(platform_controller, logger=logger, level=level)

    def _post_finish(self) -> None:
        """Called after steps returned by :py:meth:`on_finish` have finished
        executing to try to join all threads.
        """
        for async_step in self.async_steps:
            async_step.kill()

    def prepare_for_execution(
        self, graph: MultiDiGraph, executor: "AbstractXDLExecutor"
    ) -> None:
        """Prepare step for execution.

        Args:
            graph (MultiDiGraph): Graph to use when preparing step for
                execution.
            executor (AbstractXDLExecutor): Executor to compile
                :py:attr:`start_block` with.
        """
        self.executor = executor
        self.graph = graph
        self.start_block = self.on_start()
        self.executor.prepare_block_for_execution(self.graph, self.start_block)

    async def execute_block(
        self,
        block: List[Step],
        platform_controller: Any,
        level: int = 0,
        step_indexes: List[int] = None,
        tracer: List[Tuple[type, Dict]] = None,
    ) -> None:
        """Executes a block of Step. Acquires locks necessary for execution
        for each Step before its execution.

        Args:
            block (List[Step]): List of Steps to execute.
            platform_controller (Any): Platform controller object instantiated
                with modules and graph to run XDL on.
            level (int, optional): Level of recursion in step execution.
                Defaults to 0.
            step_indexes (List[int]): Indexes into steps list and substeps
                lists. Defaults to None.
            tracer (List, optional): List of previously executed Steps and their
                properties at the point of execution. Defaults to None.
        """
        step_indexes = step_indexes if step_indexes is not None else [0]

        if self.parent:
            parent_locks = self.parent.tree_locks(platform_controller)
        else:
            parent_locks = []

        for step in block:
            step_indexes = step_indexes[:]
            step_indexes.append(0)
            step_indexes[level + 1] = self.substep_index
            step_indexes = step_indexes[: level + 2]

            step_locks = {
                lock: platform_controller._locks[lock]
                for lock in step.locks(platform_controller)
                if lock not in parent_locks
            }

            # no deps here because steps are executed sequentially
            await step.execute_step(
                platform_controller=platform_controller,
                deps=None,
                locks=step_locks,
                tracer=tracer,
                step_indexes=step_indexes,
            )

            if isinstance(step, AbstractAsyncStep):
                self.async_steps.append(step)
            self.substep_index += 1

    async def execute(
        self,
        platform_controller: Any,
        logger: logging.Logger = None,
        level: int = 0,
        step_indexes: List[int] = None,
        tracer: List[Tuple[type, Dict]] = None,
    ) -> None:
        """Execute step lifecycle. :py:meth:`on_start`, followed by
        :py:meth:`on_continue` repeatedly until an empty list is returned,
        followed by :py:meth:`on_finish`, after which all threads are joined as
        fast as possible.

        Args:
            platform_controller (Any): Platform controller object to use for
                executing steps.
            logger (Logger): Logger object.
            level (int): Level of recursion in step execution.
            step_indexes (List[int]): Indexes into steps list and substeps
                lists.

        Returns:
            bool: ``True`` if execution should continue, ``False`` if execution
            should stop.
        """
        if logger is None:
            logger = get_logger()

        # Not simulation, execute as normal
        if self.started:
            self.reset()

        # Get default step indexes if they are not passed
        step_indexes = step_indexes if step_indexes is not None else [0]
        self.substep_index = 0

        self.started = True

        if self.start_block is None:
            raise XDLError(
                "Dynamic step has not been prepared for execution.\
 if executing steps individually, please use\
 `xdl_obj.execute(platform_controller, step_index)` rather than\
 `xdl_obj.steps[step_index].execute(platform_controller)`."
            )

        # If platform controller simulation flag is True, run simulation steps
        if platform_controller.simulation is True:

            # Run simulation steps
            await asyncio.create_task(
                self.simulate(
                    platform_controller, step_indexes=step_indexes, tracer=tracer
                )
            )

            return True

        # Execute steps from on_start
        await self.execute_block(
            self.start_block,
            platform_controller=platform_controller,
            step_indexes=step_indexes,
            tracer=tracer,
        )

        # Repeatedly execute steps from on_continue until empty list returned
        continue_block = self.on_continue()
        self.executor.prepare_block_for_execution(self.graph, continue_block)

        # Execute steps from on_continue
        while continue_block:
            await self.execute_block(
                continue_block,
                platform_controller=platform_controller,
                step_indexes=step_indexes,
                tracer=tracer,
            )
            continue_block = self.on_continue()
            self.executor.prepare_block_for_execution(self.graph, continue_block)

        # Execute steps from on_finish
        finish_block = self.on_finish()
        self.executor.prepare_block_for_execution(self.graph, finish_block)

        await self.execute_block(
            finish_block,
            platform_controller=platform_controller,
            step_indexes=step_indexes,
            tracer=tracer,
        )

        # Kill all threads
        self._post_finish()

        return True

    async def simulate(
        self,
        platform_controller: Any,
        step_indexes: List[int] = None,
        tracer: List[Tuple[type, Dict]] = None,
    ) -> str:
        """Run simulation steps to catch any errors that may occur during
        execution.

        Args:
            platform_controller (Any): Platform controller to use to run
                simulation steps. Should be in simulation mode.
            logger (logging.Logger): XDL logger object.
            level (int): Recursion level of step.
            step_indexes (List[int]): Indexes into steps list and substeps
                lists.
            tracer (List[(str, Dict)]): Tracer with all steps that have been
                executed and their properties at execution time.
                Defaults to None.
        """
        step_indexes = step_indexes if step_indexes is not None else [0]

        simulation_steps = self.get_simulation_steps()
        step_indexes = step_indexes[:]
        step_indexes.append(0)

        await self.execute_block(
            simulation_steps,
            platform_controller=platform_controller,
            step_indexes=step_indexes,
            tracer=tracer,
        )

    @abstractmethod
    def get_simulation_steps(self) -> List[Step]:
        """Should return all steps that it is possible for the step to run when
        it actually executes. The point of this is that due to the fact the
        steps list is not known ahead of time in a dynamic step, normal
        simulation cannot be done. So this is here to provide a means of
        specifying steps that should pass simulation.

        Returns:
            List[Step]: List of all steps that it is possible for the dynamic
            step to execute.
        """
        return []

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
        for substep in self.start_block:
            step_reagents_consumed = substep.reagents_consumed(graph)
            for reagent, volume in step_reagents_consumed.items():
                if reagent in reagents_consumed:
                    reagents_consumed[reagent] += volume
                else:
                    reagents_consumed[reagent] = volume
        return reagents_consumed

    def duration(self, graph: MultiDiGraph) -> FTNDuration:
        """Return duration of start block, since duration after that is unknown.

        Returns:
            FTNDuration: Estimated duration of step in seconds.
        """
        duration = FTNDuration(0, 0, 0)
        for step in self.start_block:
            duration += step.duration(graph)
        return duration
