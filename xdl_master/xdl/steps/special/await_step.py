import asyncio
import logging
from typing import List

from xdl_master.xdl.steps.core import AbstractAwaitStep


class Await(AbstractAwaitStep):
    """Wait for Async step with given pid to finish executing.

    Args:
        pid (str): pid of :py:class:``Async`` step to wait for.
    """

    PROP_TYPES = {
        "pid": str,
    }

    def __init__(self, pid: str, **kwargs):
        super().__init__(locals())
        self.steps = []

    async def execute(
        self,
        platform_controller,
        logger: logging.Logger = None,
        level: int = 0,
        step_indexes: List[int] = None,
    ) -> None:
        step_indexes = step_indexes if step_indexes is not None else [0]

        if self.context.xdl and self.pid:

            async_steps = [s for s in self.context.xdl().steps if s.name == "Async"]

            # Await async step with self.pid
            for async_step in async_steps:
                if async_step.pid == self.pid:
                    while not async_step.finished:
                        await asyncio.sleep(1)
                    # Reset async step so it can be used again, for example in
                    # Repeat step.
                    async_step.finished = False

        return True
