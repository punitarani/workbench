"""The Calder epoch: the firm simulated LLM-first from day zero.

No pre-built chronicle — genesis is the spec itself (people, channels,
seed documents, standing meetings), and every day after it unfolds
through the day chain: plans, wakes, meetings, reflections, and a client
world stirred by the seeded season director. Maya arrives March 2 as a
scripted arrival, exactly as she did in the chronicle era.

``epoch_spec(days=N)`` is the one knob: 2 for the acceptance cassette,
5 for the flagship week, 194 for the six-month epoch.
"""

from datetime import date

from workbench.core.events.chat import ChatConversationCreatedPayload
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.seed import Seed
from workbench.simulation.actors.client import ClientActorParams
from workbench.simulation.director import PoissonCueSchedule
from workbench.simulation.workplace.spec import (
    ChannelSpec,
    PersonArrival,
    PersonSpec,
    SeedCalendarEvent,
    SeedDocument,
    WorkplaceSpec,
)
from workbench.workplaces.calder.genesis import build_genesis
from workbench.workplaces.calder.people import ARRIVAL, ARRIVAL_DATE
from workbench.workplaces.calder.season import CLIENT_PROFILES, season_multipliers
from workbench.workplaces.calder.spec import _RECORDS, LIVE_DAY_SPEC

EPOCH_START = "2026-01-05"

# Firm-side contacts each client habitually writes to, by full name.
_CLIENT_CONTACTS: dict[str, tuple[str, ...]] = {
    "per-dana-whitfield": ("Gabriel Fontes", "Victor Alade"),
    "per-marco-petrosyan": ("Gabriel Fontes", "Sylvia Nakamura"),
    "per-evan-doyle": ("Gabriel Fontes", "Lucia Mendes"),
    "per-reuben-tate": ("Gabriel Fontes",),
    "per-alice-kwon": ("Colin Mackey", "Elias Finch"),
    "per-frank-osei": ("Desmond Ortiz",),
    "per-sana-qureshi": ("Victor Alade",),
    "per-margot-ellison": ("Elias Finch",),
    "per-gloria-nunez": ("Lucia Mendes",),
    "per-naomi-castellanos": ("Imogen Carraway",),
    "per-denise-archer": ("Sylvia Nakamura",),
}

_TEMPERAMENTS: dict[str, str] = {
    "per-dana-whitfield": "Precise and numbers-fluent; expects the same back.",
    "per-marco-petrosyan": "Warm, hurried, writes like he talks.",
    "per-evan-doyle": "Formal, lender-minded, wants dates and commitments.",
    "per-reuben-tate": "Casual and direct; hates paperwork.",
    "per-alice-kwon": "Apologetic about the books, grateful for patience.",
    "per-frank-osei": "Blunt, margin-obsessed, short sentences.",
    "per-sana-qureshi": "Fast, technical, thinks in bullet points.",
    "per-margot-ellison": "Organized and courteous; plans ahead.",
    "per-gloria-nunez": "Chatty, thorough, includes every detail.",
    "per-naomi-castellanos": "Mission-first, careful with donor money.",
    "per-denise-archer": "Bureaucratic boilerplate with reference numbers.",
}


def _client_params(person_id: str) -> ClientActorParams:
    record = _RECORDS[person_id]
    return ClientActorParams(
        person_id=person_id,
        name=record.name,
        organization=record.department,
        role=record.title,
        temperament=_TEMPERAMENTS[person_id],
        contacts=_CLIENT_CONTACTS[person_id],
    )


def _people() -> tuple[PersonSpec, ...]:
    people: list[PersonSpec] = []
    for person in LIVE_DAY_SPEC.people:
        if person.person_id == ARRIVAL.person_id:
            continue  # Maya arrives mid-epoch, not at genesis.
        if person.person_id in _CLIENT_CONTACTS:
            people.append(
                person.model_copy(
                    update={
                        "persona": None,
                        "client_persona": _client_params(person.person_id),
                    }
                )
            )
        else:
            people.append(person)
    # Externals the live-day script never used become clients too.
    for person_id in _CLIENT_CONTACTS:
        if any(person.person_id == person_id for person in people):
            continue
        record = _RECORDS[person_id]
        people.append(
            PersonSpec(
                person_id=record.person_id,
                name=record.name,
                email_address=record.email_address,
                title=record.title,
                department=record.department,
                manager=record.manager,
                affiliation=record.affiliation,
                timezone=record.timezone,
                persona=None,
                client_persona=_client_params(person_id),
            )
        )
    return tuple(people)


def _seed_surfaces() -> tuple[tuple[ChannelSpec, ...], tuple[SeedDocument, ...]]:
    """Channels and documents from the same authored genesis data the
    chronicle used — rebuilt as spec fields so compile owns t=0."""

    genesis = build_genesis(Seed(root=42))
    channels: list[ChannelSpec] = []
    documents: list[SeedDocument] = []
    epoch_people = {person.person_id for person in _people()} | {ARRIVAL.person_id}
    for event in genesis.events:
        payload = event.payload
        if (
            isinstance(payload, ChatConversationCreatedPayload)
            and payload.name is not None
        ):
            members = tuple(
                member for member in payload.members if member in epoch_people
            )
            channels.append(ChannelSpec(name=payload.name, members=members))
        elif isinstance(payload, DocumentCreatedPayload):
            documents.append(
                SeedDocument(
                    author=payload.author,
                    title=payload.title,
                    path=payload.path,
                    content=payload.content,
                    content_format=payload.content_format,
                )
            )
    return tuple(channels), tuple(documents)


def epoch_spec(days: int = 194) -> WorkplaceSpec:
    channels, documents = _seed_surfaces()
    arrival_day = (
        date.fromisoformat(ARRIVAL_DATE) - date.fromisoformat(EPOCH_START)
    ).days
    arrivals = ()
    if days > arrival_day:
        maya = next(
            person
            for person in LIVE_DAY_SPEC.people
            if person.person_id == ARRIVAL.person_id
        )
        arrivals = (PersonArrival(at="08:30", day=arrival_day, person=maya),)
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return LIVE_DAY_SPEC.model_copy(
        update={
            "epoch": datetime.fromisoformat(f"{EPOCH_START}T00:00:00").replace(
                tzinfo=ZoneInfo(LIVE_DAY_SPEC.timezone)
            ),
            "days": days,
            "people": _people(),
            "arrivals": arrivals,
            "channels": channels,
            "seed_documents": documents,
            "seed_calendar": (
                SeedCalendarEvent(
                    organizer="per-victor-alade",
                    title="Tax group huddle",
                    start_clock="09:30",
                    end_clock="09:45",
                    attendees=(
                        "per-victor-alade",
                        "per-desmond-ortiz",
                        "per-lucia-mendes",
                        "per-nadia-osman",
                    ),
                    description="Queue, blockers, and who needs review.",
                ),
            ),
            "day_script": (),
        }
    )


def epoch_director(seed: Seed) -> PoissonCueSchedule:
    return PoissonCueSchedule(
        seed=seed,
        clients=CLIENT_PROFILES,
        season=season_multipliers,
        max_cues_per_day=8,
    )
