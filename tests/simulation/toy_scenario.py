"""A three-person chat scenario exercising the full engine loop with no LM.

ann kicks off a thread; the game master picks the next speaker round-robin;
each reply is deterministic. Used by engine, determinism, and resume tests.
"""

from pathlib import Path

from pydantic import BaseModel

from workbench.core.actions import (
    ActionSpec,
    EntityAction,
    FreeAction,
    FreeActionSpec,
    NextActingDecision,
    ResolutionDecision,
    TerminateDecision,
)
from workbench.core.events import Event, EventDraft
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.ids import IdMinter
from workbench.core.simtime import SimDuration, SimTime
from workbench.core.store import SqliteRunStore
from workbench.core.worldlog import WorldLogWriter
from workbench.simulation.engine.attention import AttentionBook
from workbench.simulation.engine.engine import InterruptEngine
from workbench.simulation.engine.queue import EventQueue, ScheduledEvent
from workbench.simulation.entity.component import BaseComponent
from workbench.simulation.entity.context import ContextBlock
from workbench.simulation.entity.entity import ComposedEntity
from workbench.simulation.time_model import EventDrivenTimeModel

ENTITIES = ("ann", "bob", "cat")
CONVERSATION = "cnv-000001"


class LastMessageState(BaseModel):
    body: str = ""


class LastMessageComponent(BaseComponent):
    state_model = LastMessageState

    def __init__(self) -> None:
        super().__init__("last-message")
        self._state = LastMessageState()

    async def pre_act(self, spec: ActionSpec) -> ContextBlock | None:
        return ContextBlock(label="Last message", content=self._state.body)

    async def pre_observe(self, event: Event) -> ContextBlock | None:
        if isinstance(event.payload, ChatMessagePayload):
            self._state = LastMessageState(body=event.payload.body)
        return None

    def get_state(self) -> LastMessageState:
        return self._state

    def set_state(self, state: LastMessageState) -> None:
        self._state = state


class ReplyAct:
    def __init__(self, entity: str) -> None:
        self._entity = entity

    async def get_action_attempt(
        self, blocks: tuple[ContextBlock, ...], spec: ActionSpec
    ) -> EntityAction:
        last = blocks[0].content if blocks else ""
        return FreeAction(text=f"{self._entity} heard: {last}")


class ToyGmState(BaseModel):
    minter: IdMinter
    routed_messages: int = 0


class ToyGameMaster:
    """Round-robin chat: whoever follows the sender replies."""

    state_model = ToyGmState

    def __init__(self, *, max_messages: int) -> None:
        self._minter = IdMinter()
        self._max_messages = max_messages
        self._routed_messages = 0

    def get_state(self) -> ToyGmState:
        return ToyGmState(minter=self._minter, routed_messages=self._routed_messages)

    def set_state(self, state: ToyGmState) -> None:
        self._minter = state.minter
        self._routed_messages = state.routed_messages

    async def route(self, event: Event) -> tuple[str, ...]:
        if not isinstance(event.payload, ChatMessagePayload):
            return ()
        self._routed_messages += 1
        return tuple(e for e in ENTITIES if e != event.source)

    async def next_acting(self, event: Event) -> NextActingDecision:
        if not isinstance(event.payload, ChatMessagePayload):
            return NextActingDecision(entities=())
        if self._routed_messages >= self._max_messages:
            return NextActingDecision(entities=())
        index = ENTITIES.index(event.source)
        return NextActingDecision(entities=(ENTITIES[(index + 1) % len(ENTITIES)],))

    async def action_spec_for(self, entity: str, event: Event) -> ActionSpec:
        return FreeActionSpec(
            call_to_action="Reply in the channel.", tag="chat.message"
        )

    async def resolve(
        self, entity: str, action: EntityAction, spec: ActionSpec, event: Event
    ) -> ResolutionDecision:
        assert isinstance(action, FreeAction)
        payload = ChatMessagePayload(
            kind="chat.message",
            chat_message_id=self._minter.mint("chm"),
            conversation_id=CONVERSATION,
            reply_to=None,
            sender=f"per-{entity}",
            body=action.text,
        )
        draft = EventDraft(
            tag=payload.kind,
            source=entity,
            caused_by=event.event_id,
            payload=payload,
            delay=SimDuration(60),
        )
        return ResolutionDecision(drafts=(draft,))

    async def should_terminate(self) -> TerminateDecision:
        if self._routed_messages >= self._max_messages:
            return TerminateDecision(terminate=True, reason="message quota reached")
        return TerminateDecision(terminate=False, reason="under quota")


def genesis_events() -> list[Event]:
    payloads = [
        SimRunStartedPayload(
            kind="sim.run.started",
            run_id="run-toy",
            seed_root=7,
            workplace_id="toy",
            config_hash="0" * 64,
            schema_version=1,
            epoch="2026-03-12T00:00:00+00:00",
            timezone="UTC",
        ),
        *[
            PersonRecordPayload(
                kind="person.record",
                person_id=f"per-{name}",
                name=name.title(),
                email_address=f"{name}@example.com",
                title="Analyst",
                department="Ops",
                manager=None,
                affiliation="internal",
                timezone="UTC",
            )
            for name in ENTITIES
        ],
        ChatConversationCreatedPayload(
            kind="chat.conversation.created",
            conversation_id=CONVERSATION,
            conversation_type="channel",
            name="#toy",
            members=tuple(f"per-{name}" for name in ENTITIES),
        ),
    ]
    return [
        Event(seq=seq, time=0, tag=p.kind, source="gm", payload=p)
        for seq, p in enumerate(payloads)
    ]


def kickoff_draft() -> EventDraft:
    payload = ChatMessagePayload(
        kind="chat.message",
        chat_message_id="chm-kickoff",
        conversation_id=CONVERSATION,
        reply_to=None,
        sender="per-ann",
        body="kickoff",
    )
    return EventDraft(tag=payload.kind, source="ann", payload=payload)


def make_entities() -> tuple[ComposedEntity, ...]:
    return tuple(
        ComposedEntity(
            name=name,
            components=(LastMessageComponent(),),
            act_component=ReplyAct(name),
        )
        for name in ENTITIES
    )


def resume_toy_engine(
    log_path: Path, snapshot, *, max_messages: int = 4
) -> tuple[InterruptEngine, WorldLogWriter]:
    writer = WorldLogWriter.append_to(
        log_path,
        next_seq=snapshot.engine.next_seq,
        last_time=snapshot.engine.time.now,
    )
    engine = InterruptEngine(
        entities=make_entities(),
        game_master=ToyGameMaster(max_messages=max_messages),
        time_model=EventDrivenTimeModel(now=SimTime(0)),
        queue=EventQueue(),
        attention=AttentionBook(entities=ENTITIES),
        world_log=writer,
        next_seq=0,
        next_order=0,
    )
    engine.restore_state(snapshot.engine)
    return engine, writer


def build_engine(
    log_path: Path, *, max_messages: int = 4
) -> tuple[InterruptEngine, WorldLogWriter]:
    writer = WorldLogWriter(log_path)
    writer.__enter__()
    genesis = genesis_events()
    for event in genesis:
        writer.append(event)
    queue = EventQueue()
    queue.push(ScheduledEvent(time=60, order=0, draft=kickoff_draft()))
    engine = InterruptEngine(
        entities=make_entities(),
        game_master=ToyGameMaster(max_messages=max_messages),
        time_model=EventDrivenTimeModel(now=SimTime(0)),
        queue=queue,
        attention=AttentionBook(entities=ENTITIES),
        world_log=writer,
        next_seq=len(genesis),
        next_order=1,
    )
    return engine, writer


class ExplodingGameMaster(ToyGameMaster):
    """Raises during resolution of the given step to test commit atomicity."""

    def __init__(self, *, max_messages: int, explode_on_step: int) -> None:
        super().__init__(max_messages=max_messages)
        self._explode_on_step = explode_on_step
        self._resolve_calls = 0

    async def resolve(self, entity, action, spec, event):
        if self._resolve_calls == self._explode_on_step:
            raise RuntimeError("boom")
        self._resolve_calls += 1
        return await super().resolve(entity, action, spec, event)


def _make_toy_gm(max_messages: int, explode_on_step: int | None) -> ToyGameMaster:
    if explode_on_step is not None:
        return ExplodingGameMaster(
            max_messages=max_messages, explode_on_step=explode_on_step
        )
    return ToyGameMaster(max_messages=max_messages)


def _store_engine(
    store: SqliteRunStore,
    gm: ToyGameMaster,
    entities: tuple[ComposedEntity, ...],
    queue: EventQueue,
    *,
    now: int,
    next_seq: int,
    next_order: int,
    step: int,
) -> InterruptEngine:
    return InterruptEngine(
        entities=entities,
        game_master=gm,
        time_model=EventDrivenTimeModel(now=SimTime(now)),
        queue=queue,
        attention=AttentionBook(entities=ENTITIES),
        store=store,
        next_seq=next_seq,
        next_order=next_order,
        step=step,
    )


def build_store_engine(
    store_path: Path,
    *,
    max_messages: int = 4,
    explode_on_step: int | None = None,
) -> tuple[InterruptEngine, SqliteRunStore]:
    store = SqliteRunStore.create(store_path)
    for event in genesis_events():
        store.append_event(event)
    kickoff = ScheduledEvent(time=60, order=0, draft=kickoff_draft())
    store.queue_add(time=kickoff.time, order=kickoff.order, draft=kickoff.draft)
    store.set_meta("step", "0")
    store.set_meta("next_order", "1")
    store.commit()
    queue = EventQueue()
    queue.push(kickoff)
    engine = _store_engine(
        store,
        _make_toy_gm(max_messages, explode_on_step),
        make_entities(),
        queue,
        now=0,
        next_seq=len(genesis_events()),
        next_order=1,
        step=0,
    )
    return engine, store


async def resume_store_engine(
    store: SqliteRunStore, *, max_messages: int = 4
) -> InterruptEngine:
    """Rebuild runtime state from the store: entity folds by replaying the
    committed events through a throwaway router, the GM from its committed
    state, counters and queue from the store."""

    entities = make_entities()
    router = ToyGameMaster(max_messages=max_messages)
    by_name = {entity.name: entity for entity in entities}
    for event in store.read_events():
        for name in await router.route(event):
            if name in by_name:
                await by_name[name].observe(event)

    gm = ToyGameMaster(max_messages=max_messages)
    gm_state = store.get_meta("gm_state")
    if gm_state is not None:
        gm.set_state(gm.state_model.model_validate_json(gm_state))

    queue = EventQueue()
    for time, order, draft in store.queue_rows():
        queue.push(ScheduledEvent(time=time, order=order, draft=draft))

    return _store_engine(
        store,
        gm,
        entities,
        queue,
        now=store.head()[1],
        next_seq=store.head()[0],
        next_order=int(store.get_meta("next_order") or "0"),
        step=int(store.get_meta("step") or "0"),
    )
