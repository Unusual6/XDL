import asyncio
import logging
from typing import Dict, List, Tuple

from xdl_master.xdl.constants import DONE
from xdl_master.xdl.steps.core.abstract_step import AbstractStep, Step
from xdl_master.xdl.utils.prop_limits import MEASUREMENT_PROP_LIMIT

from . import Callback


class AbstractMonitorStep(AbstractStep):
    """Abstract class for all 'Monitor' steps. Such steps should continue to
    measure until a certain threshold is reached. Upon reaching that threshold,
    a XDLStatus of DONE (found in constants.py) should be returned.

    Such steps can be used in conjunction with 'Repeats', where no 'repeats'
    number is set. Repeat will continue to repeat the child steps until the
    XDLStatus of DONE is returned.

    This mechanism is recommended as a replacement for the deprecated dynamic
    step AddDynamic and any future steps which depend on sensor readings.

    The following behavior regarding the threshold values is anticipated:

    .. code-block:: text

                 min
        [-] <-----+----------------> [+]
              end | continue

                            max
        [-] <----------------+-----> [+]
                    continue | end

                 min        max
        [-] <-----+----------+-----> [+]
              end | continue | end

    Args:
        target (str): target vessel to measure.
        quantity (str): Quantity of the reading.
        min (float): Minimum threshold that stops iteration when measurement
            below.
        max (float): Maximum threshold that stops iteration when measurement
            above.
    """

    MANDATORY_NAME = "Monitor"

    PROP_TYPES = {
        "target": str,
        "quantity": str,
        "min": MEASUREMENT_PROP_LIMIT,
        "max": MEASUREMENT_PROP_LIMIT,
    }

    DEFAULT_PROPS = {
        "min": None,
        "max": None,
    }

    async def execute(
        self,
        platform_controller,
        logger: logging.Logger = None,
        level: int = 0,
        step_indexes: List[int] = None,
        tracer: List[Tuple[type, Dict]] = None,
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
        step_indexes = step_indexes if step_indexes is not None else [0]

        if (
            hasattr(platform_controller, "simulation")
            and platform_controller.simulation is True
        ):
            self.get_steps = self.get_simulation_steps
            self._update_steps()

        task = asyncio.create_task(
            super().execute(
                platform_controller=platform_controller,
                logger=logger,
                level=level,
                step_indexes=step_indexes,
                tracer=tracer,
            ),
            # name=step.name  # python >= 3.8
        )
        result = await task
        return result

    def get_simulation_steps(self) -> List[Step]:
        """In simulation, no sensor readings.
        Create DummyStep that returns DONE immediately.
        """
        return [Callback(lambda: DONE)]
