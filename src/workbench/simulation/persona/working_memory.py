"""The persona's private fold of everything it has observed.

Grounding, not memory: the fold is the observed events themselves, so every
derived view is exactly consistent with the world log — a persona cannot
drift from the record. The facts ledger accumulates what this persona has
itself said, and drafts must not contradict it.

Snapshots carry event *ids*, not events: the world log is the single copy of
every event, and a restored component is rehydrated from it. Until
rehydration happens, reads fail loud rather than acting on empty memory.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.actions import ActionSpec, EntityAction, IntentAction
from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.tickets import TicketCreatedPayload
from workbench.core.intents import (
    ChatIntent,
    DocumentEditIntent,
    EmailIntent,
    TicketIntent,
)
from workbench.simulation.entity.component import BaseComponent
from workbench.simulation.entity.context import ContextBlock
from workbench.simulation.errors import SnapshotError


class PendingItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    channel: str
    summary: str
    age_minutes: int = Field(ge=0)


# A long history accumulates unreplied mail without bound; a real person
# works from the top of the inbox. The persona sees at most this many
# pending items — the youngest ones, in stable order. Below the cap the
# view is exactly the old one, which keeps recorded prompts byte-stable.
PENDING_CAP = 20


class WorkingMemoryState(BaseModel):
    event_ids: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()


class WorkingMemoryComponent(BaseComponent):
    state_model = WorkingMemoryState

    def __init__(self, *, person_id: str) -> None:
        super().__init__("working-memory")
        self._person_id = person_id
        self._events: tuple[Event, ...] = ()
        self._facts: tuple[str, ...] = ()
        self._awaiting_ids: tuple[str, ...] | None = None

    def _require_hydrated(self) -> tuple[Event, ...]:
        if self._awaiting_ids is not None:
            raise SnapshotError(
                "working memory restored from ids but never rehydrated; "
                "call rehydrate(events_by_id) with the run's event store"
            )
        return self._events

    async def pre_observe(self, event: Event) -> None:
        self._require_hydrated()
        self._events = (*self._events, event)
        return None

    async def pre_act(self, spec: ActionSpec) -> ContextBlock | None:
        events = self._require_hydrated()
        now = self.last_time()
        clock = f"{now // 3600:02d}:{(now % 3600) // 60:02d}"
        documents = [
            e.payload.path
            for e in events
            if isinstance(e.payload, DocumentCreatedPayload)
        ]
        tickets = [
            f"{e.payload.ticket_id}: {e.payload.title}"
            for e in events
            if isinstance(e.payload, TicketCreatedPayload)
        ]
        channels = [
            e.payload.name or e.payload.conversation_id
            for e in events
            if isinstance(e.payload, ChatConversationCreatedPayload)
            and self._person_id in e.payload.members
        ]
        lines = [f"Current time: about {clock}."]
        if documents:
            lines.append("Documents you know of: " + "; ".join(documents))
        if tickets:
            lines.append("Tickets you know of: " + "; ".join(tickets))
        if channels:
            lines.append("Chat channels you can post in: " + "; ".join(channels))
        total = len(self._pending_all())
        if total > PENDING_CAP:
            lines.append(
                f"You have {PENDING_CAP}+ pending item(s) (showing the "
                f"{PENDING_CAP} most recent)."
            )
        else:
            lines.append(f"You have {total} pending item(s).")
        return ContextBlock(label="Situation", content="\n".join(lines))

    async def post_act(self, action: EntityAction) -> None:
        if not isinstance(action, IntentAction):
            return
        intent = action.intent
        fact: str | None = None
        if isinstance(intent, EmailIntent | ChatIntent):
            fact = intent.draft.summary
        elif isinstance(intent, TicketIntent):
            if intent.create is not None:
                fact = f"Opened ticket: {intent.create.title}"
            elif intent.comment:
                fact = f"Commented on {intent.ticket_ref}: {intent.comment[:80]}"
            elif intent.changes:
                fact = f"Updated {intent.ticket_ref}"
        elif isinstance(intent, DocumentEditIntent):
            if intent.edit is not None:
                fact = f"Revised {intent.document_ref}: {intent.edit.change_summary}"
            elif intent.create is not None:
                fact = f"Created document: {intent.create.title}"
        if fact is not None:
            self._facts = (*self._facts, fact)

    def events(self) -> tuple[Event, ...]:
        return self._require_hydrated()

    def facts(self) -> tuple[str, ...]:
        return self._facts

    def restore_facts(self, facts: tuple[str, ...]) -> None:
        """Roll-forward resume: facts are the persona's own action
        summaries — they appear in no world event, so a rebuild without a
        snapshot restores them from the run's durable metadata."""

        self._facts = tuple(facts)

    def last_time(self) -> int:
        events = self._require_hydrated()
        if not events:
            return 0
        return int(events[-1].time)

    def resolve_thread_ref(self, ref: str) -> str | None:
        """Accept a thread id or a message id; return the thread id."""
        for event in self._require_hydrated():
            payload = event.payload
            if isinstance(payload, EmailMessagePayload):
                if payload.thread_id == ref:
                    return ref
                if payload.message_id == ref:
                    return payload.thread_id
        return None

    def pending_items(self) -> tuple[PendingItem, ...]:
        """The bounded view every prompt surface consumes."""

        items = self._pending_all()
        if len(items) <= PENDING_CAP:
            return items
        youngest = sorted(
            range(len(items)), key=lambda index: (items[index].age_minutes, index)
        )[:PENDING_CAP]
        return tuple(items[index] for index in sorted(youngest))

    def _pending_all(self) -> tuple[PendingItem, ...]:
        events = self._require_hydrated()
        now = self.last_time()
        items: list[PendingItem] = []

        replied_to = {
            e.payload.in_reply_to
            for e in events
            if isinstance(e.payload, EmailMessagePayload)
            and e.payload.sender == self._person_id
            and e.payload.in_reply_to is not None
        }
        for event in events:
            payload = event.payload
            if (
                isinstance(payload, EmailMessagePayload)
                and self._person_id in (*payload.to, *payload.cc)
                and payload.message_id not in replied_to
            ):
                items.append(
                    PendingItem(
                        ref=payload.message_id,
                        channel="email",
                        summary=payload.subject,
                        age_minutes=max(0, (now - int(event.time)) // 60),
                    )
                )

        my_conversations = {
            e.payload.conversation_id
            for e in events
            if isinstance(e.payload, ChatConversationCreatedPayload)
            and self._person_id in e.payload.members
        }
        for conversation_id in sorted(my_conversations):
            last_message: ChatMessagePayload | None = None
            last_time = 0
            answered = True
            for event in events:
                payload = event.payload
                if (
                    isinstance(payload, ChatMessagePayload)
                    and payload.conversation_id == conversation_id
                ):
                    if payload.sender == self._person_id:
                        answered = True
                    else:
                        last_message = payload
                        last_time = int(event.time)
                        answered = False
            if last_message is not None and not answered:
                items.append(
                    PendingItem(
                        ref=conversation_id,
                        channel="chat",
                        summary=last_message.body[:80],
                        age_minutes=max(0, (now - last_time) // 60),
                    )
                )
        return tuple(items)

    def get_state(self) -> WorkingMemoryState:
        events = self._require_hydrated()
        return WorkingMemoryState(
            event_ids=tuple(str(e.event_id) for e in events),
            facts=self._facts,
        )

    def set_state(self, state: WorkingMemoryState) -> None:
        self._facts = state.facts
        self._events = ()
        # An empty memory needs nothing from the store.
        self._awaiting_ids = state.event_ids or None

    def rehydrate(self, events_by_id: Mapping[str, Event]) -> None:
        if self._awaiting_ids is None:
            return
        missing = [i for i in self._awaiting_ids if i not in events_by_id]
        if missing:
            raise SnapshotError(
                f"cannot rehydrate working memory: {len(missing)} event id(s) "
                f"absent from the store, first {missing[0]!r}"
            )
        self._events = tuple(events_by_id[i] for i in self._awaiting_ids)
        self._awaiting_ids = None
