"""The grounded game master: typed intents in, typed world events out.

Fully deterministic in v1 — reference resolution, validation, and routing are
code, not model calls. Unresolvable intents become sim.gm.note events, so a
run never wedges and every rejection is visible in the log. LM-backed repair
(RepairIntent, ResolveFreeform) is a named future optimization target.
"""

import re

from pydantic import BaseModel

from core.actions import (
    ActionSpec,
    CueActionSpec,
    DeliverableActionSpec,
    EntityAction,
    IntentAction,
    IntentActionSpec,
    MeetingTurnActionSpec,
    NextActingDecision,
    PlanActionSpec,
    ReflectActionSpec,
    ResolutionDecision,
    TerminateDecision,
    TimesheetActionSpec,
)
from core.artifacts import (
    parse_formatted,
    parse_slides,
    parse_spreadsheet,
)
from core.events import Event, EventDraft
from core.events.agent import (
    SimAgentMemoryPayload,
    SimAgentPlanPayload,
)
from core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarResponsePayload,
)
from core.events.chat import ChatMessagePayload, ChatReactionAddedPayload
from core.events.control import (
    SimCuePayload,
    SimDayEndedPayload,
    SimDayStartedPayload,
    SimDeliverablePayload,
    SimGmNotePayload,
    SimPlanningPayload,
    SimReflectionPayload,
    SimTimesheetPayload,
    SimWakePayload,
)
from core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from core.events.email import Attachment, EmailMessagePayload
from core.events.meetings import (
    MeetingTranscriptPayload,
    SimMeetingConvenePayload,
    SimMeetingTurnPayload,
    TranscriptTurn,
)
from core.events.people import PersonRecordPayload
from core.events.tickets import (
    PERSON_TICKET_FIELDS,
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
    collapse_field_changes,
)
from core.events.work import TimeLoggedPayload
from core.filing import filed_name
from core.ids import IdMinter
from core.intents import (
    ActionIntent,
    AgentNoteIntent,
    AgentPlanIntent,
    CalendarIntent,
    ChatIntent,
    DocumentCreateSpec,
    DocumentEditIntent,
    EmailIntent,
    FreeformIntent,
    IdleIntent,
    MeetingSpeakIntent,
    ReactionIntent,
    TicketIntent,
    TimeLogIntent,
    TimesheetIntent,
)
from core.seed import Seed, derive_seed
from core.simtime import SimDuration
from simulation.calendar import SECONDS_PER_DAY, CalendarWindow
from simulation.gm.timeflow import intent_duration
from simulation.gm.world_state import WorldState, WorldStateModel


class TicketVocabulary(BaseModel):
    statuses: tuple[str, ...]
    priorities: tuple[str, ...]
    ticket_types: tuple[str, ...]


class IntentRejection(Exception):
    """A refusal the actor sees and can correct.

    ``dropped_entries``/``unknown_refs`` carry work the world could not
    accept, so the note built from this rejection reports it as data. A
    gate three files away used to recover the same numbers by parsing the
    prose, which meant rewording a sentence silently zeroed a loss rate.

    **Two audiences, two strings.** ``reason`` is read by a person inside
    the fiction: it becomes a memory at importance 10, the highest this
    world has, so it is retrieved ahead of everything else that person
    knows and it shapes what they plan, write and say. ``detail`` is read
    by whoever is running the recording. Most reasons here are already
    written for the first audience — *"an email needs at least one
    recipient; name them by full name as they appear in the thread"* is
    exactly what a colleague would say. The one that was not put a
    pydantic dump in front of a lawyer, at importance 10, every time a
    document failed to parse; the firm read it, believed it, and spent six
    months discussing a platform outage that never happened.

    ``engine_fault`` is the other half. *"unsupported intent kind"* and
    *"expected a typed intent, got …"* describe a programming mistake, not
    a workplace one: there is no different thing the person could have
    done, so telling them is not instruction, it is noise that outranks
    their real memories. Those reach the operator and stop there.
    """

    def __init__(
        self,
        reason: str,
        *,
        detail: str = "",
        engine_fault: bool = False,
        dropped_entries: int = 0,
        unknown_refs: tuple[str, ...] = (),
    ) -> None:
        super().__init__(" ".join(part for part in (reason, detail) if part))
        self.reason = reason
        self.detail = detail
        self.engine_fault = engine_fault
        self.dropped_entries = dropped_entries
        self.unknown_refs = unknown_refs

    @property
    def guidance(self) -> str:
        """What the person is allowed to remember. Empty for engine faults."""

        return "" if self.engine_fault else self.reason


class DayPlan(BaseModel):
    """How runs unfold: each sim.day.started mints that workday's wake
    cohorts and its sim.day.ended; each sim.day.ended chains the next
    workday's start. Weekends never appear in the log.

    Wakes land on a shared tick grid: each persona's interval quantizes
    up to a grid multiple and a seeded per-(day, persona) phase picks its
    ticks. Personas co-waking on a tick is what lets the windowed engine
    batch their LM calls; what they do on the tick still varies."""

    window: CalendarWindow
    personas: tuple[tuple[str, int], ...]  # (entity name, check interval minutes)
    # How often each person produces work product, in days. A staff
    # accountant writes workpapers most days; a partner writes a memo
    # now and then. Rotating everyone equally gave all seventeen people
    # the same five documents, which no practice has ever looked like.
    deliverable_period: tuple[tuple[str, int], ...] = ()
    end_of_day: int
    day_start: int = 9 * 3600
    wake_grid_minutes: int = 30
    seed_root: int = 0
    # v2: one end-of-day timesheet turn per persona. Off by default so a v1
    # recording replays byte-identically.
    timesheets: bool = False
    # v2: a scheduled work-product turn for half the cast each day. Off by
    # default for the same reason.
    deliverables: bool = False


_PARSERS = {
    "spreadsheet": parse_spreadsheet,
    "formatted": parse_formatted,
    "slides": parse_slides,
}


# What a persona is told they filed, and what to do about it. The reason
# reaches them as a memory at importance 10, so it has to be a sentence a
# colleague would say.
#
# This read "send the structured JSON for that format" and cost a lawyer's
# reflection: Cecile Marchand wrote "doc-000003 is malformed: it declares a
# structured format but the underlying content is not actually structured
# JSON". She was paraphrasing the referee. A partner does not know what
# structured JSON is, and the vocabulary check that was supposed to catch
# this had every type name and action verb in it and not the word `json`.
_WORK_PRODUCT = {
    "spreadsheet": "a workbook",
    "formatted": "a document",
    "slides": "a deck",
    "markdown": "a note",
}
_HOW_TO_FIX = {
    "spreadsheet": "set the figures out in rows and columns",
    "formatted": "set it out in headings and paragraphs",
    "slides": "set it out as slides, each with a title and its points",
    "markdown": "write it as prose",
}


def _reject_unless_parsable(content_format: str, content: str, label: str) -> None:
    """Raise the instructive rejection unless the content really is that form.

    Applied on creation *and* on revision. The asymmetry was a real defect:
    creation validated, revision did not, and the revise path drafts prose.
    A workbook worked forward therefore came back as text, kept its
    ``spreadsheet`` format, and materialized as a ``.txt`` file that claims
    to be a workbook and is not — 10 of 52 documents in one recorded world.
    Nothing failed at the time; the corruption surfaced only when something
    finally read the file room.
    """

    # Empty is its own rejection, and what "empty" means depends on the
    # format. Nine documents in a six-month world were created blank and
    # materialized as zero-byte files -- work product the record registers
    # and the folder loses, invisible to any check that counts documents.
    #
    # Here rather than on the create path alone, so revision gets the same
    # rule. That asymmetry is the defect this function already exists to
    # fix, arrived at from a second direction.
    if not (content or "").strip():
        raise IntentRejection(
            f"{label} has no content; a document with nothing in it is not "
            "work product — write it, or choose an action other than "
            "creating or revising a document"
        )
    parser = _PARSERS.get(content_format)
    if parser is None:
        return
    try:
        parsed = parser(content)
    except ValueError as error:
        raise IntentRejection(
            f"{label} is filed as {_WORK_PRODUCT[content_format]} and what "
            f"is in it is not one; {_HOW_TO_FIX[content_format]}, or call it "
            "a note and write it as prose",
            # The parser's own words, for the operator. Interpolated into
            # the reason, this read "(1 validation error for
            # SpreadsheetContent review_note Extra inputs are not
            # permitted)" -- and that sentence, at importance 10, is what
            # the firm turned into "the malformed-input bug".
            detail=str(error),
        ) from error
    # A workbook of column headings and no rows parses cleanly and is
    # empty in the only sense that matters -- `formatted` and `slides`
    # already refuse their equivalents, so this is the one format where a
    # document can be well-formed and hold nothing.
    sheets = getattr(parsed, "sheets", None)
    if sheets is not None and not any(getattr(sheet, "rows", ()) for sheet in sheets):
        raise IntentRejection(
            f"{label} is a workbook whose sheets have no rows; put the "
            "figures in it, or write the note as prose instead"
        )


# How many *other people's* engagements a turn is shown, for context. The
# cap is on context only — see below.
_CONTEXT_CAP = 16


def _within_cap(
    mine: list[str], others: list[str], standing_ids: set[str]
) -> tuple[str, ...]:
    """The engagements a timesheet turn is shown.

    You cannot book time to a code you cannot see, so the list bounds the
    wrong thing if it can hide one. Two kinds of entry are *bookable* by
    the person being asked — their own matters, and the standing codes
    anybody may book to — and neither may be truncated. Everyone else's
    matters are context, and that is what the cap limits.

    This was a flat `(mine + others)[:16]` in declaration order. Standing
    codes are declared last, because they belong to nobody in particular,
    so they fell off the end and people invented references for work they
    genuinely had to record: **20.7% of attempted time refused**.

    Reserving them was the obvious repair and was still wrong, because it
    reserved them *after* the person's own matters. Measured on this
    firm's shape — 8 standing codes, 22 client matters — a partner
    carrying 12 matters still saw only 4 of the 8, and would still invent
    the other four. A fix that works for a junior and fails for a partner
    reads as working, because juniors are the common case.
    """

    # Declared standing codes only. Inferring them from a missing client
    # swept up every ticket a persona opened at runtime, because the
    # grounding path does not set one — and those are ordinary matters
    # whose time then vanished from the client record.
    standing = [line for line in others if line.split(" ", 1)[0] in standing_ids]
    context = [line for line in others if line not in standing]
    # Everything bookable, then as much context as the cap allows. The
    # bookable half is bounded too — by how many standing codes the world
    # declares, which is a fixed small number — where inferring the class
    # let it grow without limit as people opened matters.
    return tuple(mine + standing + context[:_CONTEXT_CAP])


def _validated_format(create: DocumentCreateSpec) -> str:
    """The declared format, once the content is known to parse as it."""

    _reject_unless_parsable(create.content_format, create.content, create.path)
    return create.content_format


# When a working session may begin, as seconds past midnight. A meeting at
# 00:20 is not a meeting; two of seven persona-scheduled events in one
# recorded day were under two thousand seconds past midnight.
_WORKING_HOURS = (7 * 3600, 19 * 3600)


def _clock_seconds(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 3600 + int(minutes) * 60


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
        delivery_quantum_seconds: int = 1,
        director=None,
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
        # Seeded outside-world schedule; None means a quiet horizon.
        self._director = director
        # Grounded deliveries round up to this quantum so disjoint
        # replies co-land on shared ticks and batch under windowing.
        self._delivery_quantum = max(1, delivery_quantum_seconds)
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
            case (
                SimReflectionPayload()
                | SimPlanningPayload()
                | SimCuePayload()
                | SimTimesheetPayload()
                | SimDeliverablePayload()
            ):
                return (payload.entity,)
            case SimGmNotePayload():
                return (payload.entity,) if payload.entity is not None else ()
            case TimeLoggedPayload():
                # A day of time arrives as many events at once. Without this
                # they preview as nobody's business, land in one batch, and
                # ask one person to act several times at the same instant.
                return self._entities_for((payload.person_id,))
            # The diary. Every one of these already has a handler waiting
            # in `memory_stream` -- "Meeting scheduled: {title}" at
            # importance 5, "Meeting held with N turns" at importance 8 --
            # and nothing delivered them, so a firm whose days are meetings
            # remembered none of them. Only the genesis seed calendar was
            # ever visible, because genesis is observed wholesale rather
            # than routed.
            #
            # The responder observes their own RSVP for exactly the reason
            # the ticket comment above gives. Measured without it: 203 of
            # 278 responses across two recorded days were the same person
            # answering the same invitation again, one of them fifteen
            # times, because `_pending_all` clears an invitation on seeing
            # the response and the response never arrived. That loop then
            # crowded out chat, which is how it was noticed at all.
            #
            # Not the organizer, though they should hear it: `world_state`
            # keeps calendar events as a set of ids with no organizer, and
            # widening that is a change to another frozen file.
            case CalendarEventScheduledPayload():
                return self._entities_for((payload.organizer, *payload.attendees))
            case CalendarResponsePayload():
                # The organizer too. An answer nobody hears is not an
                # answer: without this the firm records 29 declines in a
                # sample of 278 and not one of them reaches the person who
                # booked the meeting, so nothing is ever moved and no task
                # can ask what was rescheduled or why.
                return self._entities_for(
                    (
                        payload.responder,
                        self._world.calendar_organizers.get(
                            payload.calendar_event_id
                        ),
                    )
                )
            case MeetingTranscriptPayload():
                return self._entities_for(payload.attendees)
            case SimMeetingTurnPayload():
                # Turns are minted one at a time today, but the same gap
                # would let two land together and act one speaker twice.
                return (payload.speaker,) if payload.speaker else ()
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
            case (
                SimReflectionPayload()
                | SimPlanningPayload()
                | SimCuePayload()
                | SimTimesheetPayload()
                | SimDeliverablePayload()
            ):
                if payload.entity in self._person_for_entity:
                    return (payload.entity,)
                return ()
            case SimGmNotePayload():
                if (
                    payload.entity is not None
                    and payload.entity in self._person_for_entity
                ):
                    return (payload.entity,)
                return ()
            # The diary. Every one of these already has a handler waiting
            # in `memory_stream` -- "Meeting scheduled: {title}" at
            # importance 5, "Meeting held with N turns" at importance 8 --
            # and nothing delivered them, so a firm whose days are meetings
            # remembered none of them. Only the genesis seed calendar was
            # ever visible, because genesis is observed wholesale rather
            # than routed.
            #
            # The responder observes their own RSVP for exactly the reason
            # the ticket comment above gives. Measured without it: 203 of
            # 278 responses across two recorded days were the same person
            # answering the same invitation again, one of them fifteen
            # times, because `_pending_all` clears an invitation on seeing
            # the response and the response never arrived. That loop then
            # crowded out chat, which is how it was noticed at all.
            #
            # Not the organizer, though they should hear it: `world_state`
            # keeps calendar events as a set of ids with no organizer, and
            # widening that is a change to another frozen file.
            case CalendarEventScheduledPayload():
                return self._entities_for((payload.organizer, *payload.attendees))
            case CalendarResponsePayload():
                # The organizer too. An answer nobody hears is not an
                # answer: without this the firm records 29 declines in a
                # sample of 278 and not one of them reaches the person who
                # booked the meeting, so nothing is ever moved and no task
                # can ask what was rescheduled or why.
                return self._entities_for(
                    (
                        payload.responder,
                        self._world.calendar_organizers.get(
                            payload.calendar_event_id
                        ),
                    )
                )
            case MeetingTranscriptPayload():
                return self._entities_for(payload.attendees)
            case _:
                return ()

    async def next_acting(self, event: Event) -> NextActingDecision:
        payload = event.payload
        match payload:
            case (
                SimReflectionPayload()
                | SimPlanningPayload()
                | SimCuePayload()
                | SimTimesheetPayload()
                | SimDeliverablePayload()
            ):
                if payload.entity in self._person_for_entity:
                    return NextActingDecision(entities=(payload.entity,))
                return NextActingDecision(entities=())
            case SimMeetingTurnPayload():
                if payload.speaker in self._person_for_entity:
                    return NextActingDecision(entities=(payload.speaker,))
                return NextActingDecision(entities=())
            case SimWakePayload():
                if payload.entity not in self._person_for_entity:
                    return NextActingDecision(entities=())
                in_meeting = any(
                    payload.entity in progress.attendees
                    for progress in self._world.meetings.values()
                )
                if in_meeting:
                    return NextActingDecision(entities=())
                return NextActingDecision(entities=(payload.entity,))
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
                # A hot conversation eventually needs a reason to continue:
                # after six straight messages the auto-grant stops until the
                # day moves (any wake resets the streaks).
                #
                # Hoisted above the two-person split so it guards the
                # channel reply path below as well. It guarded DMs alone,
                # and the email branch caps chains at depth 3 with the note
                # that "without this cap, courteous personas acknowledge
                # each other forever" — the channel path had neither, which
                # cost nothing while replying to a channel message was
                # effectively impossible and became a runaway the moment
                # pending items began naming a message to reply to.
                if self._world.chat_streaks.get(payload.conversation_id, 0) >= 6:
                    return NextActingDecision(entities=())
                if len(members) == 2:
                    others = self._entities_for(
                        m for m in members if m != payload.sender
                    )
                    return NextActingDecision(entities=others[:1])
                if payload.reply_to is not None:
                    # Replying to someone's message grants them the turn.
                    target = self._world.chat_message_senders.get(payload.reply_to)
                    if target is not None and target != payload.sender:
                        entities = self._entities_for((target,))
                        if entities:
                            return NextActingDecision(entities=entities)
                for person_id in members:
                    if person_id == payload.sender:
                        continue
                    record = self._world.people.get(person_id)
                    if record is None:
                        continue
                    first_name = record.name.split()[0].casefold()
                    full_name = record.name.casefold()
                    if first_name in body or full_name in body:
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
        if isinstance(event.payload, SimReflectionPayload):
            return ReflectActionSpec(day=event.payload.day, scope=event.payload.scope)
        if isinstance(event.payload, SimPlanningPayload):
            return PlanActionSpec(day=event.payload.day)
        if isinstance(event.payload, SimTimesheetPayload):
            person = self._person_for(entity)
            # Their own engagements first, then the rest of the book, so a
            # persona logs against work they actually touch but can still
            # bill a colleague's matter when they helped on it.
            mine = [
                f"{ticket_id} {values.get('title', '')}"
                for ticket_id, values in self._world.tickets.items()
                if values.get("assignee") == person
            ]
            others = [
                f"{ticket_id} {values.get('title', '')}"
                for ticket_id, values in self._world.tickets.items()
                if values.get("assignee") != person
            ]
            engagements = _within_cap(mine, others, self._world.standing_tickets)
            return TimesheetActionSpec(
                day=event.payload.day,
                engagements=engagements,
                bills_clients=person in self._bill_rates,
            )
        if isinstance(event.payload, SimDeliverablePayload):
            person = self._person_for(entity)
            mine = [
                f"{ticket_id} {values.get('title', '')}"
                for ticket_id, values in self._world.tickets.items()
                if values.get("assignee") == person
            ]
            others = [
                f"{ticket_id} {values.get('title', '')}"
                for ticket_id, values in self._world.tickets.items()
                if values.get("assignee") != person
            ]
            # Authoring, rework, and review in rotation. Reviewing a
            # colleague's file is the branch that was missing: the earlier
            # rule only ever handed a person their own draft back, so a
            # firm of seventeen produced a hundred versions without a
            # single second reader — and a practice's whole quality
            # control was invisible in its own record.
            candidate: str | None = None
            text = ""
            as_review = False
            if self._world.documents:
                paths = self._world.document_paths_by_id
                authors = self._world.document_authors
                authored = [
                    document_id
                    for document_id in paths
                    if authors.get(document_id) == person
                ]
                colleagues = [
                    document_id
                    for document_id in paths
                    if authors.get(document_id) not in (None, person)
                ]
                # Rotate on something that actually advances. Authorship
                # never moves once a document exists, so a phase counted
                # from "documents I wrote" sticks on whichever branch it
                # first reaches — the old rule stuck on rework, which is
                # why five files carry nine versions each and no file
                # carries a second name. Total versions in the world moves
                # with every create and every revision; the roster offset
                # keeps seventeen people from all doing the same thing on
                # the same morning.
                roster = sorted(self._world.people)
                offset = roster.index(person) if person in roster else 0
                phase = (sum(self._world.documents.values()) + offset) % 3
                if phase == 2 and authored:
                    candidate = authored[-1]
                elif phase == 1 and colleagues:
                    candidate = colleagues[offset % len(colleagues)]
                    as_review = True
                if candidate is not None:
                    text = self._world.document_heads.get(candidate, "")
            return DeliverableActionSpec(
                day=event.payload.day,
                engagements=tuple(mine + others)[:12],
                revise_document_id=candidate,
                revise_document_text=text,
                as_review=as_review,
            )
        if isinstance(event.payload, SimCuePayload):
            return CueActionSpec(note=event.payload.note, topic=event.payload.topic)
        if isinstance(event.payload, SimMeetingTurnPayload):
            progress = self._world.meetings.get(event.payload.meeting_id)
            if progress is not None:
                names = []
                for name in progress.attendees:
                    person = self._world.people.get(self._person_for(name))
                    names.append(person.name if person else name)
                transcript = "\n".join(
                    f"{turn.speaker}: {turn.text}" for turn in progress.turns
                )
                return MeetingTurnActionSpec(
                    meeting_id=progress.meeting_id,
                    title=progress.title,
                    agenda=progress.description,
                    attendees=tuple(names),
                    transcript=transcript or "(the room settles)",
                    turn_index=event.payload.turn_index,
                )
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
                note=(
                    f"Rejected action from {entity}: {rejection.reason}"
                    + (f" [{rejection.detail}]" if rejection.detail else "")
                ),
                guidance=rejection.guidance,
                rejected_intent=_intent_summary(action),
                entity=entity,
                dropped_entries=rejection.dropped_entries,
                unknown_refs=rejection.unknown_refs,
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
        payload = event.payload
        meeting_drafts = self._meeting_consequences(event, payload)
        if meeting_drafts is not None:
            return meeting_drafts
        plan = self._day_plan
        if plan is None:
            return ()
        match payload:
            case SimDayStartedPayload():
                day = self._day_index(payload.day)
                drafts: list[EventDraft] = []
                grid = plan.wake_grid_minutes * 60
                # Morning planning cohort: everyone lays out the day on the
                # first tick, before any wake fires.
                for entity_name, _interval in plan.personas:
                    planning = SimPlanningPayload(
                        kind="sim.planning",
                        entity=entity_name,
                        day=payload.day,
                    )
                    drafts.append(
                        EventDraft(
                            tag=planning.kind,
                            source="gm",
                            caused_by=event.event_id,
                            payload=planning,
                            delay=SimDuration(plan.day_start),
                        )
                    )
                for entity_name, interval in plan.personas:
                    quantum = max(grid, -(-interval * 60 // grid) * grid)
                    slots = quantum // grid
                    phase = (
                        derive_seed(
                            Seed(root=plan.seed_root),
                            "wake-phase",
                            payload.day,
                            entity_name,
                        )
                        % slots
                    )
                    wake_delay = plan.day_start + phase * grid
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
                        wake_delay += quantum
                # Reflection cohort: every persona consolidates its day on
                # the last grid tick before close — one shared tick, so the
                # deep-model calls batch under windowing.
                workdays_so_far = sum(
                    1 for index in range(day + 1) if plan.window.is_workday(index)
                )
                scope = "weekly" if workdays_so_far % 5 == 0 else "daily"
                reflect_delay = max(plan.day_start, plan.end_of_day - grid)
                if plan.deliverables:
                    # Work product lands during the working day, not at the
                    # end of it. Half the cast on any given day, alternating,
                    # so a professional produces something every other day —
                    # roughly what fieldwork looks like, and enough that the
                    # repository reflects the practice rather than its
                    # templates.
                    produce_delay = max(
                        plan.day_start,
                        plan.day_start + (plan.end_of_day - plan.day_start) // 3,
                    )
                    periods = dict(plan.deliverable_period)
                    for index, (entity_name, _interval) in enumerate(plan.personas):
                        period = periods.get(entity_name, 2)
                        if (index + day) % period:
                            continue
                        deliverable = SimDeliverablePayload(
                            kind="sim.deliverable",
                            entity=entity_name,
                            day=payload.day,
                        )
                        drafts.append(
                            EventDraft(
                                tag=deliverable.kind,
                                source="gm",
                                caused_by=event.event_id,
                                payload=deliverable,
                                delay=SimDuration(produce_delay),
                            )
                        )
                if plan.timesheets:
                    # Time gets written up just before the day is reflected
                    # on, the way a professional closes out: log the hours,
                    # then think about the day.
                    timesheet_delay = max(plan.day_start, reflect_delay - grid)
                    for entity_name, _interval in plan.personas:
                        timesheet = SimTimesheetPayload(
                            kind="sim.timesheet",
                            entity=entity_name,
                            day=payload.day,
                        )
                        drafts.append(
                            EventDraft(
                                tag=timesheet.kind,
                                source="gm",
                                caused_by=event.event_id,
                                payload=timesheet,
                                delay=SimDuration(timesheet_delay),
                            )
                        )
                for entity_name, _interval in plan.personas:
                    reflection = SimReflectionPayload(
                        kind="sim.reflection",
                        entity=entity_name,
                        day=payload.day,
                        scope=scope,
                    )
                    drafts.append(
                        EventDraft(
                            tag=reflection.kind,
                            source="gm",
                            caused_by=event.event_id,
                            payload=reflection,
                            delay=SimDuration(reflect_delay),
                        )
                    )
                if self._director is not None:
                    for cue in self._director.cues_for(payload.day):
                        if cue.entity not in self._person_for_entity:
                            continue
                        cue_payload = SimCuePayload(
                            kind="sim.cue",
                            entity=cue.entity,
                            note=cue.note,
                            topic=cue.topic,
                        )
                        drafts.append(
                            EventDraft(
                                tag=cue_payload.kind,
                                source="gm",
                                caused_by=event.event_id,
                                payload=cue_payload,
                                delay=SimDuration(cue.at),
                            )
                        )
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

    def _meeting_consequences(
        self, event: Event, payload
    ) -> tuple[EventDraft, ...] | None:
        """Meeting orchestration: convene scheduled calendar events with
        two or more simulated attendees; a convene grants the organizer's
        side the first turn. Returns None when the event is not
        meeting-related so the day chain can look at it."""

        match payload:
            case CalendarEventScheduledPayload():
                attendees = self._entities_for(payload.attendees)
                start = int(payload.start)
                if len(attendees) < 2 or start <= int(event.time):
                    return ()
                convene = SimMeetingConvenePayload(
                    kind="sim.meeting.convene",
                    meeting_id=self._minter.mint("mtg"),
                    calendar_event_id=payload.calendar_event_id,
                    title=payload.title,
                    description=payload.description or "",
                    attendees=attendees,
                    duration_seconds=max(60, int(payload.end) - start),
                )
                return (
                    EventDraft(
                        tag=convene.kind,
                        source="gm",
                        caused_by=event.event_id,
                        payload=convene,
                        delay=SimDuration(start - int(event.time)),
                    ),
                )
            case SimMeetingConvenePayload():
                turn = SimMeetingTurnPayload(
                    kind="sim.meeting.turn",
                    meeting_id=payload.meeting_id,
                    speaker=payload.attendees[0],
                    turn_index=0,
                    attendees=payload.attendees,
                )
                return (
                    EventDraft(
                        tag=turn.kind,
                        source="gm",
                        caused_by=event.event_id,
                        payload=turn,
                        delay=SimDuration(60),
                    ),
                )
            case _:
                return None

    def _ground_meeting_speak(
        self, entity, intent: MeetingSpeakIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        progress = self._world.meetings.get(intent.meeting_ref)
        if progress is None:
            raise IntentRejection(f"no open meeting {intent.meeting_ref!r}")
        if entity not in progress.attendees:
            raise IntentRejection(f"{entity} is not in {progress.title!r}")
        person = self._person_for(entity)
        turns = (*progress.turns, TranscriptTurn(speaker=person, text=intent.text))
        yielded = progress.yielded
        if intent.yields and entity not in yielded:
            yielded = (*yielded, entity)
        updated = progress.model_copy(update={"turns": turns, "yielded": yielded})
        self._world.meetings[intent.meeting_ref] = updated

        finished = len(turns) >= updated.budget or set(updated.attendees) <= set(
            yielded
        )
        if finished:
            transcript = MeetingTranscriptPayload(
                kind="meeting.transcript",
                meeting_id=updated.meeting_id,
                calendar_event_id=updated.calendar_event_id,
                attendees=tuple(self._person_for(name) for name in updated.attendees),
                started=updated.started,
                ended=int(event.time) + 120,
                turns=turns,
            )
            return (
                EventDraft(
                    tag=transcript.kind,
                    source="gm",
                    caused_by=event.event_id,
                    payload=transcript,
                    delay=SimDuration(120),
                ),
            )
        order = updated.attendees
        start = (order.index(entity) + 1) % len(order)
        speaker = next(
            (
                order[(start + offset) % len(order)]
                for offset in range(len(order))
                if order[(start + offset) % len(order)] not in yielded
            ),
            order[start],
        )
        turn = SimMeetingTurnPayload(
            kind="sim.meeting.turn",
            meeting_id=updated.meeting_id,
            speaker=speaker,
            turn_index=len(turns),
            attendees=order,
        )
        return (
            EventDraft(
                tag=turn.kind,
                source="gm",
                caused_by=event.event_id,
                payload=turn,
                delay=SimDuration(120),
            ),
        )

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
            raise IntentRejection(
                f"expected a typed intent, got {action.kind} action",
                engine_fault=True,
            )
        if isinstance(action.intent, FreeformIntent):
            raise IntentRejection(
                "freeform intents are not grounded yet",
                detail=action.intent.text[:80],
                engine_fault=True,
            )
        return action.intent

    def _person_for(self, entity: str) -> str:
        person = self._person_for_entity.get(entity)
        if person is None:
            raise IntentRejection(
            f"entity {entity} has no person record", engine_fault=True
        )
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

    # Any minted world id, as it appears inside prose.
    _MINTED_ID = re.compile(r"\b[a-z]{3}-\d{6}\b")

    def _human_label(self, ref: str) -> str | None:
        """What a person would call the thing this id names.

        The filename comes from `core.filing`, not from the declared path.
        A name must never lie about its bytes: an author who declares a
        workbook and calls it `.docx` gets a file the room serves as
        `.xlsx`, and taking the declared basename here would put a
        filename into prose that no surface answers to. That rule already
        has one home precisely so its readers cannot drift -- and this was
        a fifth reader quietly reimplementing it.

        A label that still carries a minted id is refused. `re.sub` does
        not rescan its replacement, so a ticket titled "Timestamp
        inconsistency on tkt-000001 ..." would put an id straight back
        into the sentence this exists to clean. Returning None leaves the
        bare id in place, which is the same visible, honest outcome an
        unresolvable id already gets.
        """

        label: str | None = None
        if ref.startswith("doc-"):
            path = self._world.document_paths_by_id.get(ref)
            if path is not None:
                content_format = self._world.document_formats.get(ref, "markdown")
                label = filed_name(path, content_format).rsplit("/", 1)[-1]
        elif ref.startswith("tkt-"):
            values = self._world.tickets.get(ref)
            label = values.get("title") if values else None
        if label and self._MINTED_ID.search(label):
            return None
        return label

    def _dereference(self, text: str) -> str:
        """Replace internal ids in prose with the names of what they point at.

        Personas are shown ids because they need them: an attachment
        field takes `doc-000042`, a reply takes `chm-000117`. Having seen
        one, they write it into the sentence too — 26.1% of the 5,894
        messages in a six-month world contained at least one, most often
        "please see doc-000042 attached".

        Nobody writes that. Worse, it is a shortcut: an agent asked which
        matters a document touched can grep the id instead of reading
        anything, so a task meant to measure comprehension measures
        string matching.

        This is a referee-level normalisation, in the same family as the
        rule that a document's format wins an argument with its declared
        suffix: the author's intent is kept and their expression of it is
        corrected. Doing it here rather than at materialisation means the
        world log itself is clean and every surface derived from it
        agrees.

        One acknowledged cost: the memory stream indexes a record by the
        ids in its payload, so a document merely *mentioned* is no longer
        retrievable by its id from that message. A document *attached*
        still is — the id stays in `attachments`, which is the structured
        field the link belongs in anyway.
        """

        return self._MINTED_ID.sub(
            lambda match: self._human_label(match.group(0)) or match.group(0), text
        )

    def _resolve_person_field(self, ref: str | None) -> str | None:
        """A ticket field that holds a person, resolved to that person's id.

        Rejecting an unresolvable name rather than storing it keeps this
        the same rule the create path applies. A stored name is worse than
        a rejection: the rejection reaches the persona, which names
        somebody real next time, while the name sits in the column
        forever looking like data.
        """

        if ref is None:
            return None
        person = self._world.resolve_person(ref)
        if person is None:
            raise IntentRejection(f"unknown person {ref!r}")
        return person

    def _ground(
        self, entity: str, intent: ActionIntent, event: Event
    ) -> tuple[EventDraft, ...]:
        quantum = self._delivery_quantum
        raw = intent_duration(intent)
        delay = SimDuration(-(-raw // quantum) * quantum)
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
            case TimesheetIntent():
                return self._ground_timesheet(entity, sender, intent, event, delay)
            case AgentNoteIntent():
                return self._ground_agent_note(entity, intent, event, delay)
            case AgentPlanIntent():
                return self._ground_agent_plan(entity, intent, event, delay)
            case MeetingSpeakIntent():
                return self._ground_meeting_speak(entity, intent, event, delay)
            case _:
                raise IntentRejection(
                    f"unsupported intent kind {intent.kind}", engine_fault=True
                )

    _MEDIA_TYPES = {
        "markdown": ("md", "text/markdown"),
        "spreadsheet": (
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        "formatted": (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "slides": (
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
    }

    def _resolve_attachments(self, refs: tuple[str, ...]) -> tuple[Attachment, ...]:
        """Turn doc- ids into real attachments.

        Deliverables were produced and never sent: the payload has carried an
        attachments field all along and the grounding hardcoded it empty, so
        no email in any world ever had a file on it.
        """

        attachments = []
        for ref in refs:
            document_id = self._world.resolve_document(ref)
            if document_id is None:
                raise IntentRejection(f"unknown document {ref!r}")
            path = self._world.document_paths_by_id.get(document_id, "")
            content_format = self._world.document_formats.get(document_id, "markdown")
            suffix, media_type = self._MEDIA_TYPES.get(
                content_format, ("bin", "application/octet-stream")
            )
            name = path.rsplit("/", 1)[-1] or f"{document_id}.{suffix}"
            attachments.append(
                Attachment(
                    filename=name, media_type=media_type, document_id=document_id
                )
            )
        return tuple(attachments)

    def _ground_email(
        self, entity, sender, intent: EmailIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        if not intent.draft.to:
            raise IntentRejection(
                "an email needs at least one recipient; name them by full "
                "name as they appear in the thread or the directory"
            )
        minted: list[PersonRecordPayload] = []
        to = self._resolve_or_mint_people(intent.draft.to, minted)
        cc = self._resolve_or_mint_people(intent.draft.cc, minted)
        if intent.thread_ref is not None:
            if intent.thread_ref not in self._world.thread_ids:
                raise IntentRejection(f"unknown thread {intent.thread_ref!r}")
            thread_id = intent.thread_ref
            # Wake-driven replies can ping-pong past any auto-grant cap; a
            # real thread this long has become a meeting or a task. The
            # rejection is feedback the persona remembers.
            length = sum(
                1 for thread in self._world.threads.values() if thread == thread_id
            )
            if length >= 12:
                raise IntentRejection(
                    f"thread {thread_id} already carries {length} messages; "
                    "move the work forward — schedule a meeting, open or "
                    "update a ticket, or let it rest"
                )
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
            subject=self._dereference(intent.draft.subject),
            body=self._dereference(intent.draft.body),
            attachments=self._resolve_attachments(intent.draft.attachment_refs),
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
        # A chat thread is one level deep in the product these surfaces
        # mirror: every reply carries the *root's* timestamp and there is
        # no reply-to-a-reply. The persona replies to whatever it was
        # shown, which is the newest message, so replies chained --
        # measured on four recorded days, 44 of 84 replies had a parent
        # that was itself a reply, with chains nine deep.
        #
        # Two things were wrong with that. The served surface set
        # `thread_ts` to the immediate parent, so a message three deep
        # named another reply as its thread root, which no real workspace
        # can represent; and a chain gives every root exactly one direct
        # reply, so a four-message exchange reads as no thread at all
        # (threaded_reply_share 0.089 against a floor of 0.30).
        #
        # Flattened here, at the source, so the log is right and the
        # surface derives correctly. The tool's own write path already
        # states this rule -- "a reply addressed at a reply belongs to
        # that thread's parent, as in Slack" -- and its single level of
        # resolution becomes sufficient once nothing nests deeper.
        reply_to = (
            self._world.chat_thread_roots.get(intent.reply_to_ref, intent.reply_to_ref)
            if intent.reply_to_ref is not None
            else None
        )
        payload = ChatMessagePayload(
            kind="chat.message",
            chat_message_id=self._minter.mint("chm"),
            conversation_id=conversation_id,
            reply_to=reply_to,
            sender=sender,
            body=self._dereference(intent.draft.body),
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
                title=self._dereference(create.title),
                description=self._dereference(create.description),
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
            raise IntentRejection(
                "ticket intent needs a ticket_ref or create spec", engine_fault=True
            )
        values = self._world.tickets.get(intent.ticket_ref)
        if values is None:
            raise IntentRejection(f"unknown ticket {intent.ticket_ref!r}")
        if intent.changes:
            # Person-valued fields are resolved here for the same reason
            # the create path resolves `assignee_ref`: a persona names a
            # colleague and the column is typed `Ref("person")`. Only the
            # create path did it. One matter in a six-month world ended up
            # with `responsible_person` holding the string "Cecile
            # Marchand", which no join against the people table can match —
            # the row does not error, it silently leaves every result that
            # groups by who is responsible.
            #
            # Resolving `old` too is not symmetry for its own sake. The
            # staleness check below compares against state that holds an
            # id, so a persona naming the current assignee — reading it
            # correctly off the surface it was shown — was rejected for
            # claiming a value that was never stale.
            #
            # Collapsed first: a persona that changed one field twice in a
            # single action disagreed with itself, and only the net change
            # ever durably held. Recording both puts a transition in
            # `matter_history` that the record never had.
            changes = tuple(
                change.model_copy(
                    update={
                        "old": self._resolve_person_field(change.old),
                        "new": self._resolve_person_field(change.new),
                    }
                )
                if change.field in PERSON_TICKET_FIELDS
                else change
                for change in collapse_field_changes(intent.changes)
            )
            for change in changes:
                if change.field in values and values[change.field] != change.old:
                    raise IntentRejection(
                        f"{change.field} has moved on since you last "
                        f"looked — it reads {values[change.field]}, not "
                        f"{change.old}; check it and make the change again"
                    )
                if change.field == "status" and change.new not in self._vocab.statuses:
                    raise IntentRejection(f"unknown ticket status {change.new!r}")
                if (
                    change.field == "priority"
                    and change.new not in self._vocab.priorities
                ):
                    raise IntentRejection(f"unknown priority {change.new!r}")
            # The check above compares against the world as it stands now,
            # but the event lands after a delay — so two people who both
            # look at an open ticket in the same tick both ground cleanly,
            # and the second one's `old` is a value the record has already
            # left behind. Four such transitions failed validation in a
            # fifteen-day run, and they land in `matter_history`, which is
            # exactly what the status-integrity task reads to decide which
            # engagements moved backwards.
            #
            # So book the change against the GM's own state at grounding
            # rather than only at landing. The next intent in the same tick
            # then sees the value this one is about to write and is
            # rejected or restated, instead of recording a transition from
            # a status the ticket no longer had.
            values.update(
                {
                    change.field: change.new
                    for change in changes
                    if change.field in values
                }
            )
            payload = TicketUpdatedPayload(
                kind="ticket.updated",
                ticket_id=intent.ticket_ref,
                actor=sender,
                changes=changes,
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
                body=self._dereference(intent.comment),
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
            raise IntentRejection(
                "that update changes nothing and carries no note; say what "
                "moved, or leave a comment saying why nothing did"
            )
        return tuple(drafts)

    def _ground_document(
        self, entity, sender, intent: DocumentEditIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        if intent.create is not None:
            # A deliverable with nothing in it is not a deliverable.
            #
            # Nine documents in a six-month world were created with empty
            # content and materialized as zero-byte files -- work product
            # that the record registers and the folder loses. The count by
            # suffix cannot see it: nine .docx files, all of them real to
            # every check that asks how many documents exist.
            #
            # Refused rather than dropped, for the same reason the path
            # collision below is: the rejection reaches the persona, which
            # can write the document or pick another action. Silently not
            # creating it would leave the persona believing it had.
            # A file room cannot hold two files at one path, and the
            # materializer does not pretend otherwise: the second write
            # overwrites the first. So the record said fifteen documents
            # and the folder held thirteen, with the earlier work invisible
            # to anything reading the surface — including a task grading
            # it.
            #
            # Rejecting rather than silently versioning is the point: the
            # persona wanted a document that already exists, and the note
            # tells it which one to work forward. That is also what the
            # deliverable turn is for, and one third of those turns are
            # meant to be revisions rather than first drafts.
            # Key on the file this will actually become, not on the path
            # the author typed. The file room keeps only the top-level
            # segment, so two documents differing in an intermediate
            # directory produce one file — and the guard compared declared
            # paths, which are distinct. Measured: 32 documents, 32
            # distinct declared paths, 30 files.
            # Validated before anything is reserved. `_validated_format`
            # parses the content and refuses an empty or malformed
            # document, and every one of those rejections used to happen
            # *after* the filed name was claimed — so a persona whose
            # workbook JSON was malformed burned that filename for the
            # rest of the run, and its retry with correct content
            # collided with a document that had never been created.
            content_format = _validated_format(intent.create)
            filed = filed_name(intent.create.path, content_format)
            existing = self._world.documents_by_filed_name.get(filed)
            if existing is not None:
                raise IntentRejection(
                    f"{intent.create.path} files as {filed}, which "
                    f"{existing} already holds; revise that document "
                    "instead of writing over it, or file this one under a "
                    "name of its own"
                )
            # Reserve at resolve time. Creates in one cohort all resolve
            # before any draft lands, so three documents reached one path
            # with no rejection at all — the revision branch below already
            # bumps its head for exactly this reason.
            document_id = self._minter.mint("doc")
            self._world.documents_by_filed_name[filed] = document_id
            payload = DocumentCreatedPayload(
                kind="document.created",
                document_id=document_id,
                author=sender,
                title=intent.create.title,
                path=intent.create.path,
                location="repository",
                content_format=content_format,
                content=intent.create.content,
            )
        else:
            if intent.document_ref is None or intent.edit is None:
                raise IntentRejection(
                    "document intent needs a document_ref and edit, or a create spec",
                    engine_fault=True,
                )
            document_id = self._world.resolve_document(intent.document_ref)
            if document_id is None:
                raise IntentRejection(f"unknown document {intent.document_ref!r}")
            # Bump the head at resolve time: a second edit resolved before the
            # first occurs must still get a distinct revision number.
            # A revision must still be the form the document is. Without
            # this, working a workbook forward silently replaces it with
            # prose that keeps the workbook's declared format.
            _reject_unless_parsable(
                self._world.document_formats.get(document_id, "markdown"),
                intent.edit.new_content,
                intent.document_ref,
            )
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
        message_ref = intent.chat_message_ref
        conversation_id = self._world.chat_message_conversations.get(message_ref)
        if conversation_id is None:
            # The commonest slip is naming the conversation instead of a
            # message; reacting to its latest message is what they meant.
            resolved = self._world.resolve_conversation(message_ref)
            if resolved is not None:
                latest = self._world.last_chat_message.get(resolved)
                if latest is None:
                    raise IntentRejection(
                        f"conversation {resolved} has no messages to react to"
                    )
                message_ref = latest
                conversation_id = resolved
            else:
                raise IntentRejection(f"unknown chat message {message_ref!r}")
        members = self._world.conversations.get(conversation_id, ())
        if sender not in members:
            raise IntentRejection(f"{sender} is not in {conversation_id}")
        payload = ChatReactionAddedPayload(
            kind="chat.reaction.added",
            conversation_id=conversation_id,
            chat_message_id=message_ref,
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

    def _ground_timesheet(
        self, entity, sender, intent: TimesheetIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        """A day of time in one turn.

        Unknown engagements are dropped with a note rather than failing the
        whole day: one bad ref should not cost a professional their entire
        timesheet, and the note still teaches.
        """

        drafts: list[EventDraft] = []
        unknown: list[str] = []
        for entry in intent.entries:
            if entry.ticket_ref not in self._world.tickets:
                unknown.append(entry.ticket_ref)
                continue
            payload = TimeLoggedPayload(
                kind="work.time.logged",
                person_id=sender,
                ticket_id=entry.ticket_ref,
                minutes=entry.minutes,
                note=entry.note,
                rate_cents=self._bill_rates.get(sender),
                billable=entry.billable,
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
        if unknown and not drafts:
            # Every entry invalid. This used to raise with no note, so the
            # loss was invisible: a world whose people had *no* valid code
            # for a whole day measured 0.0% dropped and passed the gate
            # that exists to catch exactly that. The bias ran one way —
            # the worse the structural gap, the likelier a persona has no
            # valid code at all, so the more of the loss disappeared.
            raise IntentRejection(
                "none of these engagements exist: "
                + ", ".join(sorted(set(unknown)))
                + "; log time against the ones on your own engagement list",
                dropped_entries=len(unknown),
                unknown_refs=tuple(sorted(set(unknown))),
            )
        if unknown:
            note = SimGmNotePayload(
                kind="sim.gm.note",
                note=(
                    f"dropped {len(unknown)} timesheet entries against unknown "
                    f"engagements {sorted(set(unknown))}"
                ),
                entity=entity,
                dropped_entries=len(unknown),
                unknown_refs=tuple(sorted(set(unknown))),
            )
            drafts.append(
                EventDraft(
                    tag=note.kind,
                    source="gm",
                    caused_by=event.event_id,
                    payload=note,
                    delay=delay,
                )
            )
        return tuple(drafts)

    def _ground_calendar(
        self, entity, sender, intent: CalendarIntent, event, delay
    ) -> tuple[EventDraft, ...]:
        if intent.schedule is not None:
            # The clock arithmetic is the referee's. A persona says "in two
            # days at 14:00"; turning that into seconds on the simulation
            # clock is exactly the step a language model was getting wrong
            # -- see CalendarScheduleSpec.
            schedule = intent.schedule
            midnight = (int(event.time) // SECONDS_PER_DAY) * SECONDS_PER_DAY
            day = midnight + schedule.day_offset * SECONDS_PER_DAY
            start = day + _clock_seconds(schedule.start_clock)
            end = day + _clock_seconds(schedule.end_clock)
            if end <= start:
                raise IntentRejection(
                    f"calendar event {schedule.title!r} ends at "
                    f"{schedule.end_clock} which is not after "
                    f"{schedule.start_clock}; give it a positive duration"
                )
            if (
                not _WORKING_HOURS[0]
                <= _clock_seconds(schedule.start_clock)
                <= (_WORKING_HOURS[1])
            ):
                raise IntentRejection(
                    f"calendar event {schedule.title!r} starts at "
                    f"{schedule.start_clock}; book working sessions inside "
                    "ordinary working hours"
                )
            attendees = self._resolve_people((sender, *schedule.attendee_refs))
            payload = CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=self._minter.mint("cal"),
                organizer=sender,
                title=schedule.title,
                start=start,
                end=end,
                attendees=attendees,
                description=schedule.description,
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
            raise IntentRejection(
                "calendar intent needs a schedule or a response", engine_fault=True
            )
        if intent.respond.calendar_event_ref not in self._world.calendar_events:
            # Every other surface rejects an id it has never issued; without
            # this one, an invented cal- ref became a response event and the
            # materializer refused the whole log as incoherent.
            raise IntentRejection(
                f"unknown calendar event {intent.respond.calendar_event_ref!r}"
            )
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
            engine_detail=intent.engine_detail,
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
            raise IntentRejection(
                "nothing in that plan falls inside the working day"
            )
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
