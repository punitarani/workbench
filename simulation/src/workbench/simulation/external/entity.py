"""An entity whose act() is served by an external process.

The engine cannot tell this seat from an internal one — that is the whole
design. During generation a demonstrator plays it; during evaluation the
agent under test does.
"""

from pydantic import BaseModel

from workbench.core.actions import ActionSpec, ActRequest, EntityAction
from workbench.core.events import Event
from workbench.core.simtime import SimTime
from workbench.simulation.entity.entity import EntitySnapshot
from workbench.simulation.errors import SnapshotError
from workbench.simulation.external.transport import ActTransport


class ExternalEntityState(BaseModel):
    buffered: tuple[Event, ...] = ()


class ExternalEntity:
    def __init__(self, *, name: str, transport: ActTransport) -> None:
        self._name = name
        self._transport = transport
        self._buffered: tuple[Event, ...] = ()

    @property
    def name(self) -> str:
        return self._name

    async def observe(self, event: Event) -> None:
        self._buffered = (*self._buffered, event)

    async def act(self, spec: ActionSpec) -> EntityAction:
        observations = self._buffered
        self._buffered = ()
        time = SimTime(int(observations[-1].time)) if observations else SimTime(0)
        request = ActRequest(
            entity=self._name,
            spec=spec,
            observations=observations,
            time=time,
        )
        response = await self._transport.act(request)
        return response.action

    def snapshot(self) -> EntitySnapshot:
        state = ExternalEntityState(buffered=self._buffered)
        return EntitySnapshot(
            entity=self._name,
            components=(("external-buffer", state.model_dump(mode="json")),),
        )

    def restore(self, snap: EntitySnapshot) -> None:
        if snap.entity != self._name:
            raise SnapshotError(
                f"snapshot is for {snap.entity!r}, entity is {self._name!r}"
            )
        for name, raw in snap.components:
            if name == "external-buffer":
                state = ExternalEntityState.model_validate(raw)
                self._buffered = state.buffered
                return
        raise SnapshotError("snapshot has no external-buffer component")
