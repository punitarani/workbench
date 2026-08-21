"""The persona's memory stream: every observed event folded into a
scored, retrievable record.

Records are deterministic folds over world events — the Smallville
memory-stream idea, grounded: an agent cannot remember what the world
never validated. Importance is rule-based at write time (an LM call per
observation would double a run's cost for marginal signal); reflections
and summaries arrive as ``sim.agent.memory`` events whose bullets carry
model-scored importance, and fold like everything else.

Snapshots carry event ids only (the D0 pattern): the world log is the
single copy of every event, and a restored component is rehydrated from
the store.
"""

import re
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from core.events import Event
from core.events.agent import SimAgentMemoryPayload, SimAgentPlanPayload
from core.events.calendar import CalendarEventScheduledPayload
from core.events.chat import ChatMessagePayload
from core.events.control import SimGmNotePayload
from core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from core.events.email import EmailMessagePayload
from core.events.meetings import MeetingTranscriptPayload
from core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from core.events.work import TimeLoggedPayload
from simulation.entity.component import BaseComponent
from simulation.errors import SnapshotError

# Any minted world id: prefix-NNNNNN. Scanning the canonical payload text
# is the cheapest complete way to collect the refs a record touches.
_REF_PATTERN = re.compile(r"\b[a-z]{3}-\d{6}\b")


class MemoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str  # the source event id
    kind: str
    time: int = Field(ge=0)
    importance: int = Field(ge=1, le=10)
    gist: str
    refs: frozenset[str] = frozenset()


class MemoryStreamState(BaseModel):
    event_ids: tuple[str, ...] = ()


def _clip(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class MemoryStreamComponent(BaseComponent):
    state_model = MemoryStreamState

    def __init__(self, *, person_id: str, entity_name: str) -> None:
        super().__init__("memory-stream")
        self._person_id = person_id
        self._entity_name = entity_name
        self._events: tuple[Event, ...] = ()
        self._records: list[MemoryRecord] = []
        self._by_ref: dict[str, list[int]] = {}
        self._awaiting_ids: tuple[str, ...] | None = None
        self._latest_plan: SimAgentPlanPayload | None = None
        self._urgent_since_plan = 0

    def _require_hydrated(self) -> None:
        if self._awaiting_ids is not None:
            raise SnapshotError(
                "memory stream restored from ids but never rehydrated; "
                "call rehydrate(events_by_id) with the run's event store"
            )

    async def pre_observe(self, event: Event) -> None:
        self._require_hydrated()
        self._ingest(event)
        return None

    def _ingest(self, event: Event) -> None:
        self._events = (*self._events, event)
        payload = event.payload
        if (
            isinstance(payload, SimAgentPlanPayload)
            and payload.entity == self._entity_name
        ):
            self._latest_plan = payload
            self._urgent_since_plan = 0
        for record in self._fold(event):
            index = len(self._records)
            self._records.append(record)
            for ref in record.refs:
                self._by_ref.setdefault(ref, []).append(index)
            if (
                self._latest_plan is not None
                and record.importance >= 8
                and record.kind in ("observation", "rejection")
            ):
                plan_refs = {
                    ref for block in self._latest_plan.blocks for ref in block.refs
                }
                if not (record.refs & plan_refs):
                    self._urgent_since_plan += 1

    def records(self) -> tuple[MemoryRecord, ...]:
        self._require_hydrated()
        return tuple(self._records)

    def latest_plan(self) -> SimAgentPlanPayload | None:
        self._require_hydrated()
        return self._latest_plan

    def replan_pending(self) -> bool:
        """Two or more urgent arrivals outside the plan's refs since it
        was made: the plan is stale and the next wake should replan."""

        self._require_hydrated()
        return self._latest_plan is not None and self._urgent_since_plan >= 2

    def records_touching(self, refs: frozenset[str]) -> tuple[MemoryRecord, ...]:
        """Records whose refs intersect the query, in fold order."""

        self._require_hydrated()
        indices = sorted({index for ref in refs for index in self._by_ref.get(ref, ())})
        return tuple(self._records[index] for index in indices)

    # -- folding -----------------------------------------------------------

    def _refs_of(self, event: Event) -> frozenset[str]:
        return frozenset(_REF_PATTERN.findall(event.payload.model_dump_json())) | {
            str(event.event_id)
        }

    def _fold(self, event: Event) -> tuple[MemoryRecord, ...]:
        payload = event.payload
        me = self._person_id
        base = {
            "ref": str(event.event_id),
            "time": int(event.time),
            "refs": self._refs_of(event),
        }
        match payload:
            case EmailMessagePayload():
                if me in payload.to:
                    importance = 7
                elif me in payload.cc:
                    importance = 4
                elif payload.sender == me:
                    importance = 5
                else:
                    importance = 3
                subject = payload.subject.casefold()
                if any(
                    marker in subject
                    for marker in ("urgent", "asap", "immediately", "deadline")
                ):
                    importance = min(10, importance + 2)
                sender = payload.sender
                return (
                    MemoryRecord(
                        kind="action" if payload.sender == me else "observation",
                        importance=importance,
                        gist=_clip(f"Email from {sender}: {payload.subject}"),
                        **base,
                    ),
                )
            case ChatMessagePayload():
                mentioned = me.partition("-")[2] in payload.body.casefold()
                if payload.sender == me:
                    importance, kind = 5, "action"
                elif mentioned:
                    importance, kind = 7, "observation"
                else:
                    importance, kind = 3, "observation"
                return (
                    MemoryRecord(
                        kind=kind,
                        importance=importance,
                        gist=_clip(f"Chat from {payload.sender}: {payload.body}"),
                        **base,
                    ),
                )
            case TicketCreatedPayload():
                importance = 8 if payload.assignee == me else 4
                return (
                    MemoryRecord(
                        kind="observation",
                        importance=importance,
                        gist=_clip(f"Ticket opened: {payload.title}"),
                        **base,
                    ),
                )
            case TicketUpdatedPayload() | TicketCommentedPayload():
                return (
                    MemoryRecord(
                        kind="observation",
                        importance=5,
                        gist=_clip(f"Ticket activity on {payload.ticket_id}"),
                        **base,
                    ),
                )
            case DocumentCreatedPayload() | DocumentRevisedPayload():
                title = getattr(payload, "title", payload.document_id)
                return (
                    MemoryRecord(
                        kind="action" if payload.author == me else "observation",
                        importance=4,
                        gist=_clip(f"Document saved: {title}"),
                        **base,
                    ),
                )
            case CalendarEventScheduledPayload():
                return (
                    MemoryRecord(
                        kind="observation",
                        importance=5,
                        gist=_clip(f"Meeting scheduled: {payload.title}"),
                        **base,
                    ),
                )
            case MeetingTranscriptPayload():
                return (
                    MemoryRecord(
                        kind="observation",
                        importance=8,
                        gist=_clip(f"Meeting held with {len(payload.turns)} turns"),
                        **base,
                    ),
                )
            case TimeLoggedPayload():
                if payload.person_id != me:
                    return ()
                return (
                    MemoryRecord(
                        kind="action",
                        importance=3,
                        gist=_clip(f"Logged {payload.minutes}m: {payload.note}"),
                        **base,
                    ),
                )
            case SimGmNotePayload():
                if payload.entity != self._entity_name:
                    return ()
                # `guidance`, never `note`. `note` is the operator's text and
                # carries engine diagnostics; this is a memory at importance
                # 10, the highest the world has, so whatever goes in here is
                # retrieved ahead of everything the person actually did. It
                # used to be `note`, and a pydantic validation dump became
                # the most important thing several lawyers knew.
                #
                # Empty guidance means the refusal was the engine's fault and
                # there was no different thing the person could have done, so
                # they remember nothing -- the alternative is an instruction
                # that cannot be followed, outranking real memories forever.
                if not payload.guidance:
                    return ()
                return (
                    MemoryRecord(
                        kind="rejection",
                        importance=10,
                        gist=_clip(payload.guidance, 110),
                        **base,
                    ),
                )
            case SimAgentMemoryPayload():
                if payload.entity != self._entity_name:
                    return ()
                kind = (
                    "summary" if payload.note_kind.endswith("summary") else "reflection"
                )
                return tuple(
                    MemoryRecord(
                        ref=str(event.event_id),
                        kind=kind,
                        time=int(event.time),
                        importance=bullet.importance,
                        gist=_clip(bullet.text, 110),
                        refs=frozenset(bullet.refs) | {str(event.event_id)},
                    )
                    for bullet in payload.bullets
                )
            case SimAgentPlanPayload():
                if payload.entity != self._entity_name:
                    return ()
                focus = "; ".join(block.focus for block in payload.blocks[:3])
                return (
                    MemoryRecord(
                        kind="plan_note",
                        importance=6,
                        gist=_clip(f"Planned the day: {focus}", 110),
                        **base,
                    ),
                )
            case _:
                return ()

    # -- snapshots ---------------------------------------------------------

    def get_state(self) -> MemoryStreamState:
        self._require_hydrated()
        return MemoryStreamState(
            event_ids=tuple(str(event.event_id) for event in self._events)
        )

    def set_state(self, state: MemoryStreamState) -> None:
        self._events = ()
        self._records = []
        self._by_ref = {}
        self._awaiting_ids = state.event_ids or None
        self._latest_plan = None
        self._urgent_since_plan = 0

    def rehydrate(self, events_by_id: Mapping[str, Event]) -> None:
        if self._awaiting_ids is None:
            return
        missing = [i for i in self._awaiting_ids if i not in events_by_id]
        if missing:
            raise SnapshotError(
                f"cannot rehydrate memory stream: {len(missing)} event id(s) "
                f"absent from the store, first {missing[0]!r}"
            )
        pending = self._awaiting_ids
        self._awaiting_ids = None
        for event_id in pending:
            self._ingest(events_by_id[event_id])
