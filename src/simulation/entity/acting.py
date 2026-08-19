from typing import Protocol

from core.actions import ActionSpec, EntityAction
from simulation.entity.context import ContextBlock


class ActComponent(Protocol):
    """The one privileged component: turns assembled context into an action."""

    async def get_action_attempt(
        self, blocks: tuple[ContextBlock, ...], spec: ActionSpec
    ) -> EntityAction: ...
