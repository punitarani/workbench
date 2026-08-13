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
from workbench.core.events.agent import (
    SimAgentMemoryPayload,
    SimAgentPlanPayload,
)
from workbench.core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarResponsePayload,
)
from workbench.core.events.chat import ChatMessagePayload, ChatReactionAddedPayload
from workbench.core.events.control import (
    SimDayEndedPayload,
    SimDayStartedPayload,
    SimGmNotePayload,
    SimWakePayload,
)
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.ids import IdMinter
from workbench.core.intents import (
    ActionIntent,
    AgentNoteIntent,
    AgentPlanIntent,
    CalendarIntent,
    ChatIntent,
    DocumentEditIntent,
    EmailIntent,
    FreeformIntent,
    IdleIntent,
    ReactionIntent,
    TicketIntent,
    TimeLogIntent,
)
from workbench.core.simtime import SimDuration
from workbench.simulation.chronicle.calendar import SECONDS_PER_DAY, CalendarWindow
from workbench.simulation.gm.timeflow import intent_duration
from workbench.simulation.gm.world_state import WorldState, WorldStateModel


class TicketVocabulary(BaseModel):
    statuses: tuple[str, ...]
    priorities: tuple[str, ...]
    ticket_types: tuple[str, ...]


class IntentRejection(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DayPlan(BaseModel):
    """How multi-day runs unfold: each sim.day.started mints that workday's
    wake ladder and its sim.day.ended; each sim.day.ended chains the next
    workday's start. Weekends never appear in the log."""

    window: CalendarWindow
    personas: tuple[tuple[str, int], ...]  # (entity name, check interval minutes)
    end_of_day: int
    day_start: int = 9 * 3600
    stagger: int = 180


class GroundedGmState(BaseModel):
    minter: IdMinter
    emergent_minted: int = 0
    # Absent in pre-resume snapshots and at run start: an empty world.
    world: WorldStateModel = WorldStateModel()


class GroundedGm:
    state_model = GroundedGmState

    def __init__(
        self,
        *,
        entity_for_person: dict[str, str],
        ticket_vocabulary: TicketVocabulary,
        response_delay_seconds: int = 120,
        day_plan: DayPlan | None = None,
    ) -> None:
        self._world = WorldState()
        self._minter = IdMinter()
        self._entity_for_person = dict(entity_for_person)
        self._person_for_entity = {
            entity: person for person, entity in entity_for_person.items()
        }
        self._vocab = ticket_vocabulary
        self._response_delay = response_delay_seconds
        self._day_plan = day_plan
        self._bill_rates: dict[str, int] = {}
        self._emergent_cap = 0
        self._emergent_minted = 0

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

    def set_emergent_cap(self, cap: int) -> None:
        """How many unknown-but-plausible people the world may mint per run."""
        self._emergent_cap = cap

    def set_bill_rates(self, rates: dict[str, int]) -> None:
        """Hourly rates in cents by person id; applied at time-log grounding."""
        self._bill_rates = dict(rates)

    def get_state(self) -> GroundedGmState:
        # Deep-copy the minter: a captured state must not alias live counters.
        return GroundedGmState(
            minter=self._minter.model_copy(deep=True),
            world=self._world.to_model(),
            emergent_minted=self._emergent_minted,
        )

    def set_state(self, state: GroundedGmState) -> None:
        self._minter = state.minter.model_copy(deep=True)
        self._world = WorldState.from_model(state.world)
        self._emergent_minted = state.emergent_minted

    def _entities_for(self, person_ids) -> tuple[str, ...]:
        seen: list[str] = []
        for person_id in person_ids:
            entity = self._entity_for_person.get(person_id)
            if entity is not None and entity not in seen:
                seen.append(entity)
        return tuple(seen)

    def observers_for(self, payload) -> tuple[str, ...]:
        """Pure routing preview for batch admission: a superset of what
        ``route`` will return for this payload, computed without applying
        the event. Supersets are safe — they only shrink batches."""
        match payload:
            case SimWakePayload():
                if payload.entity in self._person_for_entity:
                    return (payload.entity,)
                return ()
            case EmailMessagePayload():
                return self._entities_for((payload.sender, *payload.to, *payload.cc))
            case ChatMessagePayload():
                members = self._world.conversations.get(payload.conversation_id, ())
                return self._entities_for((payload.sender, *members))
            case TicketCreatedPayload():
                return self._entities_for(
                    (payload.actor, payload.requester, payload.assignee)
                )
            case TicketUpdatedPayload():
                values = self._world.tickets.get(payload.ticket_id, {})
                changed = [
                    ref
                    for change in payload.changes
                    if change.field == "assignee"
                    for ref in (change.old, change.new)
                ]
                return self._entities_for(
                    (payload.actor, values.get("assignee"), *changed)
                )
            case TicketCommentedPayload():
                values = self._world.tickets.get(payload.ticket_id, {})
                return self._entities_for((payload.actor, values.get("assignee")))
            case DocumentCreatedPayload() | DocumentRevisedPayload():
                return self._entities_for((payload.author,))
            case SimAgentMemoryPayload() | SimAgentPlanPayload():
                return (payload.entity,)
            case SimGmNotePayload():
                return (payload.entity,) if payload.entity is not None else ()
            case _:
                return ()

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
            # Senders observe their own messages too: sent mail is how a
            # persona knows a pending item is answered and how later drafts
            # see their own side of a thread. Observation is not a turn —
            # next_acting never grants one to the sender.
            case EmailMessagePayload():
                return self._entities_for((payload.sender, *payload.to, *payload.cc))
            case ChatMessagePayload():
                members = self._world.conversations.get(payload.conversation_id, ())
                return self._entities_for((payload.sender, *members))
            # Record-type events deliver to their actor too: an actor who
            # never sees their own ticket or revision will redo it forever.
            case TicketCreatedPayload():
                return self._entities_for(
                    (payload.actor, payload.requester, payload.assignee)
                )
            case TicketUpdatedPayload() | TicketCommentedPayload():
                values = self._world.tickets.get(payload.ticket_id, {})
                return self._entities_for((payload.actor, values.get("assignee")))
            case DocumentCreatedPayload() | DocumentRevisedPayload():
                return self._entities_for((payload.author,))
            # Cognition and correction events go back to their entity —
            # rejections become memories agents can learn from.
            case SimAgentMemoryPayload() | SimAgentPlanPayload():
                return (
                    (payload.entity,)
                    if payload.entity in self._person_for_entity
                    else ()
                )
            case SimGmNotePayload():
                if (
                    payload.entity is not None
                    and payload.entity in self._person_for_entity
                ):
                    return (payload.entity,)
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
                entity=entity,
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

    async def consequences(self, event: Event) -> tuple[EventDraft, ...]:
        plan = self._day_plan
        if plan is None:
            return ()
        payload = event.payload
        match payload:
            case SimDayStartedPayload():
                day = self._day_index(payload.day)
                drafts: list[EventDraft] = []
                for index, (entity_name, interval) in enumerate(plan.personas):
                    wake_delay = plan.day_start + (index + 1) * plan.stagger
                    while wake_delay < plan.end_of_day:
                        wake = SimWakePayload(kind="sim.wake", entity=entity_name)
                        drafts.append(
                            EventDraft(
                                tag=wake.kind,
                                source="gm",
                                caused_by=event.event_id,
                                payload=wake,
                                delay=SimDuration(wake_delay),
                            )
                        )
                        wake_delay += interval * 60
                ended = SimDayEndedPayload(kind="sim.day.ended", day=payload.day)
                drafts.append(
                    EventDraft(
                        tag=ended.kind,
                        source="gm",
                        caused_by=event.event_id,
                        payload=ended,
                        delay=SimDuration(plan.end_of_day),
                    )
                )
                return tuple(drafts)
            case SimDayEndedPayload():
                day = self._day_index(payload.day)
                for candidate in range(day + 1, plan.window.day_count):
                    if plan.window.is_workday(candidate):
                        started = SimDayStartedPayload(
                            kind="sim.day.started",
                            day=plan.window.iso_date(candidate),
                        )
                        delay = (
                            int(plan.window.day_offset(candidate))
                            - day * SECONDS_PER_DAY
                            - plan.end_of_day
                        )
                        return (
                            EventDraft(
                                tag=started.kind,
                                source="gm",
                                caused_by=event.event_id,
                                payload=started,
                                delay=SimDuration(delay),
                            ),
                        )
                return ()
            case _:
                return ()

    def _day_index(self, iso_day: str) -> int:
        plan = self._day_plan
        assert plan is not None
        from datetime import date

        start = date.fromisoformat(plan.window.start_date)
        return (date.fromisoformat(iso_day) - start).days

    async def should_terminate(self) -> TerminateDecision:
        return TerminateDecision(terminate=False, reason="runs until quiescent")

    def _extract_intent(self, action: EntityAction) -> ActionIntent:
        if not isinstance(action, IntentAction):
            raise IntentRejection(f"expected a typed intent, got {action.kind} action")
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

    @staticmethod
    def _plausible_person(ref: str) -> tuple[str, str] | None:
        """(name, email) for refs that plausibly denote a real new person."""
        stripped = ref.strip()
        if "@" in stripped and " " not in stripped:
            local, _, domain = stripped.partition("@")
            if local and "." in domain:
                name = " ".join(
                    part.capitalize()
                    for part in local.replace(".", " ").replace("_", " ").split()
                )
                if name:
                    return (name, stripped.lower())
            return None
        words = stripped.split()
        if len(words) >= 2 and all(w[:1].isupper() and w.isalpha() for w in words):
            slug = "-".join(w.lower() for w in words)
            return (stripped, f"{slug}@external.example")
        return None

    def _mint_person(self, name: str, email: str) -> PersonRecordPayload:
        base = "per-" + "-".join(
            "".join(c for c in word.lower() if c.isalnum()) for word in name.split()
        )
        person_id = base
        suffix = 2
        while person_id in self._world.people:
            person_id = f"{base}-{suffix}"
            suffix += 1
        record = PersonRecordPayload(
            kind="person.record",
            person_id=person_id,
            name=name,
            email_address=email,
            title="External contact",
            department="External",
            manager=None,
            affiliation="external",
            timezone="UTC",
        )
        self._emergent_minted += 1
        # Apply immediately so later refs in the same intent resolve.
        self._world.people[person_id] = record
        self._world.name_to_person[name.casefold()] = person_id
        self._world.email_to_person[email.casefold()] = person_id
        return record

    def _resolve_or_mint_people(
        self, refs, minted: list[PersonRecordPayload]
    ) -> tuple[str, ...]:
        resolved: list[str] = []
        for ref in refs:
            person = self._world.resolve_person(ref)
            if person is None and self._emergent_minted < self._emergent_cap:
                plausible = self._plausible_person(ref)
                if plausible is not None:
                    record = self._mint_person(*plausible)
                    minted.append(record)
                    person = record.person_id
            if person is None:
                raise IntentRejection(f"unknown person {ref!r}")
            if person not in resolved:
                resolved.append(person)
        return tuple(resolved)

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
            case ReactionIntent():
                return self._ground_reaction(entity, sender, intent, event, delay)
            case TimeLogIntent():
                return self._ground_time_log(entity, sender, intent, event, delay)
            case AgentNoteIntent():
                return self._ground_agent_note(entity, intent, event, delay)
            case AgentPlanIntent():
                return self._ground_agent_plan(entity, intent, event, delay)
            case _:
                raise IntentRejection(f"unsupported intent kind {intent.kind}")

    def _ground_email(
        self, entity, sender, intent: EmailIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        minted: list[PersonRecordPayload] = []
        to = self._resolve_or_mint_people(intent.draft.to, minted)
        cc = self._resolve_or_mint_people(intent.draft.cc, minted)
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
        record_drafts = tuple(
            EventDraft(
                tag=record.kind,
                source="gm",
                caused_by=event.event_id,
                payload=record,
                delay=delay,
            )
            for record in minted
        )
        return (
            *record_drafts,
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
            raise IntentRejection(f"unknown conversation {intent.conversation_ref!r}")
        members = self._world.conversations[conversation_id]
        if sender not in members:
            raise IntentRejection(f"{sender} is not a member of {conversation_id}")
        if intent.reply_to_ref is not None:
            if intent.reply_to_ref not in self._world.chat_messages:
                raise IntentRejection(f"unknown chat message {intent.reply_to_ref!r}")
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
            # Bump the head at resolve time: a second edit resolved before the
            # first occurs must still get a distinct revision number.
            revision = self._world.documents[document_id] + 1
            self._world.documents[document_id] = revision
            payload = DocumentRevisedPayload(
                kind="document.revised",
                document_id=document_id,
                revision=revision,
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

    def _ground_reaction(
        self, entity, sender, intent: ReactionIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        conversation_id = self._world.chat_message_conversations.get(
            intent.chat_message_ref
        )
        if conversation_id is None:
            raise IntentRejection(f"unknown chat message {intent.chat_message_ref!r}")
        members = self._world.conversations.get(conversation_id, ())
        if sender not in members:
            raise IntentRejection(f"{sender} is not in {conversation_id}")
        payload = ChatReactionAddedPayload(
            kind="chat.reaction.added",
            conversation_id=conversation_id,
            chat_message_id=intent.chat_message_ref,
            person_id=sender,
            emoji=intent.emoji,
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

    def _ground_time_log(
        self, entity, sender, intent: TimeLogIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        if intent.ticket_ref not in self._world.tickets:
            raise IntentRejection(f"unknown ticket {intent.ticket_ref!r}")
        payload = TimeLoggedPayload(
            kind="work.time.logged",
            person_id=sender,
            ticket_id=intent.ticket_ref,
            minutes=intent.minutes,
            note=intent.note,
            rate_cents=self._bill_rates.get(sender),
            billable=intent.billable,
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
        if intent.schedule is not None:
            attendees = self._resolve_people((sender, *intent.schedule.attendee_refs))
            payload = CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=self._minter.mint("cal"),
                organizer=sender,
                title=intent.schedule.title,
                start=intent.schedule.start,
                end=intent.schedule.end,
                attendees=attendees,
                description=intent.schedule.description,
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
        if intent.respond is None:
            raise IntentRejection("calendar intent needs a schedule or a response")
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

    def _ground_agent_note(
        self, entity, intent: AgentNoteIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        bullets = tuple(
            bullet.model_copy(
                update={
                    "refs": tuple(
                        ref for ref in bullet.refs if self._world.knows_ref(ref)
                    )
                }
            )
            for bullet in intent.bullets
        )
        payload = SimAgentMemoryPayload(
            kind="sim.agent.memory",
            note_id=self._minter.mint("mem"),
            entity=entity,
            note_kind=intent.note_kind,
            day=intent.day,
            bullets=bullets,
            open_loops=intent.open_loops,
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

    def _ground_agent_plan(
        self, entity, intent: AgentPlanIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        end_of_day = self._day_plan.end_of_day if self._day_plan is not None else 86_400
        clamped = []
        previous_end = 0
        for block in sorted(intent.blocks, key=lambda b: (b.start, b.end)):
            start = max(block.start, previous_end)
            end = min(block.end, end_of_day)
            if end <= start:
                continue
            clamped.append(block.model_copy(update={"start": start, "end": end}))
            previous_end = end
        if not clamped:
            raise IntentRejection("plan has no blocks inside the working day")
        key = f"{entity}|{intent.day}"
        revision = self._world.plan_revisions.get(key, 0) + 1
        payload = SimAgentPlanPayload(
            kind="sim.agent.plan",
            plan_id=self._minter.mint("pln"),
            entity=entity,
            day=intent.day,
            revision=revision,
            blocks=tuple(clamped),
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
