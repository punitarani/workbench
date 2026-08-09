"""The persona's private fold of everything it has observed.

Grounding, not memory: state is the observed events themselves, so every
derived view is exactly consistent with the world log — a persona cannot
drift from the record. The facts ledger accumulates what this persona has
itself said, and drafts must not contradict it.
"""

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
from workbench.core.intents import ChatIntent, EmailIntent
from workbench.simulation.entity.component import BaseComponent
from workbench.simulation.entity.context import ContextBlock


class PendingItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    channel: str
    summary: str
    age_minutes: int = Field(ge=0)


class WorkingMemoryState(BaseModel):
    events: tuple[Event, ...] = ()
    facts: tuple[str, ...] = ()


class WorkingMemoryComponent(BaseComponent):
    state_model = WorkingMemoryState

    def __init__(self, *, person_id: str) -> None:
        super().__init__("working-memory")
        self._person_id = person_id
        self._state = WorkingMemoryState()

    async def pre_observe(self, event: Event) -> None:
        self._state = self._state.model_copy(
            update={"events": (*self._state.events, event)}
        )
        return None

    async def pre_act(self, spec: ActionSpec) -> ContextBlock | None:
        now = self.last_time()
        clock = f"{now // 3600:02d}:{(now % 3600) // 60:02d}"
        documents = [
            e.payload.path
            for e in self._state.events
            if isinstance(e.payload, DocumentCreatedPayload)
        ]
        tickets = [
            f"{e.payload.ticket_id}: {e.payload.title}"
            for e in self._state.events
            if isinstance(e.payload, TicketCreatedPayload)
        ]
        lines = [f"Current time: about {clock}."]
        if documents:
            lines.append("Documents you know of: " + "; ".join(documents))
        if tickets:
            lines.append("Tickets you know of: " + "; ".join(tickets))
        lines.append(f"You have {len(self.pending_items())} pending item(s).")
        return ContextBlock(label="Situation", content="\n".join(lines))

    async def post_act(self, action: EntityAction) -> None:
        if not isinstance(action, IntentAction):
            return
        intent = action.intent
        if isinstance(intent, EmailIntent | ChatIntent):
            self._state = self._state.model_copy(
                update={"facts": (*self._state.facts, intent.draft.summary)}
            )

    def events(self) -> tuple[Event, ...]:
        return self._state.events

    def facts(self) -> tuple[str, ...]:
        return self._state.facts

    def last_time(self) -> int:
        if not self._state.events:
            return 0
        return int(self._state.events[-1].time)

    def resolve_thread_ref(self, ref: str) -> str | None:
        """Accept a thread id or a message id; return the thread id."""
        for event in self._state.events:
            payload = event.payload
            if isinstance(payload, EmailMessagePayload):
                if payload.thread_id == ref:
                    return ref
                if payload.message_id == ref:
                    return payload.thread_id
        return None

    def pending_items(self) -> tuple[PendingItem, ...]:
        now = self.last_time()
        items: list[PendingItem] = []

        replied_to = {
            e.payload.in_reply_to
            for e in self._state.events
            if isinstance(e.payload, EmailMessagePayload)
            and e.payload.sender == self._person_id
            and e.payload.in_reply_to is not None
        }
        for event in self._state.events:
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
            for e in self._state.events
            if isinstance(e.payload, ChatConversationCreatedPayload)
            and self._person_id in e.payload.members
        }
        for conversation_id in sorted(my_conversations):
            last_message: ChatMessagePayload | None = None
            last_time = 0
            answered = True
            for event in self._state.events:
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
        return self._state

    def set_state(self, state: WorkingMemoryState) -> None:
        self._state = state
