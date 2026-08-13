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
    SimWakePayload,
)
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.events.email import Attachment, EmailMessagePayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.hashing import content_hash
from workbench.core.ids import IdMinter
from workbench.core.seed import Seed
from workbench.simulation.engine.queue import ScheduledEvent
from workbench.simulation.errors import ConfigError
from workbench.simulation.gm.grounded import TicketVocabulary
from workbench.simulation.persona.params import ProfessionalWorkerParams
from workbench.simulation.workplace.spec import WorkplaceSpec

# Bumping this invalidates every recorded run built from a workplace spec.
COMPILER_VERSION = 1


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


class CompiledWorkplace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workplace_id: str
    config_hash: str
    genesis: tuple[Event, ...]
    scheduled: tuple[ScheduledEvent, ...]
    personas: tuple[tuple[str, ProfessionalWorkerParams], ...]
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


def _entity_name(person_id: str) -> str:
    prefix, dash, rest = person_id.partition("-")
    return rest or person_id


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
    for person in spec.people:
        payloads.append(
            PersonRecordPayload(
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
        )
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
                content_format="markdown",
                content=document.content,
            )
        )
    for calendar_event in spec.seed_calendar:
        payloads.append(
            CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=minter.mint("cal"),
                organizer=calendar_event.organizer,
                title=calendar_event.title,
                start=_clock_to_seconds(calendar_event.start_clock),
                end=_clock_to_seconds(calendar_event.end_clock),
                attendees=calendar_event.attendees,
                description=calendar_event.description,
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
                content_format="markdown",
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
                    media_type="text/markdown",
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

    personas = tuple(
        (_entity_name(person.person_id), person.persona)
        for person in spec.people
        if person.persona is not None
    )

    # Periodic check-in turns: without these, personas act only when
    # addressed and the day dies with its reply chains.
    end_of_day_seconds = _clock_to_seconds(spec.end_of_day)
    end_time = time_offset + (spec.days - 1) * 86_400 + end_of_day_seconds
    if spec.days == 1:
        # Byte-compatible with every recorded single-day cassette: the whole
        # ladder is materialized at compile time, and no day events exist.
        day_start = time_offset + 9 * 3600
        for index, (entity_name, persona) in enumerate(personas):
            wake_time = day_start + (index + 1) * 180
            while wake_time < end_time:
                payload = SimWakePayload(kind="sim.wake", entity=entity_name)
                scheduled.append(
                    ScheduledEvent(
                        time=wake_time,
                        order=order,
                        draft=EventDraft(
                            tag=payload.kind, source="gm", payload=payload
                        ),
                    )
                )
                order += 1
                wake_time += persona.check_interval_minutes * 60
    else:
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
    entity_for_person = tuple(
        (person.person_id, _entity_name(person.person_id))
        for person in spec.people
        if person.persona is not None
    )

    return CompiledWorkplace(
        workplace_id=spec.workplace_id,
        config_hash=digest,
        genesis=genesis,
        scheduled=tuple(scheduled),
        personas=personas,
        entity_for_person=entity_for_person,
        ticket_vocabulary=spec.ticket_vocabulary,
        end_time=end_time,
        days=spec.days,
        start_date=spec.epoch.date().isoformat(),
        timezone=spec.timezone,
        end_of_day_seconds=end_of_day_seconds,
        minter=minter,
    )
