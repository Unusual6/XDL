"""
.. module:: steps_synthesis.adjust_ph
    :platform: Unix, Windows
    :synopsis: Dynamic XDL step for adjusting the pH of a reaction vessel.

"""

from xdl_master.xdl.constants import DONE
from xdl_master.xdl.steps import AbstractBaseStep


class MockMeasure(AbstractBaseStep):
    """Mock step for implementing the measurement of a sensor.

    Note:
        This method is currently just a stub with absolutely zero implementation
        of hardware control. This is purely to validate the repeat step and
        in XDL.
        This step requires an implementation and refinement.

    Args:
        None
    """

    PROP_TYPES = {"target_repeats": int}
    DEFAULT_PROPS = {"target_repeats": 1}

    INTERNAL_PROPS = []

    def __init__(self, target_repeats="default", **kwargs):
        super().__init__(locals())

    async def execute(self, chempiler, logger=None, level=0) -> bool:
        """Executes the XDL step.

        Args:
            chempiler (Chempiler): Chempiler object
            logger (Logger, optional): Logging object. Defaults to None.
            level (int, optional): Logging level. Defaults to 0.

        Returns:
            bool: Step executed successfully.
        """
        # Increment as counter starts at 0
        current_iteration = self.context._counter + 1
        if current_iteration is not None and (current_iteration >= self.target_repeats):
            return DONE
        return True
