"""The sliding window: parallel acts, canonical bytes.

Admission takes the maximal conflict-free prefix of same-time queue items,
so the committed sequence — and therefore the world log — is identical for
every window size. That invariance is the whole guarantee, and the last
test states it as bytes.
"""

from pathlib import Path

from mini_workplace import ann_params, make_spec
from pydantic import BaseModel, ConfigDict
from test_workplace import DECIDE_IDLE_FALLBACK, SequenceLM

from workbench.core.actions import ActionSpec, EntityAction, IntentActionSpec
from workbench.core.events import Event, EventDraft
from workbench.core.events.control import SimRunStartedPayload, SimWakePayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.seed import Seed
from workbench.core.store import SqliteRunStore
from workbench.simulation.engine.attention import AttentionBook
from workbench.simulation.engine.engine import InterruptEngine
from workbench.simulation.engine.queue import EventQueue, ScheduledEvent
from workbench.simulation.gm.game_master import (
    NextActingDecision,
    ResolutionDecision,
    TerminateDecision,
)
from workbench.simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from workbench.simulation.run import run_workplace
from workbench.simulation.time_model import EventDrivenTimeModel
from workbench.simulation.workplace.spec import ExogenousEmail, PersonSpec


class _NullState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class QuietGm:
    """A protocol-complete GM that routes nowhere and grants no turns —
    admission behavior is driven purely by footprints."""

    state_model = _NullState

    def get_state(self) -> _NullState:
        return _NullState()

    def set_state(self, state: _NullState) -> None:
        pass

    def observers_for(self, payload) -> tuple[str, ...]:
        return ()

    async def route(self, event: Event) -> tuple[str, ...]:
        return ()

    async def next_acting(self, event: Event) -> NextActingDecision:
        return NextActingDecision(entities=())

    async def action_spec_for(self, entity: str, event: Event) -> ActionSpec:
        return IntentActionSpec(call_to_action="act")

    async def resolve(
        self, entity: str, action: EntityAction, spec: ActionSpec, event: Event
    ) -> ResolutionDecision:
        return ResolutionDecision(drafts=())

    async def consequences(self, event: Event) -> tuple[EventDraft, ...]:
        return ()

    async def should_terminate(self) -> TerminateDecision:
        return TerminateDecision(terminate=False, reason="")


def _wake(entity: str) -> EventDraft:
    payload = SimWakePayload(kind="sim.wake", entity=entity)
    return EventDraft(tag=payload.kind, source="gm", payload=payload)


def _arrival() -> EventDraft:
    payload = PersonRecordPayload(
        kind="person.record",
        person_id="per-new",
        name="New Person",
        email_address="new@x.example",
        title="t",
        department="d",
        manager=None,
        affiliation="external",
        timezone="UTC",
    )
    return EventDraft(tag=payload.kind, source="gm", payload=payload)


def _engine(store_path: Path, drafts: list[EventDraft]) -> InterruptEngine:
    store = SqliteRunStore.create(store_path)
    genesis = Event(
        seq=0,
        time=0,
        tag="sim.run.started",
        source="gm",
        payload=SimRunStartedPayload(
            kind="sim.run.started",
            run_id="run-window",
            seed_root=1,
            workplace_id="w",
            config_hash="0" * 64,
            schema_version=1,
            epoch="2026-03-12T00:00:00+00:00",
            timezone="UTC",
        ),
    )
    store.append_event(genesis)
    queue = EventQueue()
    for order, draft in enumerate(drafts):
        item = ScheduledEvent(time=60, order=order, draft=draft)
        queue.push(item)
        store.queue_add(time=item.time, order=item.order, draft=item.draft)
    store.commit()
    return InterruptEngine(
        entities=(),
        game_master=QuietGm(),
        time_model=EventDrivenTimeModel(now=0),
        queue=queue,
        attention=AttentionBook(entities=()),
        store=store,
        next_seq=1,
        next_order=len(drafts),
    )


async def test_disjoint_same_time_items_batch_together(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "run.db", [_wake("a"), _wake("b"), _wake("a")])
    first = await engine.step_batch(8)
    assert [r.event.payload.entity for r in first] == ["a", "b"], (
        "disjoint wakes share a batch; the second 'a' conflicts"
    )
    second = await engine.step_batch(8)
    assert [r.event.payload.entity for r in second] == ["a"]
    assert engine.queue_length() == 0


async def test_barriers_execute_alone(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "run.db", [_wake("a"), _arrival(), _wake("b")])
    assert len(await engine.step_batch(8)) == 1, "batch stops before a barrier"
    barrier = await engine.step_batch(8)
    assert [r.event.tag for r in barrier] == ["person.record"]
    assert len(await engine.step_batch(8)) == 1


def wide_spec():
    """Three personas and two same-time emails from distinct outside
    senders to distinct personas: a genuinely batchable moment."""

    def persona(person_id: str, name: str, email: str) -> PersonSpec:
        return PersonSpec(
            person_id=person_id,
            name=name,
            email_address=email,
            title="Counsel",
            department="Legal",
            manager=None,
            affiliation="internal",
            persona=ann_params().model_copy(
                update={"person_id": person_id, "name": name}
            ),
        )

    def outsider(person_id: str, name: str, email: str) -> PersonSpec:
        return PersonSpec(
            person_id=person_id,
            name=name,
            email_address=email,
            title="Outside Counsel",
            department="External",
            manager=None,
            affiliation="external",
            persona=None,
        )

    base = make_spec()
    return make_spec(
        people=(
            *base.people,
            persona("per-bob-tran", "Bob Tran", "bob@mini.example"),
            persona("per-cara-diaz", "Cara Diaz", "cara@mini.example"),
            outsider("per-sara-oni", "Sara Oni", "sara@outside.example"),
        ),
        day_script=(
            *base.day_script,
            ExogenousEmail(
                at="10:00",
                sender="per-ravi-dee",
                to=("per-bob-tran",),
                cc=(),
                subject="Status check",
                body="Any update?",
            ),
            ExogenousEmail(
                at="10:00",
                sender="per-sara-oni",
                to=("per-cara-diaz",),
                cc=(),
                subject="Intro call",
                body="Could we speak this week?",
            ),
        ),
    )


async def test_window_invariance_is_byte_identical(tmp_path: Path) -> None:
    cassette = CassetteStore(tmp_path / "cassette")
    baseline = tmp_path / "w1"
    await run_workplace(
        wide_spec(),
        seed=Seed(root=42),
        out_dir=baseline,
        inner_lm=RecordingLM(SequenceLM([DECIDE_IDLE_FALLBACK]), cassette),
        model="test/model",
        window=1,
    )
    reference = (baseline / "world.jsonl").read_bytes()
    for window in (4, 16):
        out_dir = tmp_path / f"w{window}"
        result = await run_workplace(
            wide_spec(),
            seed=Seed(root=42),
            out_dir=out_dir,
            inner_lm=ReplayLM(cassette),
            model="test/model",
            window=window,
        )
        assert result.reason == "quiescent"
        assert (out_dir / "world.jsonl").read_bytes() == reference, (
            f"window={window} diverged from the sequential log"
        )
