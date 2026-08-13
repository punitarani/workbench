"""The game-master contract the engine drives.

Control flow is typed decisions, not free text. Implementations decide how
much of each decision is code and how much is a language model.
"""

from typing import ClassVar, Protocol

from pydantic import BaseModel

from workbench.core.actions import (
    ActionSpec,
    EntityAction,
    NextActingDecision,
    ResolutionDecision,
    TerminateDecision,
)
from workbench.core.events import Event, EventDraft


class GameMaster(Protocol):
    state_model: ClassVar[type[BaseModel]]

    async def route(self, event: Event) -> tuple[str, ...]:
        """Who observes this event, in delivery order. Pure by convention."""
        ...

    async def next_acting(self, event: Event) -> NextActingDecision: ...

    async def action_spec_for(self, entity: str, event: Event) -> ActionSpec: ...

    async def resolve(
        self, entity: str, action: EntityAction, spec: ActionSpec, event: Event
    ) -> ResolutionDecision: ...

    async def consequences(self, event: Event) -> tuple[EventDraft, ...]:
        """World-driven follow-ups for events nobody acts on (day chains)."""
        ...

    async def should_terminate(self) -> TerminateDecision: ...

    def get_state(self) -> BaseModel: ...

    def set_state(self, state: BaseModel) -> None: ...
