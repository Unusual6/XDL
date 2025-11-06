from typing import Any, Callable, Dict, List, Optional

from xdl_master.xdl.steps import AbstractBaseStep


class Callback(AbstractBaseStep):
    """Call ``fn`` when this step is executed with given args.

    Args:
        fn (Callable): Function to call. If the function has an output,
            the output will be returned by the Callback.
        args (List[Any]): arguments required by the function (fn).
        keyword_args (Dict[str, Any]): keyword arguments required by fn.
    """

    PROP_TYPES = {"fn": Callable, "args": List[Any], "keyword_args": Dict[str, Any]}

    def __init__(
        self,
        fn: Callable,
        args: Optional[List[Any]] = None,
        keyword_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        args = args if args is not None else []
        keyword_args = keyword_args if keyword_args is not None else {}
        super().__init__(locals())

    async def execute(self, chempiler, logger, level=0):
        return self.fn(*self.args, **self.keyword_args)
