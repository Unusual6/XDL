from typing import Sequence, Type

from .core import (
    AbstractAsyncStep,
    AbstractBaseStep,
    AbstractDynamicStep,
    AbstractStep,
    Step,
    UnimplementedStep,
)
from .special import Async, Await, Callback, Loop, Repeat, Wait

# Steps that don't contain step.steps
NON_RECURSIVE_ABSTRACT_STEPS: Sequence[Type[Step]] = (
    AbstractBaseStep,
    AbstractDynamicStep,
    AbstractAsyncStep,
)
