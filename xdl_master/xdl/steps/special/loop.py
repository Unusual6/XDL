from typing import List, Union

from xdl_master.xdl.steps import AbstractDynamicStep, Step
from xdl_master.xdl.utils.steps import steps_from_step_templates


class Loop(AbstractDynamicStep):
    """Repeat children of this step indefinitely.

    Args:
        children (List[Step]): Child steps to repeat.

    """

    PROP_TYPES = {"children": Union[Step, List[Step]]}

    def __init__(self, children: Union[Step, List[Step]], **kwargs) -> None:
        if type(children) != list:
            children = [children]

        self.context = kwargs.get("context", None)

        # for steps with children, their steps are instantiated as 'Step'
        # objects and need to be converted from step templates to steps
        # (requires parent to have context).
        self.children = steps_from_step_templates(
            parent=self, step_templates=children, bindings=kwargs
        )

        super().__init__(locals())

    def on_start(self):
        """Nothing to be done."""
        return []

    def on_continue(self):
        """Perform child steps"""
        return self.children

    def on_finish(self):
        """Nothing to be done."""
        return []
