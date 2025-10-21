from typing import Any, Dict

from xdl_master.xdl.steps.core.step import Step


class UnimplementedStep(Step):
    """Abstract base class for steps that have no implementation but are
    included either as stubs or for the purpose of showing requirements or
    ``human_readable``.

    Args:
        param_dict (Dict[str, Any]): Step properties dict to initialize step
            with.
    """

    def __init__(self, param_dict: Dict[str, Any]) -> None:
        super().__init__(param_dict)
        self.steps = []

    async def execute(
        self, platform_controller, logger=None, level=0, step_indexes=None
    ):
        step_indexes = step_indexes if step_indexes is not None else [0]
        raise NotImplementedError(f"{self.__class__.__name__} step is unimplemented.")
