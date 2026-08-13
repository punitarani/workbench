"""Genesis for Hartwell & Marsh LLP: the world as it stands on Monday
2026-03-02, before the seven-month history begins.

Everything is data assembled into time-zero events. Every minted id comes
from one IdMinter; the statically declared org ids are re-minted against it
so the exported counter state is provably truthful.
"""

from collections.abc import Mapping
from importlib import resources

from pydantic import BaseModel, ConfigDict

from workbench.core.events import Event, EventPayload
from workbench.core.events.chat import ChatConversationCreatedPayload
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.events.tickets import TicketCreatedPayload
from workbench.core.hashing import content_hash
from workbench.core.ids import IdMinter
from workbench.core.seed import Seed, derive_rng
from workbench.simulation.chronicle.calendar import CalendarWindow
from workbench.simulation.chronicle.procedural import (
    CastMember,
    ChatChannel,
    DayProfile,
    DmThread,
    OpenMatter,
    ProceduralCast,
    Timekeeper,
)
from workbench.simulation.errors import ConfigError
from workbench.workplaces.hartwell.people import (
    EMPLOYEES,
    EXTERNALS,
    ORGS,
    TIMEKEEPER_IDS,
)

WORKPLACE_ID = "hartwell"
TIMEZONE = "America/Los_Angeles"
EPOCH_ISO = "2026-03-02T00:00:00-08:00"
SCHEMA_VERSION = 1
DIRECTED_ONLY_EXTERNAL_IDS = frozenset({"per-olivia-chen"})

WINDOW = CalendarWindow(
    start_date="2026-03-02", end_date="2026-09-30", timezone=TIMEZONE
)

# US federal holidays for 2026, in observed form, paired with how much of
# a normal working day the firm still generates. A twelve-person practice
# does not go dark: partners clear mail, a litigator works a brief. Only
# Memorial Day and Juneteenth fall inside the March-June window; the rest
# are carried so the table is a calendar rather than a special case.
FEDERAL_HOLIDAYS_2026: tuple[tuple[str, str, float], ...] = (
    ("2026-01-01", "New Year's Day", 0.08),
    ("2026-01-19", "Birthday of Martin Luther King, Jr.", 0.30),
    ("2026-02-16", "Washington's Birthday", 0.35),
    ("2026-05-25", "Memorial Day", 0.10),
    ("2026-06-19", "Juneteenth National Independence Day", 0.35),
    ("2026-07-03", "Independence Day (observed)", 0.12),
    ("2026-09-07", "Labor Day", 0.10),
    ("2026-10-12", "Columbus Day", 0.45),
    ("2026-11-11", "Veterans Day", 0.40),
    ("2026-11-26", "Thanksgiving Day", 0.05),
    ("2026-12-25", "Christmas Day", 0.05),
)
_HOLIDAY_INTENSITY = {day: intensity for day, _, intensity in FEDERAL_HOLIDAYS_2026}

# Weekend baselines. Saturdays carry catch-up and crunch work; Sundays are
# quieter. A per-day jitter keeps some weekends silent and others busy
# instead of painting every Saturday the same shade.
_SATURDAY = 0.075
_SUNDAY = 0.045


def day_profile(seed: Seed, day_index: int) -> DayProfile:
    """How much traffic the firm generates on one calendar day."""

    day = WINDOW.iso_date(day_index)
    holiday = _HOLIDAY_INTENSITY.get(day)
    if holiday is not None:
        return DayProfile(kind="holiday", intensity=holiday)
    weekday = WINDOW.date_of(day_index).weekday()
    if weekday < 5:
        return DayProfile(kind="workday", intensity=1.0)
    base = _SATURDAY if weekday == 5 else _SUNDAY
    jitter = derive_rng(seed, "hartwell.weekend", day).uniform(0.35, 2.0)
    return DayProfile(kind="weekend", intensity=min(base * jitter, 1.0))


_EVERYONE = tuple(person.person_id for person in EMPLOYEES)

_CHANNELS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (
        "#general",
        _EVERYONE,
        "Firm-wide announcements and chatter",
        "Anything that does not belong on a specific matter.",
    ),
    (
        "#matters",
        TIMEKEEPER_IDS,
        "Active matter coordination",
        "Status, staffing, and deadlines on open matters.",
    ),
    (
        "#billing",
        (
            "per-eleanor-hartwell",
            "per-samuel-marsh",
            "per-anita-bailey",
            "per-carl-jensen",
        ),
        "Billing cycle and collections",
        "Prebills, invoices, trust balances, and fee questions.",
    ),
    (
        "#it-help",
        _EVERYONE,
        "IT and facilities requests",
        "Printers, passwords, and access badges. Tessa triages.",
    ),
)

# Standing DM pairs and each pair's expected exchanges per workday.
# Grace<->Samuel runs hot: the litigation docket flows through that
# thread, and S5 buries its correction mid-stream in a season of routine
# traffic; the other pairs run heavy enough that skimming every DM
# history end to end costs real turns. New pairs append at the end so the
# earlier pairs' seeded draws — and their message content — never move.
_DMS: tuple[tuple[str, str, float], ...] = (
    ("per-grace-adeyemi", "per-samuel-marsh", 2.1),
    ("per-eleanor-hartwell", "per-samuel-marsh", 0.7),
    ("per-marcus-liang", "per-peter-novak", 0.9),
    ("per-sofia-ramirez", "per-grace-adeyemi", 0.8),
    ("per-diane-okonkwo", "per-noah-feldstein", 0.7),
    ("per-anita-bailey", "per-carl-jensen", 0.9),
    ("per-tessa-nguyen", "per-omar-haddad", 0.6),
    ("per-eleanor-hartwell", "per-anita-bailey", 0.6),
    ("per-samuel-marsh", "per-sofia-ramirez", 0.7),
    ("per-noah-feldstein", "per-peter-novak", 0.5),
    ("per-grace-adeyemi", "per-peter-novak", 0.6),
    ("per-marcus-liang", "per-sofia-ramirez", 0.5),
)

# Fee earners: standard hourly rate in cents and the billable day the
# firm expects of them. Partners carry management load and bill less than
# the associates; paralegal rates are a third of an attorney's. These are
# the targets, not the outcome — absence, light days, and crunch move the
# realized figure day by day.
_TIMEKEEPERS: tuple[tuple[str, float, int], ...] = (
    ("per-eleanor-hartwell", 4.8, 67_500),
    ("per-samuel-marsh", 5.9, 62_500),
    ("per-diane-okonkwo", 5.6, 52_500),
    ("per-marcus-liang", 7.1, 44_500),
    ("per-sofia-ramirez", 7.0, 38_500),
    ("per-noah-feldstein", 6.7, 36_500),
    ("per-grace-adeyemi", 6.3, 21_500),
    ("per-peter-novak", 6.5, 18_500),
)

# Matter complexity and staffing, in matter declaration order. Weight is
# the share of a staffed timekeeper's day the matter competes for, so a
# contested acquisition accretes several times the hours of a lease
# renewal instead of every file coming out the same size.
_STAFFING: tuple[tuple[float, tuple[str, ...]], ...] = (
    (3.0, ("per-marcus-liang", "per-peter-novak", "per-eleanor-hartwell")),
    (0.9, ("per-sofia-ramirez", "per-grace-adeyemi", "per-samuel-marsh")),
    (0.7, ("per-diane-okonkwo", "per-peter-novak")),
    (1.7, ("per-sofia-ramirez", "per-samuel-marsh", "per-grace-adeyemi")),
    (0.5, ("per-marcus-liang", "per-peter-novak")),
    (0.4, ("per-noah-feldstein", "per-diane-okonkwo")),
    (0.35, ("per-noah-feldstein", "per-diane-okonkwo", "per-peter-novak")),
    (1.4, ("per-samuel-marsh", "per-grace-adeyemi", "per-sofia-ramirez")),
    (1.5, ("per-marcus-liang", "per-noah-feldstein", "per-eleanor-hartwell")),
    (
        2.2,
        (
            "per-sofia-ramirez",
            "per-samuel-marsh",
            "per-grace-adeyemi",
            "per-peter-novak",
        ),
    ),
)

# The rate every time entry is recorded at, directed or procedural: a
# storyline entry that carried no rate would stand out in the billing
# database as sharply as the arc it belongs to.
TIMEKEEPER_RATES: Mapping[str, int] = {
    person_id: rate for person_id, _, rate in _TIMEKEEPERS
}

_DOCUMENTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "per-eleanor-hartwell",
        "Engagement Letter (Standard Form)",
        "/firm/templates/engagement-letter.md",
        "engagement_letter_template.md",
    ),
    (
        "per-grace-adeyemi",
        "Matter Intake Checklist",
        "/firm/playbooks/matter-intake-checklist.md",
        "matter_intake_checklist.md",
    ),
    (
        "per-carl-jensen",
        "Billing & Time Entry Guidelines",
        "/firm/policies/billing-guidelines.md",
        "billing_guidelines.md",
    ),
    (
        "per-samuel-marsh",
        "Litigation Hold Notice (Template)",
        "/firm/templates/litigation-hold-notice.md",
        "litigation_hold_notice.md",
    ),
    (
        "per-marcus-liang",
        "Asset Purchase Agreement — Solstice Vineyards (Executed)",
        "/firm/precedents/asset-purchase-solstice.md",
        "asset_purchase_solstice.md",
    ),
    (
        "per-diane-okonkwo",
        "Commercial Lease — Pelican Bay Marina (Executed)",
        "/firm/precedents/commercial-lease-pelican-bay.md",
        "commercial_lease_pelican_bay.md",
    ),
    (
        "per-sofia-ramirez",
        "Discovery Response Playbook",
        "/firm/playbooks/discovery-responses.md",
        "discovery_response_playbook.md",
    ),
    (
        "per-omar-haddad",
        "Records Retention Policy",
        "/firm/policies/records-retention.md",
        "records_retention_policy.md",
    ),
)

# The internal handle the firm uses for a matter in background chatter and time
# narratives, when it differs from the Clio title. The Meridian diligence file
# runs under the deal code name "Project Skylark": the client name stays on the
# Clio matter (title and client org) but never rides the firm's day-to-day
# traffic, which is what makes the S2 fee-dispute support audit turn on the code
# name rather than a client-name grep. Keyed by Clio title.
PROCEDURAL_MATTER_LABELS: dict[str, str] = {
    "Meridian diagnostics acquisition": "Project Skylark",
}

# title, description, client org, actor, requester, assignee, type, priority
_MATTERS: tuple[tuple[str, str, str, str, str, str, str, str], ...] = (
    (
        "Meridian diagnostics acquisition",
        "Buy-side asset acquisition of a diagnostics startup: diligence, "
        "definitive agreements, and closing checklist.",
        "org-000001",
        "per-peter-novak",
        "per-priya-raman",
        "per-marcus-liang",
        "ma-acquisition",
        "high",
    ),
    (
        "Cascadia supplier dispute",
        "Commercial litigation against a fabric supplier over recurring "
        "late deliveries and defect rates.",
        "org-000002",
        "per-grace-adeyemi",
        "per-tom-hollis",
        "per-sofia-ramirez",
        "commercial-litigation",
        "normal",
    ),
    (
        "Veridian rate filing compliance",
        "Regulatory compliance review of the cooperative's member rate "
        "filing and board resolutions.",
        "org-000003",
        "per-peter-novak",
        "per-eleanor-hartwell",
        "per-diane-okonkwo",
        "regulatory-compliance",
        "normal",
    ),
    (
        "Brightline wrongful termination defense",
        "Defense of a wrongful termination claim by a former dispatch "
        "supervisor; position statement due to the agency.",
        "org-000004",
        "per-grace-adeyemi",
        "per-samuel-marsh",
        "per-sofia-ramirez",
        "employment",
        "high",
    ),
    (
        "Solstice asset purchase closing",
        "Post-closing obligations under the Halloran Cellars asset "
        "purchase: holdback administration and license transfers.",
        "org-000005",
        "per-peter-novak",
        "per-eleanor-hartwell",
        "per-marcus-liang",
        "contract-negotiation",
        "normal",
    ),
    (
        "Northgate vendor contract refresh",
        "Refresh of the medical group's vendor contract package against "
        "the current template set.",
        "org-000006",
        "per-peter-novak",
        "per-diane-okonkwo",
        "per-noah-feldstein",
        "contract-negotiation",
        "normal",
    ),
    (
        "Pelican Bay lease renewal",
        "Exercise of the marina's five-year renewal option and negotiation "
        "of updated CAM terms.",
        "org-000007",
        "per-peter-novak",
        "per-diane-okonkwo",
        "per-noah-feldstein",
        "real-estate-lease",
        "normal",
    ),
    (
        "Arroyo mechanics lien action",
        "Prosecution of a mechanics lien and stop notice on the Fruitvale "
        "mixed-use project.",
        "org-000008",
        "per-grace-adeyemi",
        "per-samuel-marsh",
        "per-samuel-marsh",
        "commercial-litigation",
        "normal",
    ),
    (
        "Lumen licensing agreement",
        "Negotiation of an inbound software licensing and support "
        "agreement for the client's platform.",
        "org-000009",
        "per-peter-novak",
        "per-june-akana",
        "per-marcus-liang",
        "ip-licensing",
        "normal",
    ),
    (
        "Goldleaf franchise litigation",
        "Franchise termination dispute headed to federal court; scheduling "
        "and early discovery.",
        "org-000010",
        "per-grace-adeyemi",
        "per-samuel-marsh",
        "per-sofia-ramirez",
        "commercial-litigation",
        "high",
    ),
)


def _doc(name: str) -> str:
    return (
        resources.files("workbench.workplaces.hartwell")
        .joinpath("seed_docs", name)
        .read_text(encoding="utf-8")
    )


class HartwellGenesis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    events: tuple[Event, ...]
    minter: IdMinter


def build_genesis(seed: Seed) -> HartwellGenesis:
    minter = IdMinter()
    body: list[EventPayload] = list(EMPLOYEES)

    for org in ORGS:
        minted = minter.mint("org")
        if minted != org.org_id:
            raise ConfigError(
                f"org ids drifted from declaration order: minted {minted}, "
                f"declared {org.org_id}"
            )
        body.append(org)
    body.extend(EXTERNALS)

    for name, members, topic, purpose in _CHANNELS:
        body.append(
            ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id=minter.mint("cnv"),
                conversation_type="channel",
                name=name,
                members=members,
                topic=topic,
                purpose=purpose,
            )
        )

    for first, second, _ in _DMS:
        body.append(
            ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id=minter.mint("cnv"),
                conversation_type="dm",
                name=None,
                members=(first, second),
            )
        )

    for author, title, path, filename in _DOCUMENTS:
        body.append(
            DocumentCreatedPayload(
                kind="document.created",
                document_id=minter.mint("doc"),
                author=author,
                title=title,
                path=path,
                location="repository",
                content_format="markdown",
                content=_doc(filename),
            )
        )

    for (
        title,
        description,
        client,
        actor,
        requester,
        assignee,
        kind,
        priority,
    ) in _MATTERS:
        body.append(
            TicketCreatedPayload(
                kind="ticket.created",
                ticket_id=minter.mint("tkt"),
                actor=actor,
                title=title,
                description=description,
                requester=requester,
                assignee=assignee,
                status="open",
                priority=priority,
                ticket_type=kind,
                client_ref=client,
            )
        )

    digest = content_hash(
        {
            "workplace_id": WORKPLACE_ID,
            "seed_root": seed.root,
            "payloads": [payload.model_dump(mode="json") for payload in body],
        }
    )
    payloads: list[EventPayload] = [
        SimRunStartedPayload(
            kind="sim.run.started",
            run_id=f"run-{WORKPLACE_ID}-{seed.root}",
            seed_root=seed.root,
            workplace_id=WORKPLACE_ID,
            config_hash=digest,
            schema_version=SCHEMA_VERSION,
            epoch=EPOCH_ISO,
            timezone=TIMEZONE,
        ),
        *body,
    ]
    events = tuple(
        Event(seq=seq, time=0, tag=payload.kind, source="gm", payload=payload)
        for seq, payload in enumerate(payloads)
    )
    return HartwellGenesis(events=events, minter=minter)


def procedural_cast(genesis: HartwellGenesis) -> ProceduralCast:
    """The background-traffic cast, resolved against minted genesis ids."""

    names = {person.person_id: person.name for person in (*EMPLOYEES, *EXTERNALS)}

    def member(person: PersonRecordPayload) -> CastMember:
        return CastMember(person_id=person.person_id, name=person.name)

    conversations = [
        event.payload
        for event in genesis.events
        if isinstance(event.payload, ChatConversationCreatedPayload)
    ]
    channels = {
        payload.name: payload for payload in conversations if payload.name is not None
    }

    def channel(name: str) -> ChatChannel:
        payload = channels[name]
        return ChatChannel(
            conversation_id=payload.conversation_id,
            members=tuple(
                CastMember(person_id=person_id, name=names[person_id])
                for person_id in payload.members
            ),
        )

    traffic = {frozenset((first, second)): rate for first, second, rate in _DMS}
    dms = tuple(
        DmThread(
            conversation_id=payload.conversation_id,
            members=(
                CastMember(
                    person_id=payload.members[0], name=names[payload.members[0]]
                ),
                CastMember(
                    person_id=payload.members[1], name=names[payload.members[1]]
                ),
            ),
            traffic=traffic[frozenset(payload.members)],
        )
        for payload in conversations
        if payload.conversation_type == "dm"
    )

    tickets = [
        event.payload
        for event in genesis.events
        if isinstance(event.payload, TicketCreatedPayload)
        and event.payload.assignee is not None
    ]
    if len(tickets) != len(_STAFFING):
        raise ConfigError(
            f"{len(tickets)} matters but {len(_STAFFING)} staffing rows declared"
        )
    if tuple(person_id for person_id, _, _ in _TIMEKEEPERS) != TIMEKEEPER_IDS:
        raise ConfigError("timekeeper economics drifted from the declared roster")
    matters = tuple(
        OpenMatter(
            ticket_id=payload.ticket_id,
            label=PROCEDURAL_MATTER_LABELS.get(payload.title, payload.title),
            assignee=payload.assignee,
            weight=weight,
            staff=staff,
        )
        for payload, (weight, staff) in zip(tickets, _STAFFING, strict=True)
    )
    return ProceduralCast(
        internal=tuple(member(person) for person in EMPLOYEES),
        timekeepers=tuple(
            Timekeeper(
                member=CastMember(person_id=person_id, name=names[person_id]),
                daily_hours=daily_hours,
                rate_cents=rate_cents,
            )
            for person_id, daily_hours, rate_cents in _TIMEKEEPERS
        ),
        externals=tuple(
            member(person)
            for person in EXTERNALS
            if person.person_id not in DIRECTED_ONLY_EXTERNAL_IDS
        ),
        standup_channel=channel("#general").conversation_id,
        matters_channel=channel("#matters"),
        billing_channel=channel("#billing"),
        it_channel=channel("#it-help"),
        matters=matters,
        dms=dms,
    )
