import pytest
from pydantic import BaseModel

from workbench.core.actions import ActionSpec, EntityAction, FreeAction, FreeActionSpec
from workbench.core.events import Event
from workbench.core.events.chat import ChatMessagePayload
from workbench.simulation.entity.component import (
    PHASE_SUCCESSORS,
    BaseComponent,
    check_successor,
)
from workbench.simulation.entity.context import ContextBlock, render_prompt
from workbench.simulation.entity.entity import ComposedEntity
from workbench.simulation.errors import PhaseError, SnapshotError


class CounterState(BaseModel):
    acts_seen: int = 0
    observations_seen: int = 0


class CounterComponent(BaseComponent):
    state_model = CounterState

    def __init__(self, name: str, label: str) -> None:
        super().__init__(name)
        self._label = label
        self._state = CounterState()

    async def pre_act(self, spec: ActionSpec) -> ContextBlock | None:
        return ContextBlock(label=self._label, content=f"acts={self._state.acts_seen}")

    async def post_act(self, action: EntityAction) -> None:
        self._state = self._state.model_copy(
            update={"acts_seen": self._state.acts_seen + 1}
        )

    async def pre_observe(self, event: Event) -> ContextBlock | None:
        self._state = self._state.model_copy(
            update={"observations_seen": self._state.observations_seen + 1}
        )
        return None

    def get_state(self) -> CounterState:
        return self._state

    def set_state(self, state: CounterState) -> None:
        self._state = state


class RecordingAct:
    def __init__(self) -> None:
        self.last_blocks: tuple[ContextBlock, ...] = ()

    async def get_action_attempt(
        self, blocks: tuple[ContextBlock, ...], spec: ActionSpec
    ) -> EntityAction:
        self.last_blocks = blocks
        return FreeAction(text=render_prompt(blocks))


def spec() -> FreeActionSpec:
    return FreeActionSpec(call_to_action="Say something.", tag="chat.message")


def chat_event() -> Event:
    payload = ChatMessagePayload(
        kind="chat.message",
        chat_message_id="chm-000001",
        conversation_id="cnv-000001",
        reply_to=None,
        sender="per-x",
        body="hello",
    )
    return Event(seq=0, time=0, tag=payload.kind, source="gm", payload=payload)


def make_entity() -> tuple[ComposedEntity, RecordingAct]:
    act = RecordingAct()
    entity = ComposedEntity(
        name="daniel",
        components=(
            CounterComponent("first", "First"),
            CounterComponent("second", "Second"),
        ),
        act_component=act,
    )
    return entity, act


def test_phase_graph_is_closed() -> None:
    assert set(PHASE_SUCCESSORS) == {
        "READY",
        "PRE_ACT",
        "POST_ACT",
        "PRE_OBSERVE",
        "POST_OBSERVE",
        "UPDATE",
    }
    check_successor("READY", "PRE_ACT")
    with pytest.raises(PhaseError):
        check_successor("PRE_ACT", "PRE_OBSERVE")


async def test_act_assembles_blocks_in_declaration_order() -> None:
    entity, act = make_entity()
    action = await entity.act(spec())
    assert [b.label for b in act.last_blocks] == ["First", "Second"]
    assert isinstance(action, FreeAction)
    assert "First" in action.text and "Second" in action.text


async def test_act_runs_full_lifecycle_and_returns_to_ready() -> None:
    entity, _ = make_entity()
    await entity.act(spec())
    await entity.observe(chat_event())
    await entity.act(spec())
    states = dict(
        (name, entity.get_component(name).get_state()) for name in ("first", "second")
    )
    assert states["first"].acts_seen == 2
    assert states["first"].observations_seen == 1


async def test_reentrant_act_raises_phase_error() -> None:
    class Malicious(BaseComponent):
        state_model = CounterState

        def __init__(self, entity_holder: dict) -> None:
            super().__init__("malicious")
            self._holder = entity_holder

        async def pre_act(self, s: ActionSpec) -> ContextBlock | None:
            await self._holder["entity"].act(spec())
            return None

        def get_state(self) -> CounterState:
            return CounterState()

        def set_state(self, state: CounterState) -> None:
            pass

    holder: dict = {}
    entity = ComposedEntity(
        name="evil",
        components=(Malicious(holder),),
        act_component=RecordingAct(),
    )
    holder["entity"] = entity
    with pytest.raises(PhaseError):
        await entity.act(spec())


def test_render_prompt_excludes_debug_blocks() -> None:
    rendered = render_prompt(
        (
            ContextBlock(label="Visible", content="shown"),
            ContextBlock(label="Hidden", content="not shown", debug_only=True),
        )
    )
    assert "shown" in rendered
    assert "not shown" not in rendered
    assert "Hidden" not in rendered


async def test_snapshot_round_trip() -> None:
    entity, _ = make_entity()
    await entity.act(spec())
    snap = entity.snapshot()

    fresh, _ = make_entity()
    fresh.restore(snap)
    assert fresh.get_component("first").get_state().acts_seen == 1


async def test_restore_rejects_unknown_component() -> None:
    entity, _ = make_entity()
    snap = entity.snapshot()
    other = ComposedEntity(
        name="daniel",
        components=(CounterComponent("renamed", "R"),),
        act_component=RecordingAct(),
    )
    with pytest.raises(SnapshotError):
        other.restore(snap)


async def test_restore_rejects_invalid_state() -> None:
    entity, _ = make_entity()
    snap = entity.snapshot()
    corrupted = snap.model_copy(
        update={
            "components": tuple(
                (name, {"acts_seen": "not-an-int-at-all", "observations_seen": []})
                for name, _ in snap.components
            )
        }
    )
    fresh, _ = make_entity()
    with pytest.raises(SnapshotError):
        fresh.restore(corrupted)
