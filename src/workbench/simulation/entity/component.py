"""Component lifecycle: an explicit phase graph, typed state, async hooks."""

from typing import ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from workbench.core.actions import ActionSpec, EntityAction
from workbench.core.events import Event
from workbench.simulation.entity.context import ContextBlock
from workbench.simulation.errors import PhaseError

Phase = Literal["READY", "PRE_ACT", "POST_ACT", "PRE_OBSERVE", "POST_OBSERVE", "UPDATE"]

PHASE_SUCCESSORS: dict[Phase, frozenset[Phase]] = {
    "READY": frozenset({"PRE_ACT", "PRE_OBSERVE"}),
    "PRE_ACT": frozenset({"POST_ACT"}),
    "POST_ACT": frozenset({"UPDATE"}),
    "PRE_OBSERVE": frozenset({"POST_OBSERVE"}),
    "POST_OBSERVE": frozenset({"UPDATE"}),
    "UPDATE": frozenset({"READY"}),
}


def check_successor(current: Phase, upcoming: Phase) -> None:
    if upcoming not in PHASE_SUCCESSORS[current]:
        raise PhaseError(f"illegal phase transition {current} -> {upcoming}")


@runtime_checkable
class Component(Protocol):
    state_model: ClassVar[type[BaseModel]]

    @property
    def name(self) -> str: ...
    async def pre_act(self, spec: ActionSpec) -> ContextBlock | None: ...
    async def post_act(self, action: EntityAction) -> None: ...
    async def pre_observe(self, event: Event) -> ContextBlock | None: ...
    async def post_observe(self) -> None: ...
    async def update(self) -> None: ...
    def get_state(self) -> BaseModel: ...
    def set_state(self, state: BaseModel) -> None: ...


class BaseComponent:
    """No-op defaults so components override only the hooks they use."""

    state_model: ClassVar[type[BaseModel]]

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def pre_act(self, spec: ActionSpec) -> ContextBlock | None:
        return None

    async def post_act(self, action: EntityAction) -> None:
        return None

    async def pre_observe(self, event: Event) -> ContextBlock | None:
        return None

    async def post_observe(self) -> None:
        return None

    async def update(self) -> None:
        return None
