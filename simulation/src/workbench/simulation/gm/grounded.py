"""The grounded game master: typed intents in, typed world events out.

Fully deterministic in v1 — reference resolution, validation, and routing are
code, not model calls. Unresolvable intents become sim.gm.note events, so a
run never wedges and every rejection is visible in the log. LM-backed repair
(RepairIntent, ResolveFreeform) is a named future optimization target.
"""

from pydantic import BaseModel

from workbench.core.actions import (
    ActionSpec,
    EntityAction,
    IntentAction,
    IntentActionSpec,
    NextActingDecision,
    ResolutionDecision,
    TerminateDecision,
)
from workbench.core.events import Event, EventDraft
from workbench.core.events.calendar import CalendarResponsePayload
from workbench.core.events.chat import ChatMessagePayload
from workbench.core.events.control import SimGmNotePayload, SimWakePayload
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.ids import IdMinter
from workbench.core.intents import (
    ActionIntent,
    CalendarIntent,
    ChatIntent,
    DocumentEditIntent,
    EmailIntent,
    FreeformIntent,
    IdleIntent,
    TicketIntent,
)
from workbench.core.simtime import SimDuration
from workbench.simulation.gm.timeflow import intent_duration
from workbench.simulation.gm.world_state import WorldState


class TicketVocabulary(BaseModel):
    statuses: tuple[str, ...]
    priorities: tuple[str, ...]
    ticket_types: tuple[str, ...]


class IntentRejection(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class GroundedGmState(BaseModel):
    minter: IdMinter


class GroundedGm:
    state_model = GroundedGmState

    def __init__(
        self,
        *,
        entity_for_person: dict[str, str],
        ticket_vocabulary: TicketVocabulary,
        response_delay_seconds: int = 120,
    ) -> None:
        self._world = WorldState()
        self._minter = IdMinter()
        self._entity_for_person = dict(entity_for_person)
        self._person_for_entity = {
            entity: person for person, entity in entity_for_person.items()
        }
        self._vocab = ticket_vocabulary
        self._response_delay = response_delay_seconds

    @property
    def world(self) -> WorldState:
        return self._world

    def rebuild(self, events) -> None:
        for event in events:
            self._world.apply(event)
            self._absorb_event(event)

    def _absorb_event(self, event: Event) -> None:
        for value in event.payload.model_dump(mode="json").values():
            self._absorb_id(value)

    def _absorb_id(self, value) -> None:
        """Advance minter counters past any pre-existing prefix-NNNNNN id."""
        if isinstance(value, str):
            prefix, dash, digits = value.rpartition("-")
            if dash and prefix.isalpha() and digits.isdigit() and len(digits) == 6:
                current = self._minter.counters.get(prefix, 0)
                self._minter.counters[prefix] = max(current, int(digits))
        elif isinstance(value, list):
            for item in value:
                self._absorb_id(item)

    def get_state(self) -> GroundedGmState:
        return GroundedGmState(minter=self._minter)

    def set_state(self, state: GroundedGmState) -> None:
        self._minter = state.minter

    def _entities_for(self, person_ids) -> tuple[str, ...]:
        seen: list[str] = []
        for person_id in person_ids:
            entity = self._entity_for_person.get(person_id)
            if entity is not None and entity not in seen:
                seen.append(entity)
        return tuple(seen)

    async def route(self, event: Event) -> tuple[str, ...]:
        self._world.apply(event)
        self._absorb_event(event)
        payload = event.payload
        match payload:
            case SimWakePayload():
                # The persona observes its own wake so its clock advances.
                if payload.entity in self._person_for_entity:
                    return (payload.entity,)
                return ()
            case EmailMessagePayload():
                recipients = self._entities_for((*payload.to, *payload.cc))
                return tuple(r for r in recipients if r != event.source)
            case ChatMessagePayload():
                members = self._world.conversations.get(payload.conversation_id, ())
                observers = self._entities_for(members)
                return tuple(o for o in observers if o != event.source)
            case TicketCreatedPayload():
                watchers = self._entities_for(
                    (payload.requester, payload.assignee, payload.actor)
                )
                return tuple(w for w in watchers if w != event.source)
            case TicketUpdatedPayload() | TicketCommentedPayload():
                values = self._world.tickets.get(payload.ticket_id, {})
                watchers = self._entities_for(
                    (values.get("assignee"), payload.actor)
                )
                return tuple(w for w in watchers if w != event.source)
            case DocumentCreatedPayload() | DocumentRevisedPayload():
                return ()
            case _:
                return ()

    async def next_acting(self, event: Event) -> NextActingDecision:
        payload = event.payload
        match payload:
            case SimWakePayload():
                if payload.entity in self._person_for_entity:
                    return NextActingDecision(entities=(payload.entity,))
                return NextActingDecision(entities=())
            case EmailMessagePayload():
                # Deep chains stop granting automatic reply turns; a wake
                # turn can always revive a thread deliberately. Without this
                # cap, courteous personas acknowledge each other forever.
                depth = self._world.message_depth.get(payload.message_id, 0)
                if depth >= 3:
                    return NextActingDecision(entities=())
                for person_id in payload.to:
                    entity = self._entity_for_person.get(person_id)
                    if entity is not None and entity != event.source:
                        return NextActingDecision(entities=(entity,))
                return NextActingDecision(entities=())
            case ChatMessagePayload():
                members = self._world.conversations.get(payload.conversation_id, ())
                body = payload.body.casefold()
                if len(members) == 2:
                    others = self._entities_for(
                        m for m in members if m != payload.sender
                    )
                    return NextActingDecision(entities=others[:1])
                for person_id in members:
                    if person_id == payload.sender:
                        continue
                    record = self._world.people.get(person_id)
                    if record is None:
                        continue
                    first_name = record.name.split()[0].casefold()
                    if first_name in body:
                        entities = self._entities_for((person_id,))
                        if entities:
                            return NextActingDecision(entities=entities)
                return NextActingDecision(entities=())
            case TicketCreatedPayload():
                if payload.assignee and payload.assignee != payload.actor:
                    return NextActingDecision(
                        entities=self._entities_for((payload.assignee,))
                    )
                return NextActingDecision(entities=())
            case _:
                return NextActingDecision(entities=())

    async def action_spec_for(self, entity: str, event: Event) -> ActionSpec:
        return IntentActionSpec(
            call_to_action=(
                "Something needs your attention. Decide your next workplace "
                "action and produce it."
            )
        )

    async def resolve(
        self, entity: str, action: EntityAction, spec: ActionSpec, event: Event
    ) -> ResolutionDecision:
        try:
            intent = self._extract_intent(action)
            drafts = self._ground(entity, intent, event)
        except IntentRejection as rejection:
            note = SimGmNotePayload(
                kind="sim.gm.note",
                note=f"Rejected action from {entity}: {rejection.reason}",
                rejected_intent=_intent_summary(action),
            )
            return ResolutionDecision(
                drafts=(
                    EventDraft(
                        tag=note.kind,
                        source="gm",
                        caused_by=event.event_id,
                        payload=note,
                    ),
                )
            )
        return ResolutionDecision(drafts=drafts)

    async def should_terminate(self) -> TerminateDecision:
        return TerminateDecision(terminate=False, reason="runs until quiescent")

    def _extract_intent(self, action: EntityAction) -> ActionIntent:
        if not isinstance(action, IntentAction):
            raise IntentRejection(
                f"expected a typed intent, got {action.kind} action"
            )
        if isinstance(action.intent, FreeformIntent):
            raise IntentRejection(
                f"freeform intents are not grounded yet: {action.intent.text[:80]}"
            )
        return action.intent

    def _person_for(self, entity: str) -> str:
        person = self._person_for_entity.get(entity)
        if person is None:
            raise IntentRejection(f"entity {entity} has no person record")
        return person

    def _resolve_people(self, refs) -> tuple[str, ...]:
        resolved: list[str] = []
        for ref in refs:
            person = self._world.resolve_person(ref)
            if person is None:
                raise IntentRejection(f"unknown person {ref!r}")
            if person not in resolved:
                resolved.append(person)
        return tuple(resolved)

    def _ground(
        self, entity: str, intent: ActionIntent, event: Event
    ) -> tuple[EventDraft, ...]:
        delay = SimDuration(intent_duration(intent))
        sender = self._person_for(entity)
        match intent:
            case IdleIntent():
                return ()
            case EmailIntent():
                return self._ground_email(entity, sender, intent, event, delay)
            case ChatIntent():
                return self._ground_chat(entity, sender, intent, event, delay)
            case TicketIntent():
                return self._ground_ticket(entity, sender, intent, event, delay)
            case DocumentEditIntent():
                return self._ground_document(entity, sender, intent, event, delay)
            case CalendarIntent():
                return self._ground_calendar(entity, sender, intent, event, delay)
            case _:
                raise IntentRejection(f"unsupported intent kind {intent.kind}")

    def _ground_email(
        self, entity, sender, intent: EmailIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        to = self._resolve_people(intent.draft.to)
        cc = self._resolve_people(intent.draft.cc)
        if intent.thread_ref is not None:
            if intent.thread_ref not in self._world.thread_ids:
                raise IntentRejection(f"unknown thread {intent.thread_ref!r}")
            thread_id = intent.thread_ref
        else:
            thread_id = self._minter.mint("thr")
        in_reply_to = intent.reply_to_ref
        if in_reply_to is not None:
            parent_thread = self._world.threads.get(in_reply_to)
            if parent_thread is None:
                raise IntentRejection(f"unknown message {in_reply_to!r}")
            if parent_thread != thread_id:
                raise IntentRejection(
                    f"reply targets {in_reply_to!r} outside thread {thread_id!r}"
                )
        for ref in intent.attach_document_refs:
            if self._world.resolve_document(ref) is None:
                raise IntentRejection(f"unknown document {ref!r}")
        payload = EmailMessagePayload(
            kind="email.message",
            message_id=self._minter.mint("msg"),
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            sender=sender,
            to=to,
            cc=cc,
            subject=intent.draft.subject,
            body=intent.draft.body,
            attachments=(),
        )
        return (
            EventDraft(
                tag=payload.kind,
                source=entity,
                caused_by=event.event_id,
                payload=payload,
                delay=delay,
            ),
        )

    def _ground_chat(
        self, entity, sender, intent: ChatIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        conversation_id = self._world.resolve_conversation(intent.conversation_ref)
        if conversation_id is None:
            raise IntentRejection(
                f"unknown conversation {intent.conversation_ref!r}"
            )
        members = self._world.conversations[conversation_id]
        if sender not in members:
            raise IntentRejection(
                f"{sender} is not a member of {conversation_id}"
            )
        if intent.reply_to_ref is not None:
            if intent.reply_to_ref not in self._world.chat_messages:
                raise IntentRejection(
                    f"unknown chat message {intent.reply_to_ref!r}"
                )
        payload = ChatMessagePayload(
            kind="chat.message",
            chat_message_id=self._minter.mint("chm"),
            conversation_id=conversation_id,
            reply_to=intent.reply_to_ref,
            sender=sender,
            body=intent.draft.body,
        )
        return (
            EventDraft(
                tag=payload.kind,
                source=entity,
                caused_by=event.event_id,
                payload=payload,
                delay=delay,
            ),
        )

    def _ground_ticket(
        self, entity, sender, intent: TicketIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        drafts: list[EventDraft] = []
        if intent.create is not None:
            create = intent.create
            if create.status not in self._vocab.statuses:
                raise IntentRejection(f"unknown ticket status {create.status!r}")
            if create.priority not in self._vocab.priorities:
                raise IntentRejection(f"unknown priority {create.priority!r}")
            if create.ticket_type not in self._vocab.ticket_types:
                raise IntentRejection(f"unknown ticket type {create.ticket_type!r}")
            requester = self._resolve_people((create.requester_ref,))[0]
            assignee = (
                self._resolve_people((create.assignee_ref,))[0]
                if create.assignee_ref
                else None
            )
            payload = TicketCreatedPayload(
                kind="ticket.created",
                ticket_id=self._minter.mint("tkt"),
                actor=sender,
                title=create.title,
                description=create.description,
                requester=requester,
                assignee=assignee,
                status=create.status,
                priority=create.priority,
                ticket_type=create.ticket_type,
                fields=(),
            )
            drafts.append(
                EventDraft(
                    tag=payload.kind,
                    source=entity,
                    caused_by=event.event_id,
                    payload=payload,
                    delay=delay,
                )
            )
            return tuple(drafts)

        if intent.ticket_ref is None:
            raise IntentRejection("ticket intent needs a ticket_ref or create spec")
        values = self._world.tickets.get(intent.ticket_ref)
        if values is None:
            raise IntentRejection(f"unknown ticket {intent.ticket_ref!r}")
        if intent.changes:
            for change in intent.changes:
                if change.field in values and values[change.field] != change.old:
                    raise IntentRejection(
                        f"stale change to {change.field}: claimed old "
                        f"{change.old!r}, actual {values[change.field]!r}"
                    )
                if change.field == "status" and change.new not in self._vocab.statuses:
                    raise IntentRejection(f"unknown ticket status {change.new!r}")
                if (
                    change.field == "priority"
                    and change.new not in self._vocab.priorities
                ):
                    raise IntentRejection(f"unknown priority {change.new!r}")
            payload = TicketUpdatedPayload(
                kind="ticket.updated",
                ticket_id=intent.ticket_ref,
                actor=sender,
                changes=intent.changes,
            )
            drafts.append(
                EventDraft(
                    tag=payload.kind,
                    source=entity,
                    caused_by=event.event_id,
                    payload=payload,
                    delay=delay,
                )
            )
        if intent.comment:
            payload = TicketCommentedPayload(
                kind="ticket.commented",
                ticket_id=intent.ticket_ref,
                actor=sender,
                body=intent.comment,
            )
            drafts.append(
                EventDraft(
                    tag=payload.kind,
                    source=entity,
                    caused_by=event.event_id,
                    payload=payload,
                    delay=delay,
                )
            )
        if not drafts:
            raise IntentRejection("ticket intent had no changes and no comment")
        return tuple(drafts)

    def _ground_document(
        self, entity, sender, intent: DocumentEditIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        if intent.create is not None:
            payload = DocumentCreatedPayload(
                kind="document.created",
                document_id=self._minter.mint("doc"),
                author=sender,
                title=intent.create.title,
                path=intent.create.path,
                location="repository",
                content_format="markdown",
                content=intent.create.content,
            )
        else:
            if intent.document_ref is None or intent.edit is None:
                raise IntentRejection(
                    "document intent needs a document_ref and edit, or a create spec"
                )
            document_id = self._world.resolve_document(intent.document_ref)
            if document_id is None:
                raise IntentRejection(f"unknown document {intent.document_ref!r}")
            payload = DocumentRevisedPayload(
                kind="document.revised",
                document_id=document_id,
                revision=self._world.documents[document_id] + 1,
                author=sender,
                content=intent.edit.new_content,
                change_summary=intent.edit.change_summary,
            )
        return (
            EventDraft(
                tag=payload.kind,
                source=entity,
                caused_by=event.event_id,
                payload=payload,
                delay=delay,
            ),
        )

    def _ground_calendar(
        self, entity, sender, intent: CalendarIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        if intent.respond is None:
            raise IntentRejection("only calendar responses are grounded in v1")
        payload = CalendarResponsePayload(
            kind="calendar.response",
            calendar_event_id=intent.respond.calendar_event_ref,
            responder=sender,
            response=intent.respond.response,
        )
        return (
            EventDraft(
                tag=payload.kind,
                source=entity,
                caused_by=event.event_id,
                payload=payload,
                delay=delay,
            ),
        )


def _intent_summary(action: EntityAction) -> str:
    return action.model_dump_json()[:500]
