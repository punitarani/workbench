"""Resolution as an inspectable pipeline of typed steps.

Steps may be pure transforms or LM-backed programs; every intermediate
context is observable, which is what makes resolution debuggable.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from workbench.core.actions import ActionSpec, EntityAction
from workbench.core.events import EventDraft
from workbench.simulation.entity.context import ContextBlock


class ResolutionContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: str
    spec: ActionSpec
    action: EntityAction
    time: int
    drafts: tuple[EventDraft, ...] = ()
    notes: tuple[ContextBlock, ...] = ()


class ResolutionStep(Protocol):
    async def __call__(self, ctx: ResolutionContext) -> ResolutionContext: ...


async def run_pipeline(
    steps: Sequence[ResolutionStep], ctx: ResolutionContext
) -> ResolutionContext:
    for step in steps:
        ctx = await step(ctx)
    return ctx
