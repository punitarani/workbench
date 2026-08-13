"""Base for components whose reasoning is a DSPy module.

The module always executes under this component's own LM via dspy.context,
so per-entity models cannot leak into each other across concurrent tasks.
"""

import dspy

from workbench.simulation.entity.component import BaseComponent
from workbench.simulation.lm.dspy_lm import WorkbenchLM


class DSPyComponent(BaseComponent):
    def __init__(self, name: str, *, module: dspy.Module, lm: WorkbenchLM) -> None:
        super().__init__(name)
        self.module = module
        self._lm = lm

    async def _invoke(self, **inputs) -> dspy.Prediction:
        with dspy.context(lm=self._lm):
            return await self.module.acall(**inputs)
