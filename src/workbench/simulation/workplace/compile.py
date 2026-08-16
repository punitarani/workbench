"""Compile a workplace spec into genesis events and a scheduled day.

Pure and deterministic: same spec and seed, same bytes. All ids are minted
here from one compile-time minter; the runtime game master absorbs them and
continues the sequences without collision.
"""

from pydantic import BaseModel, ConfigDict

from workbench.core.events import Event, EventDraft
from workbench.core.events.calendar import CalendarEventScheduledPayload
from workbench.core.events.chat import ChatConversationCreatedPayload
from workbench.core.events.control import (
    SimDayStartedPayload,
    SimRunStartedPayload,
)
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.events.email import Attachment, EmailMessagePayload
from workbench.core.events.meetings import SimMeetingConvenePayload
from workbench.core.events.people import (
    OrganizationRecordPayload,
    PersonRecordPayload,
)
from workbench.core.events.tickets import TicketCreatedPayload
from workbench.core.hashing import content_hash
from workbench.core.ids import IdMinter
from workbench.core.seed import Seed
from workbench.simulation.actors.client import ClientActorParams
from workbench.simulation.engine.queue import ScheduledEvent
from workbench.simulation.errors import ConfigError
from workbench.simulation.gm.grounded import TicketVocabulary
from workbench.simulation.persona.params import ProfessionalWorkerParams
from workbench.simulation.workplace.spec import PersonSpec, WorkplaceSpec

# Bumping this invalidates every recorded run built from a workplace spec.
# v2: the day chain owns wake cohorts; the compile-time ladder is gone.
COMPILER_VERSION = 2

_MEDIA_TYPES = {
    "markdown": "text/markdown",
    "spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    "formatted": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}


def config_hash(spec: WorkplaceSpec, seed: Seed) -> str:
    return content_hash(
        {
            "compiler_version": COMPILER_VERSION,
            "spec": spec.model_dump(mode="json"),
            "seed_root": seed.root,
        }
    )


def _clock_to_seconds(clock: str) -> int:
    hours, _, minutes = clock.partition(":")
    return int(hours) * 3600 + int(minutes) * 60


def _recurrence_days(recurrence: str, days: int) -> tuple[int, ...]:
    """Which sim days a standing meeting lands on.

    Sim days are workdays, so "daily" is every day index and "weekly" is
    every fifth — no calendar arithmetic, and no meeting on a Saturday
    that the simulation does not have.
    """

    match recurrence:
        case "daily":
            return tuple(range(max(1, days)))
        case "weekly":
            return tuple(range(0, max(1, days), 5))
        case _:
            return (0,)


class CompiledWorkplace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workplace_id: str
    config_hash: str
    genesis: tuple[Event, ...]
    scheduled: tuple[ScheduledEvent, ...]
    personas: tuple[tuple[str, ProfessionalWorkerParams], ...]
    # Slim outside-world actors: cue-driven, reply-granted, never woken.
    clients: tuple[tuple[str, ClientActorParams], ...] = ()
    # Persona-bearing scripted arrivals: their entities are built when the
    # arrival's person.record occurs, never at genesis (so they get no
    # compile-time wakes and observe nothing before they exist).
    arrivals: tuple[tuple[str, ProfessionalWorkerParams], ...] = ()
    entity_for_person: tuple[tuple[str, str], ...]
    ticket_vocabulary: TicketVocabulary
    end_time: int
    days: int = 1
    start_date: str = ""
    timezone: str = "UTC"
    end_of_day_seconds: int = 0
    # Final compile-time counters; the runtime GM starts from these so its
    # minted ids can never collide with scheduled-but-not-yet-occurred ones.
    minter: IdMinter
    wake_grid_minutes: int = 30
    timesheets: bool = False
    deliverables: bool = False
    delivery_quantum_seconds: int = 300


def _entity_name(person_id: str) -> str:
    prefix, dash, rest = person_id.partition("-")
    return rest or person_id


def _person_payload(person: PersonSpec) -> PersonRecordPayload:
    return PersonRecordPayload(
        kind="person.record",
        person_id=person.person_id,
        name=person.name,
        email_address=person.email_address,
        title=person.title,
        department=person.department,
        manager=person.manager,
        affiliation=person.affiliation,
        timezone=person.timezone,
    )


def compile_workplace(
    spec: WorkplaceSpec,
    seed: Seed,
    *,
    time_offset: int = 0,
    starting_minter: IdMinter | None = None,
    include_genesis: bool = True,
) -> CompiledWorkplace:
    """Compile a workplace. The hybrid parameters continue an existing world:
    ``time_offset`` shifts every scheduled time onto an absolute timeline,
    ``starting_minter`` continues id sequences past a prior history, and
    ``include_genesis=False`` skips genesis for a world that already exists."""

    people = {person.person_id for person in spec.people}
    for arrival in spec.arrivals:
        if arrival.person.person_id in people:
            raise ConfigError(
                f"arrival duplicates existing person {arrival.person.person_id!r}"
            )
        people.add(arrival.person.person_id)

    def require_person(ref: str, where: str) -> None:
        if ref not in people:
            raise ConfigError(f"{where} references unknown person {ref!r}")

    for channel in spec.channels:
        for member in channel.members:
            require_person(member, f"channel {channel.name}")
    for document in spec.seed_documents:
        require_person(document.author, f"seed document {document.path}")
    for calendar_event in spec.seed_calendar:
        require_person(calendar_event.organizer, f"calendar {calendar_event.title}")
        for attendee in calendar_event.attendees:
            require_person(attendee, f"calendar {calendar_event.title}")
    for ticket in spec.seed_tickets:
        require_person(ticket.actor, f"seed ticket {ticket.title}")
        require_person(ticket.requester, f"seed ticket {ticket.title}")
        if ticket.assignee is not None:
            require_person(ticket.assignee, f"seed ticket {ticket.title}")
    for arrival in spec.day_script:
        require_person(arrival.sender, "day script")
        for recipient in (*arrival.to, *arrival.cc):
            require_person(recipient, "day script")

    minter = (
        starting_minter.model_copy(deep=True)
        if starting_minter is not None
        else IdMinter()
    )
    digest = config_hash(spec, seed)

    payloads: list = [
        SimRunStartedPayload(
            kind="sim.run.started",
            run_id=f"run-{spec.workplace_id}-{seed.root}",
            seed_root=seed.root,
            workplace_id=spec.workplace_id,
            config_hash=digest,
            schema_version=1,
            epoch=spec.epoch.isoformat(),
            timezone=spec.timezone,
        )
    ]
    for organization in spec.organizations:
        payloads.append(
            OrganizationRecordPayload(
                kind="org.record",
                org_id=organization.org_id,
                name=organization.name,
                category=organization.category,
            )
        )
    for person in spec.people:
        payloads.append(_person_payload(person))
    for channel in spec.channels:
        payloads.append(
            ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id=minter.mint("cnv"),
                conversation_type="channel",
                name=channel.name,
                members=channel.members,
            )
        )
    for document in spec.seed_documents:
        payloads.append(
            DocumentCreatedPayload(
                kind="document.created",
                document_id=minter.mint("doc"),
                author=document.author,
                title=document.title,
                path=document.path,
                location="repository",
                content_format=document.content_format,
                content=document.content,
            )
        )
    persona_people = {
        person.person_id for person in spec.people if person.persona is not None
    }
    seed_convenes: list[tuple[object, int]] = []
    for calendar_event in spec.seed_calendar:
        base_start = _clock_to_seconds(calendar_event.start_clock)
        base_end = _clock_to_seconds(calendar_event.end_clock)
        # A standing meeting is one spec row and many instances, each with
        # its own id: sharing one id across days would make every RSVP and
        # every transcript point at the same event.
        for day in _recurrence_days(calendar_event.recurrence, spec.days):
            calendar_id = minter.mint("cal")
            start_seconds = day * 86_400 + base_start
            end_seconds = day * 86_400 + base_end
            payloads.append(
                CalendarEventScheduledPayload(
                    kind="calendar.event.scheduled",
                    calendar_event_id=calendar_id,
                    organizer=calendar_event.organizer,
                    title=calendar_event.title,
                    start=start_seconds,
                    end=end_seconds,
                    attendees=calendar_event.attendees,
                    description=calendar_event.description,
                )
            )
            # Genesis events never pass through GM consequences, so seed
            # meetings convene from compile: same payload, scheduled at the
            # event's start.
            simulated = tuple(
                _entity_name(person_id)
                for person_id in calendar_event.attendees
                if person_id in persona_people
            )
            if len(simulated) >= 2:
                seed_convenes.append(
                    (
                        SimMeetingConvenePayload(
                            kind="sim.meeting.convene",
                            meeting_id=minter.mint("mtg"),
                            calendar_event_id=calendar_id,
                            title=calendar_event.title,
                            description=calendar_event.description or "",
                            attendees=simulated,
                            duration_seconds=max(60, end_seconds - start_seconds),
                        ),
                        start_seconds,
                    )
                )

    for ticket in spec.seed_tickets:
        payloads.append(
            TicketCreatedPayload(
                kind="ticket.created",
                ticket_id=minter.mint("tkt"),
                actor=ticket.actor,
                title=ticket.title,
                description=ticket.description,
                requester=ticket.requester,
                assignee=ticket.assignee,
                status=ticket.status,
                priority=ticket.priority,
                ticket_type=ticket.ticket_type,
                client_ref=ticket.client_ref,
            )
        )

    if not include_genesis:
        genesis: tuple[Event, ...] = ()
    else:
        genesis = tuple(
            Event(seq=seq, time=0, tag=p.kind, source="gm", payload=p)
            for seq, p in enumerate(payloads)
        )

    scheduled: list[ScheduledEvent] = []
    order = 0
    for arrival in sorted(spec.arrivals, key=lambda a: (a.day, a.at)):
        payload = _person_payload(arrival.person)
        scheduled.append(
            ScheduledEvent(
                time=time_offset + arrival.day * 86_400 + _clock_to_seconds(arrival.at),
                order=order,
                draft=EventDraft(tag=payload.kind, source="gm", payload=payload),
            )
        )
        order += 1
    for arrival in sorted(spec.day_script, key=lambda a: a.at):
        arrival_time = time_offset + _clock_to_seconds(arrival.at)
        attachments: tuple[Attachment, ...] = ()
        if arrival.attachment is not None:
            document_id = minter.mint("doc")
            document_payload = DocumentCreatedPayload(
                kind="document.created",
                document_id=document_id,
                author=arrival.sender,
                title=arrival.attachment.title,
                path=arrival.attachment.path,
                location="attachment",
                content_format=arrival.attachment.content_format,
                content=arrival.attachment.content,
            )
            scheduled.append(
                ScheduledEvent(
                    time=arrival_time,
                    order=order,
                    draft=EventDraft(
                        tag=document_payload.kind,
                        source="gm",
                        payload=document_payload,
                    ),
                )
            )
            order += 1
            attachments = (
                Attachment(
                    filename=arrival.attachment.path.rsplit("/", 1)[-1],
                    media_type=_MEDIA_TYPES[arrival.attachment.content_format],
                    document_id=document_id,
                ),
            )
        email_payload = EmailMessagePayload(
            kind="email.message",
            message_id=minter.mint("msg"),
            thread_id=minter.mint("thr"),
            in_reply_to=None,
            sender=arrival.sender,
            to=arrival.to,
            cc=arrival.cc,
            subject=arrival.subject,
            body=arrival.body,
            attachments=attachments,
        )
        scheduled.append(
            ScheduledEvent(
                time=arrival_time,
                order=order,
                draft=EventDraft(
                    tag=email_payload.kind,
                    source=_entity_name(arrival.sender),
                    payload=email_payload,
                ),
            )
        )
        order += 1

    # Personas are told the firm's own ticket vocabulary rather than
    # guessing it. A hardcoded default of "Open, In Progress, Blocked,
    # Closed" cost 31 rejected status changes in one half-epoch: the
    # personas used the words they were given, and this firm calls them
    # open, in-progress, waiting-client, review, closed.
    vocabulary = (
        "statuses: "
        + ", ".join(spec.ticket_vocabulary.statuses)
        + "; priorities: "
        + ", ".join(spec.ticket_vocabulary.priorities)
    )
    personas = tuple(
        (
            _entity_name(person.person_id),
            person.persona.model_copy(update={"ticket_vocabulary": vocabulary}),
        )
        for person in spec.people
        if person.persona is not None
    )
    clients = tuple(
        (_entity_name(person.person_id), person.client_persona)
        for person in spec.people
        if person.client_persona is not None and person.persona is None
    )

    # Periodic check-in turns: without these, personas act only when
    # addressed and the day dies with its reply chains.
    end_of_day_seconds = _clock_to_seconds(spec.end_of_day)
    end_time = time_offset + (spec.days - 1) * 86_400 + end_of_day_seconds
    # Every run — single-day included — unfolds through the day chain:
    # sim.day.started mints that day's wake cohorts at runtime (COMPILER
    # v2; the compile-time ladder died with the pre-pivot cassettes).
    started = SimDayStartedPayload(
        kind="sim.day.started", day=spec.epoch.date().isoformat()
    )
    scheduled.append(
        ScheduledEvent(
            time=time_offset,
            order=order,
            draft=EventDraft(tag=started.kind, source="gm", payload=started),
        )
    )
    order += 1
    for convene, start_seconds in seed_convenes:
        scheduled.append(
            ScheduledEvent(
                time=time_offset + start_seconds,
                order=order,
                draft=EventDraft(tag=convene.kind, source="gm", payload=convene),
            )
        )
        order += 1
    arrival_personas = tuple(
        (_entity_name(arrival.person.person_id), arrival.person.persona)
        for arrival in spec.arrivals
        if arrival.person.persona is not None
    )
    # The GM's routing map knows arrivals from the start: routing to an
    # entity that does not exist yet is harmless (the engine skips it).
    entity_for_person = tuple(
        (person_id, _entity_name(person_id))
        for person_id in (
            *(p.person_id for p in spec.people if p.persona is not None),
            *(
                p.person_id
                for p in spec.people
                if p.client_persona is not None and p.persona is None
            ),
            *(
                a.person.person_id
                for a in spec.arrivals
                if a.person.persona is not None
            ),
        )
    )

    return CompiledWorkplace(
        workplace_id=spec.workplace_id,
        config_hash=digest,
        genesis=genesis,
        scheduled=tuple(scheduled),
        personas=personas,
        clients=clients,
        arrivals=arrival_personas,
        entity_for_person=entity_for_person,
        ticket_vocabulary=spec.ticket_vocabulary,
        end_time=end_time,
        days=spec.days,
        start_date=spec.epoch.date().isoformat(),
        timezone=spec.timezone,
        end_of_day_seconds=end_of_day_seconds,
        minter=minter,
        wake_grid_minutes=spec.wake_grid_minutes,
        timesheets=spec.timesheets,
        deliverables=spec.deliverables,
        delivery_quantum_seconds=spec.delivery_quantum_seconds,
    )
