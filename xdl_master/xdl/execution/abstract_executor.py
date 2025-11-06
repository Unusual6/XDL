import asyncio
import hashlib
import logging
from abc import ABC
from itertools import chain
from typing import Any, Dict, List, Optional, Tuple

from networkx import MultiDiGraph
from networkx.readwrite import node_link_data

from xdl_master.xdl.errors import (
    XDLExecutionBeforeCompilationError,
    XDLExecutionOnDifferentGraphError,
)
from xdl_master.xdl.execution.utils import do_sanity_check
from xdl_master.xdl.steps import NON_RECURSIVE_ABSTRACT_STEPS
from xdl_master.xdl.steps.base_steps import AbstractDynamicStep, Step
from xdl_master.xdl.utils.logging import get_logger

if False:
    from xdl import XDL


class AbstractXDLExecutor(ABC):
    """Abstract class for XDL executor. The main functionality of this class is
    to perform compilation and execution of a given XDL object.

    Args:
        xdl (XDL): XDL object to compile / execute.

    Attributes:
        _prepared_for_execution (bool): Flag to specify whether self._xdl is
            ready for execution or not. Should be set to True at the end of
            :py:meth:`prepare_for_execution`.
        _xdl (XDL): XDL object passed to ``__init__``. This object will be
            altered during :py:meth:`prepare_for_execution`.
        _graph (MultiDiGraph): Graph passed to :py:meth:`prepare_for_execution`.
            ``self._xdl`` will be altered to execute on this graph during
            :py:meth`prepare_for_execution`.
        logger (logging.Logger): Logger object for executor to use when logging.
    """

    _prepared_for_execution: bool = False
    _xdl: "XDL" = None
    _graph: MultiDiGraph = None
    logger: logging.Logger = None

    def __init__(self, xdl: "XDL" = None) -> None:
        """Initalize ``_xdl`` and ``logger`` member variables."""
        self._xdl = xdl
        self.logger = get_logger()

    ####################
    # Abstract Methods #
    ####################

    def _graph_hash(self, graph: MultiDiGraph = None) -> str:
        """Get SHA 256 hash of graph. Used to determine whether graph used for
        execution is the same as the one used for compilation.

        Recommended to override this basic implementation, as this will give
        you a different hash if the position of nodes change, even if the
        properties and connectivity stays the same.

        Args:
            graph (MultiDiGraph): Graph to get hash of.

        Returns:
            str: Hash of graph.
        """
        if not graph:
            graph = self._graph
        return hashlib.sha256(str(node_link_data(graph)).encode("utf-8")).hexdigest()

    def prepare_for_execution(self, graph: MultiDiGraph, **kwargs) -> None:
        """Abstract compile method. Should convert :py:attr:`_xdl` into an
        executable form.

        At the moment, the implementation of this
        method is completely open. When it becomes clear what overlap there is
        between implementation on different platforms, it could make sense to
        move some code from platform specific implementations into the abstract
        class. At the moment pretty much everything has to be done in the
        platform specific implementation.

        Tasks this method must generally complete:
            1. Map all vessels in ``self._xdl.vessel_specs`` to vessels in
               graph. This involves choosing a graph vessel to use for every
               vessel in ``self._xdl.vessel_specs``, and updating every
               occurrence of the xdl vessel in ``self._xdl.steps`` with the
               appropriate graph vessel.

            2. Add internal properties to all steps, child steps and substeps.
               This can typically be done by calling
               :py:meth:`add_internal_properties`. This may need to be done more
               than once, depending on the way in which new steps are added
               and step properties are updated during this method.

            3. Do sanity checks to make sure that the procedure is indeed
               executable. As a bare minimum :py:meth:`perform_sanity_checks`
               should be called at the end of this method.

            4. Once :py:attr:`_xdl` has been successfully prepared for
               execution, set :py:attr:`self._prepared_for_execution` to True.

        Additionally, if for any reason :py:attr:`_xdl` cannot be prepared for
        execution with the given graph, helpful, informative errors should be
        raised.

        Args:
            graph_file (Union[str, MultiDiGraph]): Path to graph file, or loaded
                graph to compile procedure with.
        """
        self._graph = graph
        self.add_internal_properties()
        self.perform_sanity_checks()
        self._prepared = True

    ########################
    # Non Abstract Methods #
    ########################

    def perform_sanity_checks(
        self, steps: List[Step] = None, graph: MultiDiGraph = None
    ) -> None:
        """Recursively perform sanity checks on every step in steps list. If
        steps list not given defaults to ``self._xdl.steps``.

        Args:
            steps (List[Step]): List of steps to perform sanity checks
                recursively for every step / substep.
                Defaults to ``self._xdl.steps``
            graph (MultiDiGraph): Graph to use when running sanity checks. If
                not given will use :py:attr:`_graph`.
        """
        if graph is None:
            graph = self._graph
        if steps is None:
            steps = self._xdl.steps
        for step in steps:
            do_sanity_check(graph, step)

    def add_internal_properties(
        self, graph: MultiDiGraph = None, steps: List[Step] = None
    ) -> None:
        """Recursively add internal properties to all steps, child steps and
        substeps in given list of steps. If graph and steps not given use
        `self._graph` and ``self._xdl.steps``. This method recursively calls the
        ``on_prepare_for_execution`` method of every step, child step and
        substep in the step list.

        Args:
            graph (MultiDiGraph): Graph to pass to step
                ``on_prepare_for_execution`` method.
            steps (List[Step]): List of steps to add internal properties to.
                This steps in this list are altered in place, hence no return
                value.
        """
        if graph is None:
            graph = self._graph
        if steps is None:
            steps = self._xdl.steps

        def prep_function(graph, step):
            self.add_internal_properties_to_step(graph, step)

        # Iterate through each step
        for step in steps:
            step.register_prep_function(prep_function, graph)

    def add_internal_properties_to_step(self, graph: MultiDiGraph, step: Step) -> None:
        """Add internal properties to given step and all its substeps and
        child steps.

        Args:
            graph (MultiDiGraph): Graph to pass to step
                ``on_prepare_for_execution`` method.
            step (Step): Step to add internal properties to.
                The step is altered in place, hence no return
                value.
        """
        # Prepare the step for execution
        step.on_prepare_for_execution(graph)

        # Special case for Dynamic steps
        if isinstance(step, AbstractDynamicStep):
            step.prepare_for_execution(graph, self)

        # Recursive steps, add internal properties to all substeps
        elif not isinstance(step, NON_RECURSIVE_ABSTRACT_STEPS):
            self.add_internal_properties(graph, step.steps)

    def prepare_dynamic_steps_for_execution(
        self, step: Step, graph: MultiDiGraph
    ) -> None:
        """Prepare any dynamic steps' start blocks for execution. This is used
        during :py:meth:`add_internal_properties` and during execution. The
        reason for using during execution is that when loaded from XDLEXE
        dynamic steps do not have a start block. In the future the start block
        of dynamic steps could potentially be saved in the XDLEXE.

        Args:
            step (Step): Step to recursively prepare any dynamic steps for
                execution.
            graph (MultiDiGraph): Graph to use when preparing for execution.
        """
        if isinstance(step, AbstractDynamicStep):
            if step.start_block is None:
                step.prepare_for_execution(graph, self)
            for substep in step.start_block:
                self.prepare_dynamic_steps_for_execution(substep, graph)
        elif not isinstance(step, NON_RECURSIVE_ABSTRACT_STEPS):
            for substep in step.steps:
                self.prepare_dynamic_steps_for_execution(substep, graph)

    async def execute(
        self,
        platform_controller: Any,
        interactive: Optional[bool] = True,
        tracer: Optional[List[Tuple[type, Dict]]] = None,
    ) -> None:
        """Execute XDL procedure with given platform controller.
        The same graph must be passed to the platform controller and to
        prepare_for_execution.

        Schedules each Step as a task. Once all Step's are scheduled, they will
        be executed once their requirements are met (appropriate locks acquired
        and Step's they are dependent on are completed).

        If execution is aborted (a Step returns False), all pending tasks will
        be cancelled.

        Args:
            platform_controller (Any): Platform controller object to execute XDL
                with.
            interactive (bool, optional): Prompt user to confirm certain steps.
                Defaults to True.
            tracer (List[(str, Dict)]): Tracer with all steps that have been
                executed and their properties at execution time.

        Raises:
            XDLExecutionOnDifferentGraphError: If trying to execute XDLEXE on
                different graph to the one which was used to compile it.
            XDLExecutionBeforeCompilationError: Trying to execute XDL object
                before it has been compiled.
        """
        # XDLEXE, check graph hashes match
        if not self._prepared_for_execution and self._xdl.compiled:

            # Currently, this check only performed for Chemputer
            if hasattr(platform_controller, "graph"):

                # Check graph hashes match
                if self._xdl.graph_sha256 == self._graph_hash(
                    platform_controller.graph
                ):

                    self.logger.info("Executing xdlexe, graph hashes match.")
                    self._prepared_for_execution = True

                # Graph hashes don't match raise error
                else:
                    raise XDLExecutionOnDifferentGraphError()

            # For platforms other than Chemputer just switch flag
            else:
                self._prepared_for_execution = True

        # Execute procedure
        if not self._prepared_for_execution:
            raise XDLExecutionBeforeCompilationError()

        self.logger.info(
            "Procedure\n"
            "---------\n\n"
            f"{self._xdl.human_readable()}\n"  # fmt: skip
        )

        task_groups = self._xdl.task_groups

        # create tasks from all steps and schedule them with asyncio
        step: Step
        for i, step in enumerate(self._xdl.steps):
            step_indexes = [i]
            deps = step.get_deps(task_groups)
            step_locks = {
                lock: platform_controller._locks[lock]
                for lock in step.locks(platform_controller)
            }

            # Execute step
            task = asyncio.create_task(
                step.execute_step(
                    platform_controller=platform_controller,
                    deps=deps,
                    locks=step_locks,
                    tracer=tracer,
                    step_indexes=step_indexes,
                )
                # name=step.name  # python >= 3.8
            )
            # order tasks by 'queue', any tasks without a queue (None)
            # will be added to the root task queue.
            task_groups[step.queue].append((step, task))

        if task_groups:
            all_steps, all_tasks = zip(*chain(*task_groups.values()))
            for task in asyncio.as_completed(all_tasks):
                keep_going = await task
                if not keep_going:
                    # name = (
                    #     task.get_name()
                    #     if hasattr(task, "name")
                    #     else task.__name__
                    # )  # python >= 3.8
                    self.logger.warning("Aborted execution.")
                    # cancel all tasks while aborting
                    for t in all_tasks:
                        t.cancel()
                    break
