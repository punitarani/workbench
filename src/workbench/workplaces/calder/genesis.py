"""Genesis for Calder & Finch, CPAs: the world as it stands on Monday
2026-01-05, before the six-month history begins.

Everything is data assembled into time-zero events. Every minted id comes
from one IdMinter; the statically declared org ids are re-minted against
it so the exported counter state is provably truthful. Maya Lindqvist is
deliberately absent: her ``person.record`` arrives mid-window through the
arrival arc, and :func:`procedural_cast` grows to include her only when
the caller passes her DM conversation id.
"""

from collections.abc import Mapping
from importlib import resources

from pydantic import BaseModel, ConfigDict

from workbench.core.artifacts import (
    FormattedDocument,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    SpreadsheetContent,
    SpreadsheetSheet,
    TableBlock,
)
from workbench.core.events import Event, EventPayload
from workbench.core.events.chat import ChatConversationCreatedPayload
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.events.tickets import TicketCreatedPayload
from workbench.core.hashing import content_hash
from workbench.core.ids import IdMinter
from workbench.core.seed import Seed, derive_rng
from workbench.simulation.chronicle.calendar import SECONDS_PER_DAY, CalendarWindow
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
from workbench.workplaces.calder.people import (
    ARRIVAL,
    EMPLOYEES,
    EXTERNALS,
    ORGS,
    TIMEKEEPER_IDS,
)

WORKPLACE_ID = "calder"
TIMEZONE = "America/Los_Angeles"
EPOCH_ISO = "2026-01-05T00:00:00-08:00"
SCHEMA_VERSION = 1

WINDOW = CalendarWindow(
    start_date="2026-01-05", end_date="2026-07-17", timezone=TIMEZONE
)

# The engine-simulated live day: the first Monday after the chronicle
# window. Flat day arithmetic, matching CalendarWindow.day_offset.
LIVE_DAY = "2026-07-20"
LIVE_DAY_INDEX = 196
LIVE_DAY_OFFSET = LIVE_DAY_INDEX * SECONDS_PER_DAY

# Federal holidays inside the window, in observed form, with how much of
# a normal working day the firm still generates. An accounting firm never
# goes fully dark — partners clear mail, someone watches the e-file
# acknowledgments — but holidays outside busy season run quiet.
FEDERAL_HOLIDAYS_2026: tuple[tuple[str, str, float], ...] = (
    ("2026-01-19", "Birthday of Martin Luther King, Jr.", 0.30),
    ("2026-02-16", "Washington's Birthday", 0.40),
    ("2026-05-25", "Memorial Day", 0.10),
    ("2026-06-19", "Juneteenth National Independence Day", 0.30),
    ("2026-07-03", "Independence Day (observed)", 0.12),
)
_HOLIDAY_INTENSITY = {day: intensity for day, _, intensity in FEDERAL_HOLIDAYS_2026}

# Weekend baselines. During filing season (February through April 15) the
# office genuinely works Saturdays; the rest of the year weekends carry
# only stray catch-up. Per-day jitter keeps some weekends silent and
# others busy instead of painting every Saturday the same shade.
_SEASON_START = "2026-02-01"
_SEASON_END = "2026-04-15"
_SEASON_SATURDAY = 0.30
_SEASON_SUNDAY = 0.12
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
    in_season = _SEASON_START <= day <= _SEASON_END
    if weekday == 5:
        base = _SEASON_SATURDAY if in_season else _SATURDAY
    else:
        base = _SEASON_SUNDAY if in_season else _SUNDAY
    jitter = derive_rng(seed, "calder.weekend", day).uniform(0.35, 2.0)
    return DayProfile(kind="weekend", intensity=min(base * jitter, 1.0))


_EVERYONE = tuple(person.person_id for person in EMPLOYEES)
_GENESIS_TIMEKEEPER_IDS = tuple(
    person_id for person_id in TIMEKEEPER_IDS if person_id != ARRIVAL.person_id
)

_CHANNELS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (
        "#firm",
        _EVERYONE,
        "Firm-wide announcements and chatter",
        "Anything that does not belong on a specific engagement.",
    ),
    (
        "#engagements",
        _GENESIS_TIMEKEEPER_IDS,
        "Active engagement coordination",
        "Status, staffing, and deadlines on open engagements.",
    ),
    (
        "#billing",
        (
            "per-rosalind-calder",
            "per-elias-finch",
            "per-hana-sato",
            "per-owen-castile",
            "per-gabriel-fontes",
        ),
        "Billing cycle and collections",
        "Prebills, invoices, retainers, WIP, and fee questions.",
    ),
    (
        "#it-help",
        _EVERYONE,
        "IT and facilities requests",
        "Portal, software, and hardware trouble. Raj triages.",
    ),
)

# Standing DM pairs and each pair's expected exchanges per workday. The
# tax manager's thread with his senior runs hot through filing season;
# the office manager's threads carry the administrative spine of the
# firm. New pairs append at the end so the earlier pairs' seeded draws —
# and their message content — never move.
_DMS: tuple[tuple[str, str, float], ...] = (
    ("per-victor-alade", "per-desmond-ortiz", 1.3),
    ("per-rosalind-calder", "per-victor-alade", 0.8),
    ("per-gabriel-fontes", "per-sylvia-nakamura", 1.1),
    ("per-desmond-ortiz", "per-nadia-osman", 0.9),
    ("per-lucia-mendes", "per-colin-mackey", 0.9),
    ("per-imogen-carraway", "per-theo-brandt", 1.2),
    ("per-theo-brandt", "per-priscilla-wong", 0.7),
    ("per-rosalind-calder", "per-owen-castile", 0.7),
    ("per-owen-castile", "per-gabriel-fontes", 0.8),
    ("per-freya-holt", "per-owen-castile", 0.9),
    ("per-raj-malhotra", "per-owen-castile", 0.5),
    ("per-hana-sato", "per-imogen-carraway", 0.8),
    ("per-elias-finch", "per-gabriel-fontes", 0.9),
    ("per-lucia-mendes", "per-nadia-osman", 0.6),
)

# Maya's standing DM once she arrives; the conversation itself is created
# by the arrival arc, which owns the minted id.
ARRIVAL_DM = ("per-maya-lindqvist", "per-desmond-ortiz", 0.8)

# Fee earners: standard hourly rate in cents and the billable day the
# firm expects of them. Partners carry management load and bill less than
# the staff; the payroll specialist bills the least. These are targets,
# not outcomes — absence, light days, and crunch move the realized figure
# day by day. Maya's row activates only after her arrival.
_TIMEKEEPERS: tuple[tuple[str, float, int], ...] = (
    ("per-rosalind-calder", 4.6, 42_500),
    ("per-elias-finch", 4.9, 39_500),
    ("per-hana-sato", 4.7, 40_500),
    ("per-victor-alade", 6.4, 28_500),
    ("per-imogen-carraway", 6.2, 27_500),
    ("per-desmond-ortiz", 6.9, 21_500),
    ("per-lucia-mendes", 6.8, 20_500),
    ("per-theo-brandt", 6.7, 19_500),
    ("per-nadia-osman", 7.1, 15_500),
    ("per-colin-mackey", 7.0, 14_500),
    ("per-priscilla-wong", 6.9, 14_500),
    ("per-gabriel-fontes", 6.0, 17_500),
    ("per-sylvia-nakamura", 5.4, 12_500),
    ("per-maya-lindqvist", 6.8, 14_500),
)

# The rate every time entry is recorded at, directed or procedural.
TIMEKEEPER_RATES: Mapping[str, int] = {
    person_id: rate for person_id, _, rate in _TIMEKEEPERS
}

# Engagement complexity and staffing, in engagement declaration order.
# Weight is the share of a staffed timekeeper's day the engagement
# competes for: the nonprofit audit accretes several times the hours of
# the bookkeeping cleanup instead of every file coming out the same size.
_STAFFING: tuple[tuple[float, tuple[str, ...]], ...] = (
    (1.6, ("per-gabriel-fontes", "per-nadia-osman", "per-elias-finch")),
    (1.3, ("per-gabriel-fontes", "per-sylvia-nakamura", "per-colin-mackey")),
    (1.4, ("per-gabriel-fontes", "per-colin-mackey", "per-elias-finch")),
    (1.0, ("per-gabriel-fontes", "per-nadia-osman")),
    (
        2.2,
        (
            "per-victor-alade",
            "per-desmond-ortiz",
            "per-nadia-osman",
            "per-rosalind-calder",
        ),
    ),
    (1.8, ("per-lucia-mendes", "per-colin-mackey", "per-rosalind-calder")),
    (
        2.8,
        (
            "per-imogen-carraway",
            "per-theo-brandt",
            "per-priscilla-wong",
            "per-hana-sato",
        ),
    ),
    (1.5, ("per-desmond-ortiz", "per-colin-mackey", "per-victor-alade")),
    (1.2, ("per-lucia-mendes", "per-nadia-osman", "per-rosalind-calder")),
    (0.9, ("per-sylvia-nakamura", "per-gabriel-fontes")),
    (1.1, ("per-victor-alade", "per-desmond-ortiz", "per-elias-finch")),
    (0.6, ("per-colin-mackey", "per-gabriel-fontes")),
)

# Engagements Maya joins when she arrives (indices into _MATTERS): the
# tax returns her group carries through filing season.
_ARRIVAL_STAFF_MATTERS = frozenset({4, 7, 8})

# The internal handle the firm uses for an engagement in background
# chatter and time narratives. Keyed by ticket title.
PROCEDURAL_MATTER_LABELS: dict[str, str] = {
    "Monthly close — Kestrel Manufacturing": "the Kestrel close",
    "Monthly close — Blue Fir Restaurant Group": "the Blue Fir close",
    "Monthly close — Stonebridge Property Group": "the Stonebridge close",
    "Monthly close — Alder Creek Brewing": "the Alder Creek close",
    "Form 1120-S — Kestrel Manufacturing 2025": "the Kestrel 1120-S",
    "Form 1065 — Stonebridge Property Group 2025": "the Stonebridge 1065",
    "Form 990 & audit — Harbor Light Foundation FY2025": "the Harbor Light audit",
    "Form 1120-S — Cardinal Ridge Builders 2025": "the Cardinal Ridge 1120-S",
    "Owner returns — Summit Physical Therapy partners": "the Summit owner returns",
    "Payroll & quarterly filings — Blue Fir Restaurant Group": "the Blue Fir payroll",
    "R&D credit study — Loop & Ladder Software": "the Loop & Ladder credit study",
    "Bookkeeping cleanup — Riverbend Dental Studio": "the Riverbend cleanup",
}

# title, description, client org, actor, requester, assignee, type, priority
_MATTERS: tuple[tuple[str, str, str, str, str, str, str, str], ...] = (
    (
        "Monthly close — Kestrel Manufacturing",
        "Recurring monthly close: bank recs, inventory tie-out, and the "
        "management reporting package.",
        "org-000001",
        "per-elias-finch",
        "per-dana-whitfield",
        "per-gabriel-fontes",
        "monthly-close",
        "normal",
    ),
    (
        "Monthly close — Blue Fir Restaurant Group",
        "Recurring monthly close across four locations: POS tie-out, "
        "tips reconciliation, and vendor accruals.",
        "org-000002",
        "per-elias-finch",
        "per-marco-petrosyan",
        "per-gabriel-fontes",
        "monthly-close",
        "normal",
    ),
    (
        "Monthly close — Stonebridge Property Group",
        "Recurring monthly close: property-level rollups, CAM "
        "reconciliations, and the lender reporting package.",
        "org-000005",
        "per-elias-finch",
        "per-evan-doyle",
        "per-gabriel-fontes",
        "monthly-close",
        "high",
    ),
    (
        "Monthly close — Alder Creek Brewing",
        "Recurring monthly close: keg deposit liability, excise "
        "reporting support, and margin reporting by channel.",
        "org-000009",
        "per-elias-finch",
        "per-reuben-tate",
        "per-gabriel-fontes",
        "monthly-close",
        "normal",
    ),
    (
        "Form 1120-S — Kestrel Manufacturing 2025",
        "S corporation return with multi-state apportionment and the "
        "shareholder basis schedules.",
        "org-000001",
        "per-rosalind-calder",
        "per-dana-whitfield",
        "per-victor-alade",
        "tax-return",
        "high",
    ),
    (
        "Form 1065 — Stonebridge Property Group 2025",
        "Partnership return: twelve properties, special allocations, "
        "and the K-1 packet to fourteen partners.",
        "org-000005",
        "per-rosalind-calder",
        "per-evan-doyle",
        "per-lucia-mendes",
        "tax-return",
        "high",
    ),
    (
        "Form 990 & audit — Harbor Light Foundation FY2025",
        "Financial statement audit and Form 990 for the foundation's "
        "June 30 fiscal year; grant compliance testing included.",
        "org-000004",
        "per-hana-sato",
        "per-naomi-castellanos",
        "per-imogen-carraway",
        "audit",
        "high",
    ),
    (
        "Form 1120-S — Cardinal Ridge Builders 2025",
        "S corporation return with percentage-of-completion revenue and "
        "the equipment depreciation schedules.",
        "org-000006",
        "per-rosalind-calder",
        "per-frank-osei",
        "per-desmond-ortiz",
        "tax-return",
        "normal",
    ),
    (
        "Owner returns — Summit Physical Therapy partners",
        "Individual returns for the practice's three partners, "
        "coordinated with the practice books.",
        "org-000010",
        "per-rosalind-calder",
        "per-gloria-nunez",
        "per-lucia-mendes",
        "tax-return",
        "normal",
    ),
    (
        "Payroll & quarterly filings — Blue Fir Restaurant Group",
        "Payroll processing support and quarterly employment filings "
        "across the group's entities.",
        "org-000002",
        "per-elias-finch",
        "per-marco-petrosyan",
        "per-sylvia-nakamura",
        "payroll",
        "normal",
    ),
    (
        "R&D credit study — Loop & Ladder Software",
        "Research credit study for the platform rebuild: qualifying "
        "activity interviews and the credit computation.",
        "org-000007",
        "per-rosalind-calder",
        "per-sana-qureshi",
        "per-victor-alade",
        "advisory",
        "normal",
    ),
    (
        "Bookkeeping cleanup — Riverbend Dental Studio",
        "Catch-up bookkeeping: eight months of uncategorized activity "
        "and a chart-of-accounts rebuild.",
        "org-000003",
        "per-elias-finch",
        "per-alice-kwon",
        "per-colin-mackey",
        "bookkeeping",
        "low",
    ),
)


def _doc(name: str) -> str:
    return (
        resources.files("workbench.workplaces.calder")
        .joinpath("seed_docs", name)
        .read_text(encoding="utf-8")
    )


def _rate_sheet() -> str:
    names = {person.person_id: person for person in EMPLOYEES}
    rows = tuple(
        (
            names[person_id].name,
            names[person_id].title,
            rate_cents / 100,
        )
        for person_id, _, rate_cents in _TIMEKEEPERS
        if person_id in names
    )
    return SpreadsheetContent(
        sheets=(
            SpreadsheetSheet(
                name="Standard Rates 2026",
                columns=("Timekeeper", "Title", "Standard rate ($/hr)"),
                rows=rows,
            ),
        )
    ).canonical_json()


def _client_master() -> str:
    contact = {person.organization: person for person in EXTERNALS}
    services = {
        "org-000001": "Monthly close; 1120-S",
        "org-000002": "Monthly close; payroll & quarterly filings",
        "org-000003": "Bookkeeping cleanup; 1120-S",
        "org-000004": "Financial statement audit; Form 990",
        "org-000005": "Monthly close; 1065",
        "org-000006": "1120-S; job costing advisory",
        "org-000007": "R&D credit study; 1120",
        "org-000008": "Bookkeeping; sales tax",
        "org-000009": "Monthly close; excise support",
        "org-000010": "Partner 1040s; practice bookkeeping",
    }
    entity = {
        "org-000001": ("S corporation", "12/31"),
        "org-000002": ("S corporation group", "12/31"),
        "org-000003": ("S corporation", "12/31"),
        "org-000004": ("501(c)(3)", "6/30"),
        "org-000005": ("Partnership", "12/31"),
        "org-000006": ("S corporation", "12/31"),
        "org-000007": ("C corporation", "12/31"),
        "org-000008": ("S corporation", "1/31"),
        "org-000009": ("LLC", "12/31"),
        "org-000010": ("Partnership", "12/31"),
    }
    rows = []
    for org in ORGS:
        if org.category != "client":
            continue
        kind, year_end = entity[org.org_id]
        person = contact[org.org_id]
        rows.append(
            (
                org.name,
                kind,
                year_end,
                services[org.org_id],
                person.name,
                person.email_address,
            )
        )
    return SpreadsheetContent(
        sheets=(
            SpreadsheetSheet(
                name="Clients",
                columns=(
                    "Client",
                    "Entity type",
                    "Year end",
                    "Services",
                    "Primary contact",
                    "Contact email",
                ),
                rows=tuple(rows),
            ),
        )
    ).canonical_json()


def _close_checklist() -> str:
    return FormattedDocument(
        blocks=(
            HeadingBlock(kind="heading", level=1, text="Monthly Close Checklist"),
            ParagraphBlock(
                kind="paragraph",
                text=(
                    "Standard sequence for every monthly-close client. Steps "
                    "run in order; a step that cannot complete gets a note in "
                    "the engagement folder, never a silent skip."
                ),
            ),
            ListBlock(
                kind="list",
                ordered=True,
                items=(
                    "Reconcile every bank and credit card account",
                    "Tie revenue to the source system (POS, invoicing, rent roll)",
                    "Review AR and AP agings; clear stale items",
                    "Book payroll accruals and benefit allocations",
                    "Roll prepaids and update the fixed-asset register",
                    "Post recurring and adjusting journal entries",
                    "Run analytics against prior month and budget",
                    "Assemble the reporting package for partner review",
                ),
            ),
            TableBlock(
                kind="table",
                columns=("Step", "Owner", "Target"),
                rows=(
                    ("Bank reconciliations", "Staff", "Business day 3"),
                    ("Revenue tie-out", "Staff", "Business day 4"),
                    ("Accruals and prepaids", "Senior", "Business day 5"),
                    ("Analytics and package", "Lead", "Business day 7"),
                    ("Partner review", "Partner", "Business day 8"),
                ),
            ),
            ParagraphBlock(
                kind="paragraph",
                text=(
                    "The client does not see the package until partner review "
                    "clears. Late support moves the calendar; it never "
                    "compresses the review."
                ),
            ),
        )
    ).canonical_json()


# author, title, path, content_format, content thunk
_DOCUMENTS: tuple[tuple[str, str, str, str, object], ...] = (
    (
        "per-rosalind-calder",
        "Engagement Letter (Standard Form)",
        "/firm/templates/engagement-letter.md",
        "markdown",
        lambda: _doc("engagement_letter_template.md"),
    ),
    (
        "per-owen-castile",
        "Time & Billing Policy",
        "/firm/policies/time-billing-policy.md",
        "markdown",
        lambda: _doc("time_billing_policy.md"),
    ),
    (
        "per-victor-alade",
        "Tax Return Workflow & Review Policy",
        "/firm/playbooks/tax-return-workflow.md",
        "markdown",
        lambda: _doc("tax_return_workflow.md"),
    ),
    (
        "per-desmond-ortiz",
        "PBC Request Template",
        "/firm/templates/pbc-request.md",
        "markdown",
        lambda: _doc("pbc_request_template.md"),
    ),
    (
        "per-raj-malhotra",
        "Records Retention & Security Policy",
        "/firm/policies/records-retention.md",
        "markdown",
        lambda: _doc("records_retention_policy.md"),
    ),
    (
        "per-owen-castile",
        "Standard Rate Sheet 2026",
        "/firm/billing/rate-sheet-2026.xlsx",
        "spreadsheet",
        _rate_sheet,
    ),
    (
        "per-freya-holt",
        "Client Master List",
        "/firm/admin/client-master.xlsx",
        "spreadsheet",
        _client_master,
    ),
    (
        "per-gabriel-fontes",
        "Monthly Close Checklist",
        "/firm/playbooks/monthly-close-checklist.docx",
        "formatted",
        _close_checklist,
    ),
)


class CalderGenesis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    events: tuple[Event, ...]
    minter: IdMinter


def build_genesis(seed: Seed) -> CalderGenesis:
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

    for author, title, path, content_format, content in _DOCUMENTS:
        body.append(
            DocumentCreatedPayload(
                kind="document.created",
                document_id=minter.mint("doc"),
                author=author,
                title=title,
                path=path,
                location="repository",
                content_format=content_format,
                content=content(),
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
    return CalderGenesis(events=events, minter=minter)


def _staff_for(index: int, *, with_arrival: bool) -> tuple[str, ...]:
    weight, staff = _STAFFING[index]
    del weight
    if with_arrival and index in _ARRIVAL_STAFF_MATTERS:
        return (*staff, ARRIVAL.person_id)
    return staff


def procedural_cast(
    genesis: CalderGenesis, *, arrival_dm_id: str | None = None
) -> ProceduralCast:
    """The background-traffic cast, resolved against minted genesis ids.

    With ``arrival_dm_id`` unset this is the firm as of day zero: no
    Maya. Passing the DM conversation id the arrival arc minted grows
    the cast to include her — as a channel-silent member, because the
    genesis channels' membership is fixed at creation and no member-add
    event exists in the world model.
    """

    people = (*EMPLOYEES, ARRIVAL, *EXTERNALS)
    names = {person.person_id: person.name for person in people}
    with_arrival = arrival_dm_id is not None

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
    dms = [
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
    ]
    if with_arrival:
        first, second, rate = ARRIVAL_DM
        dms.append(
            DmThread(
                conversation_id=arrival_dm_id,
                members=(
                    CastMember(person_id=first, name=names[first]),
                    CastMember(person_id=second, name=names[second]),
                ),
                traffic=rate,
            )
        )

    tickets = [
        event.payload
        for event in genesis.events
        if isinstance(event.payload, TicketCreatedPayload)
        and event.payload.assignee is not None
    ]
    if len(tickets) != len(_STAFFING):
        raise ConfigError(
            f"{len(tickets)} engagements but {len(_STAFFING)} staffing rows declared"
        )
    if tuple(person_id for person_id, _, _ in _TIMEKEEPERS) != TIMEKEEPER_IDS:
        raise ConfigError("timekeeper economics drifted from the declared roster")
    matters = tuple(
        OpenMatter(
            ticket_id=payload.ticket_id,
            label=PROCEDURAL_MATTER_LABELS[payload.title],
            assignee=payload.assignee,
            weight=weight,
            staff=_staff_for(index, with_arrival=with_arrival),
        )
        for index, (payload, (weight, _)) in enumerate(
            zip(tickets, _STAFFING, strict=True)
        )
    )
    active_ids = set(_EVERYONE) | ({ARRIVAL.person_id} if with_arrival else set())
    return ProceduralCast(
        internal=tuple(member(person) for person in EMPLOYEES),
        channel_silent=(member(ARRIVAL),) if with_arrival else (),
        timekeepers=tuple(
            Timekeeper(
                member=CastMember(person_id=person_id, name=names[person_id]),
                daily_hours=daily_hours,
                rate_cents=rate_cents,
            )
            for person_id, daily_hours, rate_cents in _TIMEKEEPERS
            if person_id in active_ids
        ),
        externals=tuple(member(person) for person in EXTERNALS),
        standup_channel=channel("#firm").conversation_id,
        matters_channel=channel("#engagements"),
        billing_channel=channel("#billing"),
        it_channel=channel("#it-help"),
        matters=matters,
        dms=tuple(dms),
    )
