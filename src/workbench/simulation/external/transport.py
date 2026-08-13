"""Transports that serve an externalized entity's actions."""

from typing import Protocol

from workbench.core.actions import ActRequest, ActResponse
from workbench.simulation.entity.entity import Entity
from workbench.simulation.errors import ScriptExhaustedError


class ActTransport(Protocol):
    async def act(self, request: ActRequest) -> ActResponse: ...


class InProcessTransport:
    """Wraps another Entity; used to prove injected == internal resolution."""

    def __init__(self, entity: Entity) -> None:
        self._entity = entity

    async def act(self, request: ActRequest) -> ActResponse:
        for event in request.observations:
            await self._entity.observe(event)
        action = await self._entity.act(request.spec)
        return ActResponse(action=action)


class ScriptedTransport:
    """Plays recorded responses in order; exhaustion is a hard error."""

    def __init__(self, responses: tuple[ActResponse, ...]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def act(self, request: ActRequest) -> ActResponse:
        if self._index >= len(self._responses):
            raise ScriptExhaustedError(
                f"script exhausted after {self._index} responses "
                f"(entity {request.entity})"
            )
        response = self._responses[self._index]
        self._index += 1
        return response
