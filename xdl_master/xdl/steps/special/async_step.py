import asyncio
import logging
from typing import Callable, List, Union

from xdl_master.xdl.errors import XDLError
from xdl_master.xdl.steps import AbstractAsyncStep, Step
from xdl_master.xdl.utils.steps import steps_from_step_templates


class Async(AbstractAsyncStep):
    """Wrapper to execute a step or sequence of steps asynchronously.

    Use like this:

    ``async_stir_step = Async(Stir(vessel=filter, time=3600))``

    Can be stopped in between steps by calling ``async_stir_step.kill()``

    Args:
        children (Union[Step, List[Step]]): Step object or list of Step objects
            to execute asynchronously.
        pid (str): Process ID. Optional, but must be given if using
            :py:class:``Await`` later in procedure.
        on_finish (Callable): Callback function to call after execution of steps
            has finished.
    """

    __xdl_deprecated__ = True

    PROP_TYPES = {
        "children": Union[Step, List[Step]],
        "pid": str,
        "on_finish": Callable,
    }

    def __init__(
        self,
        children: Union[Step, List[Step]],
        pid: str = None,
        on_finish: Callable = None,
        **kwargs,
    ) -> None:
        if not children:
            raise XDLError("Async: No children specified.")

        if type(children) != list:
            children = [children]

        self.context = kwargs.get("context", None)

        # for steps with children, their steps are instantiated as 'Step'
        # objects and need to be converted from step templates to steps
        # (requires parent to have context).
        self.children = steps_from_step_templates(
            parent=self, step_templates=children, validate=False, bindings=kwargs
        )

        super().__init__(locals())

        self.logger.info(
            'WARNING: Async is now deprecated. This step has been \
kept for backwards compatibility, but we recommend you specify "queue" to \
schedule steps to run at the same time. \
Please see documentation for more detail on "Parallel Execution" in XDL2.'
        )

        self._should_end = False
        self.finished = False

    @property
    def steps(self):
        if hasattr(self, "children"):
            return self.children
        # when context is set during init, it calls Async.steps when
        # self.children is not yet set.
        else:
            return []

    async def async_execute(
        self,
        chempiler: "Chempiler",  # noqa: F821
        logger: logging.Logger = None,
        level: int = 0,
        step_indexes: List[int] = None,
    ) -> None:
        # Get default step indexes if they are not passed
        step_indexes = step_indexes if step_indexes is not None else [0]

        # Get logger if not passed
        if not logger:
            logger = logging.getLogger("xdl")

        # Execute async children steps
        for i, step in enumerate(self.steps):
            # Update step indexes
            step_indexes = step_indexes[:]
            step_indexes.append(0)
            step_indexes[level + 1] = i
            step_indexes = step_indexes[: level + 2]

            # Execute step
            keep_going = await asyncio.create_task(
                step.execute(
                    chempiler, logger, level=level + 1, step_indexes=step_indexes
                )
                # name=step.name  # python >= 3.8
            )

            # Break out of loop if either stop flag is ``True``
            if not keep_going or self._should_end:
                self.finished = True
                return

        # Finish and log step finish
        self.finished = True
        if self.on_finish:
            self.on_finish()
        return True

    def human_readable(self, language="en"):
        human_readable = "Asynchronous:\n"
        for step in self.steps:
            human_readable += f"    {step.human_readable()}\n"
        return human_readable
