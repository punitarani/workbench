"""Directed arcs for the Calder & Finch six-month history.

Five deterministic storylines ride on top of the procedural fabric: the
monthly close cycle, filing season with its April 15 crunch, quarterly
estimate reminders, Maya's arrival, and the Harbor Light audit. All
prose is template-authored — no LM anywhere — and every random choice
draws from ``derive_rng(seed, "calder.arcs", day)``, so a rebuild is
byte-identical and extending the window never rewrites history.

The director is stateful across days (cross-day email threads reference
message ids minted earlier), so ``drafts_for`` must be called once per
day in ascending order — exactly how the build driver walks the window.
"""

import random
from datetime import date, timedelta

from workbench.core.artifacts import (
    FormattedDocument,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    SpreadsheetContent,
    SpreadsheetSheet,
    TableBlock,
)
from workbench.core.events.calendar import CalendarEventScheduledPayload
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
    ChatReactionAddedPayload,
)
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import Attachment, EmailMessagePayload
from workbench.core.events.tickets import (
    FieldChange,
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.ids import IdMinter
from workbench.core.seed import Seed, derive_rng
from workbench.core.simtime import SimDuration, SimTime
from workbench.simulation.chronicle.builder import TimedDraft
from workbench.simulation.chronicle.calendar import SECONDS_PER_DAY
from workbench.workplaces.calder.genesis import (
    FEDERAL_HOLIDAYS_2026,
    TIMEKEEPER_RATES,
    WINDOW,
    CalderGenesis,
)
from workbench.workplaces.calder.people import ARRIVAL, ARRIVAL_DATE

# The window's own holiday table plus New Year's Day, which precedes the
# window but still shapes "Nth business day of January" arithmetic.
_HOLIDAYS = {day for day, _, _ in FEDERAL_HOLIDAYS_2026} | {"2026-01-01"}

_MD = "text/markdown"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _t(hour: int, minute: int = 0) -> int:
    return hour * 3600 + minute * 60


def _is_workday(day: date) -> bool:
    return day.weekday() < 5 and day.isoformat() not in _HOLIDAYS


def _next_workday(day: date) -> date:
    while not _is_workday(day):
        day += timedelta(days=1)
    return day


def _workday_of_month(year: int, month: int, ordinal: int) -> date:
    """The Nth working day of a month (1-based)."""

    day = date(year, month, 1)
    count = 0
    while True:
        if _is_workday(day):
            count += 1
            if count == ordinal:
                return day
        day += timedelta(days=1)


def _entity(person_id: str) -> str:
    return person_id.partition("-")[2]


# Close cycle: (client org, engagement title, contact person, slug,
# monthly revenue base in dollars).
_CLOSE_CLIENTS: tuple[tuple[str, str, str, str, int], ...] = (
    (
        "org-000001",
        "Monthly close — Kestrel Manufacturing",
        "per-dana-whitfield",
        "kestrel",
        1_820_000,
    ),
    (
        "org-000002",
        "Monthly close — Blue Fir Restaurant Group",
        "per-marco-petrosyan",
        "blue-fir",
        940_000,
    ),
    (
        "org-000005",
        "Monthly close — Stonebridge Property Group",
        "per-evan-doyle",
        "stonebridge",
        1_260_000,
    ),
    (
        "org-000009",
        "Monthly close — Alder Creek Brewing",
        "per-reuben-tate",
        "alder-creek",
        430_000,
    ),
)

# The months each close cycle reports on: December 2025 through June
# 2026, closed in the following month.
_CLOSE_CYCLES: tuple[tuple[int, int], ...] = (
    (2025, 12),
    (2026, 1),
    (2026, 2),
    (2026, 3),
    (2026, 4),
    (2026, 5),
    (2026, 6),
)

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

# Filing season: (engagement title, client name, contact, preparer,
# return label, extended?).
_TAX_CLIENTS: tuple[tuple[str, str, str, str, str, bool], ...] = (
    (
        "Form 1120-S — Kestrel Manufacturing 2025",
        "Kestrel Manufacturing",
        "per-dana-whitfield",
        "per-victor-alade",
        "Form 1120-S",
        False,
    ),
    (
        "Form 1065 — Stonebridge Property Group 2025",
        "Stonebridge Property Group",
        "per-evan-doyle",
        "per-lucia-mendes",
        "Form 1065",
        False,
    ),
    (
        "Form 1120-S — Cardinal Ridge Builders 2025",
        "Cardinal Ridge Builders",
        "per-frank-osei",
        "per-desmond-ortiz",
        "Form 1120-S",
        True,
    ),
    (
        "Owner returns — Summit Physical Therapy partners",
        "Summit Physical Therapy",
        "per-gloria-nunez",
        "per-lucia-mendes",
        "the partner returns",
        True,
    ),
)

_SEASON_START = date(2026, 3, 1)
_DEADLINE = date(2026, 4, 15)

# Who carries season overtime and against which engagement.
_SEASON_STAFF: tuple[tuple[str, str], ...] = (
    ("per-victor-alade", "Form 1120-S — Kestrel Manufacturing 2025"),
    ("per-desmond-ortiz", "Form 1120-S — Cardinal Ridge Builders 2025"),
    ("per-lucia-mendes", "Form 1065 — Stonebridge Property Group 2025"),
    ("per-nadia-osman", "Form 1120-S — Kestrel Manufacturing 2025"),
    ("per-colin-mackey", "Form 1065 — Stonebridge Property Group 2025"),
    ("per-rosalind-calder", "Form 1120-S — Kestrel Manufacturing 2025"),
    ("per-maya-lindqvist", "Form 1120-S — Kestrel Manufacturing 2025"),
)

_SEASON_NOTES: tuple[str, ...] = (
    "Prepare federal and state returns; clear diagnostics — {label}",
    "Review workpapers against source documents — {label}",
    "Shareholder/partner allocation schedules — {label}",
    "Depreciation reconciliation and book-tax differences — {label}",
    "State apportionment workpaper — {label}",
    "Assemble e-file packet and review diagnostics — {label}",
    "Respond to review notes — {label}",
)

# Quarterly estimates: (due-date, reminder-anchor, clients).
_ESTIMATE_ROUNDS: tuple[tuple[str, date, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "fourth-quarter",
        date(2026, 1, 8),
        (
            ("per-sana-qureshi", "Loop & Ladder Software", "per-victor-alade"),
            ("per-frank-osei", "Cardinal Ridge Builders", "per-desmond-ortiz"),
            ("per-gloria-nunez", "Summit Physical Therapy", "per-lucia-mendes"),
        ),
    ),
    (
        "first-quarter",
        date(2026, 4, 6),
        (
            ("per-sana-qureshi", "Loop & Ladder Software", "per-victor-alade"),
            ("per-frank-osei", "Cardinal Ridge Builders", "per-desmond-ortiz"),
        ),
    ),
    (
        "second-quarter",
        date(2026, 6, 8),
        (
            ("per-sana-qureshi", "Loop & Ladder Software", "per-victor-alade"),
            ("per-frank-osei", "Cardinal Ridge Builders", "per-desmond-ortiz"),
            ("per-gloria-nunez", "Summit Physical Therapy", "per-lucia-mendes"),
        ),
    ),
)

_AUDIT_TICKET = "Form 990 & audit — Harbor Light Foundation FY2025"
_AUDIT_TEAM = (
    "per-imogen-carraway",
    "per-theo-brandt",
    "per-priscilla-wong",
    "per-hana-sato",
)

PBC_LIST_TITLE = "PBC List — Harbor Light Foundation FY2025 Audit"
DRAFT_FS_TITLE = "Draft Financial Statements — Harbor Light Foundation FY2025"
WELCOME_SUBJECT = "Welcome to Calder & Finch, Maya"


class CalderDirector:
    """Generates the directed drafts for one day at a time, in order."""

    def __init__(self, genesis: CalderGenesis, seed: Seed, minter: IdMinter) -> None:
        self._seed = seed
        self._names = {
            event.payload.person_id: event.payload.name
            for event in genesis.events
            if event.payload.kind == "person.record"
        }
        self._names[ARRIVAL.person_id] = ARRIVAL.name
        self._tickets = {
            event.payload.title: event.payload.ticket_id
            for event in genesis.events
            if isinstance(event.payload, TicketCreatedPayload)
        }
        channels = {
            event.payload.name: event.payload.conversation_id
            for event in genesis.events
            if isinstance(event.payload, ChatConversationCreatedPayload)
            and event.payload.name is not None
        }
        self._firm = channels["#firm"]
        self._engagements = channels["#engagements"]
        documents = {
            event.payload.title: event.payload.document_id
            for event in genesis.events
            if isinstance(event.payload, DocumentCreatedPayload)
        }
        self._engagement_letter_doc = documents["Engagement Letter (Standard Form)"]

        # Ids the director owns, minted up front in a fixed order.
        self.arrival_dm_id = minter.mint("cnv")
        self._pbc_doc_id = minter.mint("doc")
        self._pbc_revision = 1

        # Cross-day email threads: key -> (thread_id, message_id).
        self._threads: dict[str, tuple[str, str]] = {}

    # -- draft helpers ----------------------------------------------------

    def _email(
        self,
        drafts: list[TimedDraft],
        minter: IdMinter,
        *,
        at: int,
        sender: str,
        to: tuple[str, ...],
        subject: str,
        body: str,
        cc: tuple[str, ...] = (),
        thread_key: str | None = None,
        reply_key: str | None = None,
        attachments: tuple[Attachment, ...] = (),
    ) -> None:
        message_id = minter.mint("msg")
        in_reply_to: str | None = None
        if reply_key is not None:
            thread_id, in_reply_to = self._threads[reply_key]
        else:
            thread_id = minter.mint("thr")
        if thread_key is not None:
            self._threads[thread_key] = (thread_id, message_id)
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(sender),
                payload=EmailMessagePayload(
                    kind="email.message",
                    message_id=message_id,
                    thread_id=thread_id,
                    in_reply_to=in_reply_to,
                    sender=sender,
                    to=to,
                    cc=cc,
                    subject=subject,
                    body=body,
                    attachments=attachments,
                ),
            )
        )

    def _chat(
        self,
        drafts: list[TimedDraft],
        minter: IdMinter,
        *,
        at: int,
        conversation: str,
        sender: str,
        body: str,
        reply_to: str | None = None,
    ) -> str:
        message_id = minter.mint("chm")
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(sender),
                payload=ChatMessagePayload(
                    kind="chat.message",
                    chat_message_id=message_id,
                    conversation_id=conversation,
                    reply_to=reply_to,
                    sender=sender,
                    body=body,
                ),
            )
        )
        return message_id

    def _comment(
        self,
        drafts: list[TimedDraft],
        *,
        at: int,
        ticket: str,
        actor: str,
        body: str,
    ) -> None:
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(actor),
                payload=TicketCommentedPayload(
                    kind="ticket.commented",
                    ticket_id=self._tickets[ticket],
                    actor=actor,
                    body=body,
                ),
            )
        )

    def _status(
        self,
        drafts: list[TimedDraft],
        *,
        at: int,
        ticket: str,
        actor: str,
        old: str,
        new: str,
    ) -> None:
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=_entity(actor),
                payload=TicketUpdatedPayload(
                    kind="ticket.updated",
                    ticket_id=self._tickets[ticket],
                    actor=actor,
                    changes=(FieldChange(field="status", old=old, new=new),),
                ),
            )
        )

    # -- month-end closes -------------------------------------------------

    def _package_content(self, org: str, year: int, month: int, base: int) -> str:
        rng = derive_rng(self._seed, "calder.close.package", org, f"{year}-{month:02d}")
        revenue = int(base * rng.uniform(0.86, 1.16))
        cogs = int(revenue * rng.uniform(0.52, 0.64))
        gross = revenue - cogs
        opex = int(revenue * rng.uniform(0.21, 0.29))
        ebitda = gross - opex
        depreciation = int(base * rng.uniform(0.015, 0.028))
        net = ebitda - depreciation
        cash = int(base * rng.uniform(0.55, 1.4))
        return SpreadsheetContent(
            sheets=(
                SpreadsheetSheet(
                    name="Summary",
                    columns=("Line", "Amount ($)"),
                    rows=(
                        ("Revenue", revenue),
                        ("Cost of sales", cogs),
                        ("Gross profit", gross),
                        ("Operating expenses", opex),
                        ("EBITDA", ebitda),
                        ("Depreciation", depreciation),
                        ("Net income", net),
                        ("Ending cash", cash),
                    ),
                ),
            )
        ).canonical_json()

    def _closes(
        self,
        day: date,
        rng: random.Random,
        minter: IdMinter,
        drafts: list[TimedDraft],
    ) -> None:
        for year, month in _CLOSE_CYCLES:
            month_name = f"{_MONTH_NAMES[month - 1]} {year}"
            close_year, close_month = (year, month + 1) if month < 12 else (year + 1, 1)

            request_day = _next_workday(date(year, month, 25))
            work_day = _workday_of_month(close_year, close_month, 3)
            package_day = _workday_of_month(close_year, close_month, 6)

            for org, ticket, contact, slug, base in _CLOSE_CLIENTS:
                key = f"close:{slug}:{year}-{month:02d}"
                if day == request_day and day >= date.fromisoformat(WINDOW.start_date):
                    self._email(
                        drafts,
                        minter,
                        at=_t(9, 40) + rng.randrange(0, 5400),
                        sender="per-gabriel-fontes",
                        to=(contact,),
                        subject=f"{month_name} close — documents needed",
                        body=(
                            f"Hi {self._names[contact].split()[0]},\n\nWe're "
                            f"queuing up the {month_name} close. Please upload "
                            "the month's bank and credit card statements and "
                            "the usual source reports to the portal when the "
                            "statements cut. Anything unusual this month, a "
                            "quick note saves us both a follow-up.\n\nThanks,\n"
                            "Gabriel Fontes\nCalder & Finch, CPAs"
                        ),
                        thread_key=key,
                    )
                if day == _next_workday(request_day + timedelta(days=2)):
                    if key in self._threads and rng.random() < 0.8:
                        self._email(
                            drafts,
                            minter,
                            at=_t(10, 10) + rng.randrange(0, 14400),
                            sender=contact,
                            to=("per-gabriel-fontes",),
                            subject=f"Re: {month_name} close — documents needed",
                            body=(
                                "Hi Gabriel,\n\nStatements are uploaded. "
                                "Flagged one odd deposit for you to look at "
                                "when you get there.\n\nThanks,\n"
                                f"{self._names[contact].split()[0]}"
                            ),
                            reply_key=key,
                        )
                if day == work_day:
                    label = ticket.replace("Monthly close — ", "")
                    message = self._chat(
                        drafts,
                        minter,
                        at=_t(9, 20) + rng.randrange(0, 3600),
                        conversation=self._engagements,
                        sender="per-gabriel-fontes",
                        body=(
                            f"{label} close for {month_name}: recs in "
                            "progress, support mostly in. Package targeted "
                            "for business day six."
                        ),
                    )
                    if rng.random() < 0.6:
                        progress = rng.choice(
                            (
                                f"Bank recs done on {label}; "
                                f"{rng.randrange(1, 4)} stale checks noted.",
                                f"Revenue tie-out on {label} matches the "
                                "source system to the dollar.",
                                f"{label}: one unreconciled deposit left, "
                                "client asked about it this morning.",
                                f"Accruals posted for {label}; prepaids "
                                "rolling forward now.",
                                f"AP cutoff on {label} was clean this month for once.",
                            )
                        )
                        self._chat(
                            drafts,
                            minter,
                            at=_t(10, 30) + rng.randrange(0, 3600),
                            conversation=self._engagements,
                            sender=rng.choice(("per-nadia-osman", "per-colin-mackey")),
                            body=progress,
                            reply_to=message,
                        )
                    self._comment(
                        drafts,
                        at=_t(15, 0) + rng.randrange(0, 5400),
                        ticket=ticket,
                        actor="per-gabriel-fontes",
                        body=(
                            f"{month_name} close underway; support received "
                            "and reconciliations in progress."
                        ),
                    )
                if day == package_day:
                    document_id = minter.mint("doc")
                    drafts.append(
                        TimedDraft(
                            at=SimDuration(_t(11, 0) + rng.randrange(0, 1800)),
                            source=_entity("per-gabriel-fontes"),
                            payload=DocumentCreatedPayload(
                                kind="document.created",
                                document_id=document_id,
                                author="per-gabriel-fontes",
                                title=(
                                    f"Reporting Package — "
                                    f"{ticket.replace('Monthly close — ', '')} "
                                    f"{month_name}"
                                ),
                                path=(
                                    f"/clients/{slug}/closes/"
                                    f"{year}-{month:02d}-reporting-package.xlsx"
                                ),
                                location="repository",
                                content_format="spreadsheet",
                                content=self._package_content(org, year, month, base),
                            ),
                        )
                    )
                    self._email(
                        drafts,
                        minter,
                        at=_t(14, 30) + rng.randrange(0, 5400),
                        sender="per-elias-finch",
                        to=(contact,),
                        cc=("per-gabriel-fontes",),
                        subject=f"{month_name} reporting package",
                        body=(
                            f"Hi {self._names[contact].split()[0]},\n\nThe "
                            f"{month_name} close is complete — reporting "
                            "package attached. Margins and cash are in line "
                            "with what we discussed; happy to walk through "
                            "anything on our next call.\n\nBest,\nElias "
                            "Finch\nCalder & Finch, CPAs"
                        ),
                        attachments=(
                            Attachment(
                                filename=(f"{year}-{month:02d}-reporting-package.xlsx"),
                                media_type=_XLSX,
                                document_id=document_id,
                            ),
                        ),
                    )

    # -- filing season ----------------------------------------------------

    def _tax_season(
        self,
        day: date,
        rng: random.Random,
        minter: IdMinter,
        drafts: list[TimedDraft],
    ) -> None:
        for index, (ticket, client, contact, preparer, label, extended) in enumerate(
            _TAX_CLIENTS
        ):
            first = self._names[contact].split()[0]
            letter_day = date(2026, 1, 12) + timedelta(days=index)
            pbc_day = date(2026, 1, 20) + timedelta(days=index)
            partial_day = _next_workday(date(2026, 2, 2) + timedelta(days=index))
            chase_day = _next_workday(date(2026, 2, 17) + timedelta(days=index))
            final_day = _next_workday(date(2026, 3, 2) + timedelta(days=index))
            key = f"pbc:{ticket}"

            if day == letter_day:
                self._email(
                    drafts,
                    minter,
                    at=_t(9, 30) + rng.randrange(0, 3600),
                    sender=preparer,
                    to=(contact,),
                    cc=("per-rosalind-calder",),
                    subject=f"{client} — 2025 engagement letter",
                    body=(
                        f"Hi {first},\n\nAttached is the engagement letter "
                        f"for the 2025 {label}. Please sign and return "
                        "through the portal and we'll get the file rolling."
                        "\n\nBest,\n"
                        f"{self._names[preparer]}\nCalder & Finch, CPAs"
                    ),
                    attachments=(
                        Attachment(
                            filename="engagement-letter.md",
                            media_type=_MD,
                            document_id=self._engagement_letter_doc,
                        ),
                    ),
                )
            if day == pbc_day:
                self._email(
                    drafts,
                    minter,
                    at=_t(10, 0) + rng.randrange(0, 3600),
                    sender=preparer,
                    to=(contact,),
                    subject=f"{client} — documents for the 2025 {label}",
                    body=(
                        f"Hi {first},\n\nTo start the 2025 {label} we need "
                        "the items on the attached list — year-end "
                        "statements, payroll reports, and anything new "
                        "signed during the year. The portal link is the "
                        "same as always.\n\nThanks,\n"
                        f"{self._names[preparer]}\nCalder & Finch, CPAs"
                    ),
                    thread_key=key,
                )
            if day == partial_day:
                self._email(
                    drafts,
                    minter,
                    at=_t(11, 0) + rng.randrange(0, 10800),
                    sender=contact,
                    to=(preparer,),
                    subject=f"Re: {client} — documents for the 2025 {label}",
                    body=(
                        f"Hi {self._names[preparer].split()[0]},\n\nUploaded "
                        "most of the list. Still hunting for the year-end "
                        "loan statement and one insurance letter — should "
                        f"have them shortly.\n\n{first}"
                    ),
                    reply_key=key,
                    thread_key=key,
                )
            if day == chase_day:
                self._email(
                    drafts,
                    minter,
                    at=_t(9, 15) + rng.randrange(0, 3600),
                    sender=preparer,
                    to=(contact,),
                    subject=f"Re: {client} — documents for the 2025 {label}",
                    body=(
                        f"Hi {first},\n\nGentle nudge on the remaining "
                        "items — we're at the point in the file where they "
                        "block progress. A photo or scan is fine.\n\nThanks,"
                        f"\n{self._names[preparer]}"
                    ),
                    reply_key=key,
                    thread_key=key,
                )
            if day == final_day:
                self._email(
                    drafts,
                    minter,
                    at=_t(13, 0) + rng.randrange(0, 10800),
                    sender=contact,
                    to=(preparer,),
                    subject=f"Re: {client} — documents for the 2025 {label}",
                    body=(
                        f"Hi {self._names[preparer].split()[0]},\n\nFound "
                        "everything — it's all in the portal now. Fingers "
                        f"crossed for a quiet filing.\n\n{first}"
                    ),
                    reply_key=key,
                )
                self._comment(
                    drafts,
                    at=_t(16, 0) + rng.randrange(0, 3600),
                    ticket=ticket,
                    actor=preparer,
                    body="All PBC items received; preparation can finish.",
                )
            if day == _DEADLINE and extended:
                self._email(
                    drafts,
                    minter,
                    at=_t(10, 30) + rng.randrange(0, 3600),
                    sender=preparer,
                    to=(contact,),
                    cc=("per-rosalind-calder",),
                    subject=f"{client} — extension filed",
                    body=(
                        f"Hi {first},\n\nAs discussed, we filed the "
                        "extension today with a payment based on the "
                        "estimate in your file. The return itself is on "
                        "our summer schedule; nothing further is needed "
                        "from you right now.\n\nBest,\n"
                        f"{self._names[preparer]}"
                    ),
                )
                self._comment(
                    drafts,
                    at=_t(11, 30) + rng.randrange(0, 1800),
                    ticket=ticket,
                    actor=preparer,
                    body="Extension e-filed with payment; acceptance received.",
                )
            if day == _DEADLINE and not extended:
                self._comment(
                    drafts,
                    at=_t(12, 0) + rng.randrange(0, 7200),
                    ticket=ticket,
                    actor=preparer,
                    body="Return e-filed; federal and state acceptances received.",
                )

        # Season overtime: directed entries on top of the procedural
        # baseline, heaviest in deadline week.
        if _SEASON_START <= day <= _DEADLINE and _is_workday(day):
            deadline_week = day >= _DEADLINE - timedelta(days=7)
            for person, ticket in _SEASON_STAFF:
                if person == ARRIVAL.person_id and day.isoformat() <= ARRIVAL_DATE:
                    continue
                chance = 0.95 if deadline_week else 0.8
                if rng.random() >= chance:
                    continue
                if deadline_week:
                    entries = 3 if rng.random() < 0.4 else 2
                else:
                    entries = 2 if rng.random() < 0.45 else 1
                label = ticket.split(" — ")[0]
                for _ in range(entries):
                    note = rng.choice(_SEASON_NOTES).format(label=label)
                    drafts.append(
                        TimedDraft(
                            at=SimDuration(_t(17, 30) + rng.randrange(0, 14400)),
                            source=_entity(person),
                            payload=TimeLoggedPayload(
                                kind="work.time.logged",
                                person_id=person,
                                ticket_id=self._tickets[ticket],
                                minutes=rng.choice((45, 60, 75, 90, 105, 120)),
                                note=note,
                                rate_cents=TIMEKEEPER_RATES[person],
                                billable=True,
                            ),
                        )
                    )

        if day == _DEADLINE:
            morning = self._chat(
                drafts,
                minter,
                at=_t(8, 45),
                conversation=self._firm,
                sender="per-victor-alade",
                body=(
                    "Filing day. The extension list is final as of last "
                    "night — nothing goes out today without a second set "
                    "of eyes on the payment amount."
                ),
            )
            for reactor in ("per-desmond-ortiz", "per-nadia-osman"):
                drafts.append(
                    TimedDraft(
                        at=SimDuration(_t(8, 50) + rng.randrange(0, 1200)),
                        source=_entity(reactor),
                        payload=ChatReactionAddedPayload(
                            kind="chat.reaction.added",
                            conversation_id=self._firm,
                            chat_message_id=morning,
                            person_id=reactor,
                            emoji="💪",
                        ),
                    )
                )
            evening = self._chat(
                drafts,
                minter,
                at=_t(18, 40),
                conversation=self._firm,
                sender="per-rosalind-calder",
                body=(
                    "E-file queue is clear and every acceptance is in. "
                    "Thank you all — that was a clean season. Breakfast on "
                    "the firm tomorrow."
                ),
            )
            for reactor in (
                "per-victor-alade",
                "per-lucia-mendes",
                "per-colin-mackey",
                "per-freya-holt",
            ):
                drafts.append(
                    TimedDraft(
                        at=SimDuration(_t(18, 42) + rng.randrange(0, 2400)),
                        source=_entity(reactor),
                        payload=ChatReactionAddedPayload(
                            kind="chat.reaction.added",
                            conversation_id=self._firm,
                            chat_message_id=evening,
                            person_id=reactor,
                            emoji=rng.choice(("🎉", "🙌", "🥞")),
                        ),
                    )
                )

    # -- quarterly estimates ----------------------------------------------

    def _estimates(
        self,
        day: date,
        rng: random.Random,
        minter: IdMinter,
        drafts: list[TimedDraft],
    ) -> None:
        for quarter, anchor, clients in _ESTIMATE_ROUNDS:
            for offset, (contact, client, sender) in enumerate(clients):
                reminder_day = _next_workday(anchor + timedelta(days=offset))
                if day != reminder_day:
                    continue
                first = self._names[contact].split()[0]
                self._email(
                    drafts,
                    minter,
                    at=_t(9, 45) + rng.randrange(0, 7200),
                    sender=sender,
                    to=(contact,),
                    subject=f"{client} — {quarter} estimated payment reminder",
                    body=(
                        f"Hi {first},\n\nReminder that the {quarter} "
                        "estimated payment is coming due. The voucher and "
                        "amount are in your portal folder — pay online or "
                        "by check, whichever is easier, and send us the "
                        "confirmation for the file.\n\nBest,\n"
                        f"{self._names[sender]}\nCalder & Finch, CPAs"
                    ),
                )

    # -- the arrival -------------------------------------------------------

    def _arrival(
        self,
        day: date,
        rng: random.Random,
        minter: IdMinter,
        drafts: list[TimedDraft],
    ) -> None:
        if day != date.fromisoformat(ARRIVAL_DATE):
            return
        drafts.append(
            TimedDraft(
                at=SimDuration(_t(8, 30)),
                source="gm",
                payload=ARRIVAL,
            )
        )
        drafts.append(
            TimedDraft(
                at=SimDuration(_t(9, 0)),
                source="gm",
                payload=ChatConversationCreatedPayload(
                    kind="chat.conversation.created",
                    conversation_id=self.arrival_dm_id,
                    conversation_type="dm",
                    name=None,
                    members=(ARRIVAL.person_id, "per-desmond-ortiz"),
                ),
            )
        )
        self._email(
            drafts,
            minter,
            at=_t(9, 5),
            sender="per-victor-alade",
            to=(ARRIVAL.person_id,),
            cc=("per-rosalind-calder",),
            subject=WELCOME_SUBJECT,
            body=(
                "Maya,\n\nWelcome aboard. You're sitting with the tax "
                "group; Desmond will be your first stop for questions and "
                "the two of you share a DM already. This week is systems, "
                "the workflow playbook, and shadowing on the Kestrel file "
                "— billable work starts once you're comfortable.\n\n"
                "Glad you're here,\nVictor"
            ),
        )
        welcome = self._chat(
            drafts,
            minter,
            at=_t(9, 30),
            conversation=self._firm,
            sender="per-victor-alade",
            body=(
                "Everyone say hi to Maya Lindqvist, who joins the tax "
                "group today as a staff accountant. Be nice — it's her "
                "first busy season with us."
            ),
        )
        for reactor in (
            "per-rosalind-calder",
            "per-freya-holt",
            "per-nadia-osman",
            "per-gabriel-fontes",
        ):
            drafts.append(
                TimedDraft(
                    at=SimDuration(_t(9, 32) + rng.randrange(0, 3000)),
                    source=_entity(reactor),
                    payload=ChatReactionAddedPayload(
                        kind="chat.reaction.added",
                        conversation_id=self._firm,
                        chat_message_id=welcome,
                        person_id=reactor,
                        emoji=rng.choice(("👋", "🎉")),
                    ),
                )
            )
        self._chat(
            drafts,
            minter,
            at=_t(10, 15),
            conversation=self.arrival_dm_id,
            sender=ARRIVAL.person_id,
            body=(
                "Hi Desmond — Victor says you're my first stop. Where do "
                "I find the workflow playbook, and is there a right order "
                "to read it in?"
            ),
        )
        self._chat(
            drafts,
            minter,
            at=_t(10, 22),
            conversation=self.arrival_dm_id,
            sender="per-desmond-ortiz",
            body=(
                "Welcome! Playbooks folder on the shared drive — start "
                "with the tax return workflow, then the time & billing "
                "policy before you log anything. Coffee at 3 and I'll "
                "walk you through the Kestrel file."
            ),
        )

    # -- the Harbor Light audit --------------------------------------------

    def _pbc_content(self, *, open_items: tuple[str, ...]) -> str:
        received = (
            "Trial balance and general ledger (full fiscal year)",
            "Bank statements and reconciliations, all accounts",
            "Board minutes for the fiscal year",
            "Grant agreements and award letters",
            "Payroll registers and allocation schedules",
        )
        return "\n".join(
            (
                f"# {PBC_LIST_TITLE}",
                "",
                "## Received",
                *(f"- [x] {item}" for item in received),
                "",
                "## Open",
                *(f"- [ ] {item}" for item in open_items),
                "",
            )
        )

    def _audit(
        self,
        day: date,
        rng: random.Random,
        minter: IdMinter,
        drafts: list[TimedDraft],
    ) -> None:
        naomi = "per-naomi-castellanos"
        imogen = "per-imogen-carraway"

        if day == date(2026, 2, 10):
            drafts.append(
                TimedDraft(
                    at=SimDuration(_t(9, 40)),
                    source=_entity("per-theo-brandt"),
                    payload=DocumentCreatedPayload(
                        kind="document.created",
                        document_id=self._pbc_doc_id,
                        author="per-theo-brandt",
                        title=PBC_LIST_TITLE,
                        path="/clients/harbor-light/audit/pbc-list.md",
                        location="repository",
                        content_format="markdown",
                        content=self._pbc_content(
                            open_items=(
                                "Investment statements and broker confirmations",
                                "Donor restriction schedules",
                                "Fixed asset additions support",
                                "Subsequent receipts for AR testing",
                                "Insurance policies in force",
                            )
                        ),
                    ),
                )
            )
            self._status(
                drafts,
                at=_t(10, 0),
                ticket=_AUDIT_TICKET,
                actor=imogen,
                old="open",
                new="in-progress",
            )
            self._email(
                drafts,
                minter,
                at=_t(10, 20),
                sender=imogen,
                to=(naomi,),
                cc=("per-hana-sato",),
                subject="Harbor Light FY2025 audit — PBC list",
                body=(
                    "Hi Naomi,\n\nKicking off the FY2025 audit — the "
                    "prepared-by-client list is attached. The open section "
                    "is what we still need; the portal folder mirrors it. "
                    "We'll schedule planning once the first tranche is "
                    "in.\n\nBest,\nImogen Carraway\nCalder & Finch, CPAs"
                ),
                attachments=(
                    Attachment(
                        filename="pbc-list.md",
                        media_type=_MD,
                        document_id=self._pbc_doc_id,
                    ),
                ),
                thread_key="audit:pbc",
            )

        if day == date(2026, 2, 24):
            self._pbc_revision += 1
            drafts.append(
                TimedDraft(
                    at=SimDuration(_t(11, 10)),
                    source=_entity("per-theo-brandt"),
                    payload=DocumentRevisedPayload(
                        kind="document.revised",
                        document_id=self._pbc_doc_id,
                        author="per-theo-brandt",
                        revision=self._pbc_revision,
                        change_summary="Marked first tranche received",
                        content=self._pbc_content(
                            open_items=(
                                "Donor restriction schedules",
                                "Subsequent receipts for AR testing",
                            )
                        ),
                    ),
                )
            )
            self._email(
                drafts,
                minter,
                at=_t(11, 30),
                sender=imogen,
                to=(naomi,),
                subject="Re: Harbor Light FY2025 audit — PBC list",
                body=(
                    "Hi Naomi,\n\nGood progress — most items are in and "
                    "the list is updated. Two things remain: the donor "
                    "restriction schedules and the subsequent receipts "
                    "detail. Once those land we'll confirm fieldwork "
                    "dates.\n\nBest,\nImogen"
                ),
                reply_key="audit:pbc",
                thread_key="audit:pbc",
            )

        if day == date(2026, 3, 16):
            drafts.append(
                TimedDraft(
                    at=SimDuration(_t(8, 40)),
                    source=_entity(imogen),
                    payload=CalendarEventScheduledPayload(
                        kind="calendar.event.scheduled",
                        calendar_event_id=minter.mint("cal"),
                        organizer=imogen,
                        title="Audit planning — Harbor Light Foundation",
                        start=SimTime(self._day_offset(day) + _t(10, 0)),
                        end=SimTime(self._day_offset(day) + _t(11, 0)),
                        attendees=_AUDIT_TEAM,
                        description=(
                            "Risk assessment, materiality, and the "
                            "fieldwork plan for FY2025."
                        ),
                    ),
                )
            )

        if day in (date(2026, 3, 23), date(2026, 3, 24)):
            ordinal = "one" if day.day == 23 else "two"
            drafts.append(
                TimedDraft(
                    at=SimDuration(_t(8, 0)),
                    source=_entity(imogen),
                    payload=CalendarEventScheduledPayload(
                        kind="calendar.event.scheduled",
                        calendar_event_id=minter.mint("cal"),
                        organizer=imogen,
                        title=(
                            "Fieldwork day "
                            f"{ordinal} — Harbor Light Foundation (on site)"
                        ),
                        start=SimTime(self._day_offset(day) + _t(9, 0)),
                        end=SimTime(self._day_offset(day) + _t(17, 0)),
                        attendees=_AUDIT_TEAM[:3],
                        description="On-site testing at the foundation offices.",
                    ),
                )
            )

        if day == date(2026, 3, 27):
            wrap = self._chat(
                drafts,
                minter,
                at=_t(15, 40),
                conversation=self._engagements,
                sender=imogen,
                body=(
                    "Harbor Light fieldwork wrapped. Open items are down "
                    "to donor restrictions documentation and one revenue "
                    "cutoff sample. Drafting begins next week."
                ),
            )
            self._chat(
                drafts,
                minter,
                at=_t(15, 52),
                conversation=self._engagements,
                sender="per-theo-brandt",
                body="Cutoff sample cleared this afternoon — support in the file.",
                reply_to=wrap,
            )

        if day == date(2026, 4, 28):
            self._pbc_revision += 1
            drafts.append(
                TimedDraft(
                    at=SimDuration(_t(9, 50)),
                    source=_entity("per-theo-brandt"),
                    payload=DocumentRevisedPayload(
                        kind="document.revised",
                        document_id=self._pbc_doc_id,
                        author="per-theo-brandt",
                        revision=self._pbc_revision,
                        change_summary="Single open item remains",
                        content=self._pbc_content(
                            open_items=("Donor restriction schedules — final Q4",)
                        ),
                    ),
                )
            )
            self._email(
                drafts,
                minter,
                at=_t(10, 10),
                sender=imogen,
                to=(naomi,),
                subject="Re: Harbor Light FY2025 audit — PBC list",
                body=(
                    "Hi Naomi,\n\nOne last item is holding the file open — "
                    "the final-quarter donor restriction schedule. "
                    "Everything else is tested and drafted.\n\nBest,\nImogen"
                ),
                reply_key="audit:pbc",
            )

        if day == date(2026, 5, 15):
            self._status(
                drafts,
                at=_t(14, 0),
                ticket=_AUDIT_TICKET,
                actor="per-hana-sato",
                old="in-progress",
                new="review",
            )
            self._comment(
                drafts,
                at=_t(14, 10),
                ticket=_AUDIT_TICKET,
                actor="per-hana-sato",
                body="Draft financial statements and 990 in partner review.",
            )

        if day == date(2026, 6, 25):
            document_id = minter.mint("doc")
            drafts.append(
                TimedDraft(
                    at=SimDuration(_t(10, 30)),
                    source=_entity(imogen),
                    payload=DocumentCreatedPayload(
                        kind="document.created",
                        document_id=document_id,
                        author=imogen,
                        title=DRAFT_FS_TITLE,
                        path=(
                            "/clients/harbor-light/audit/"
                            "draft-financial-statements.docx"
                        ),
                        location="repository",
                        content_format="formatted",
                        content=self._draft_fs_content(),
                    ),
                )
            )
            self._email(
                drafts,
                minter,
                at=_t(11, 0),
                sender=imogen,
                to=(naomi,),
                cc=("per-hana-sato",),
                subject="Harbor Light FY2025 — draft financial statements",
                body=(
                    "Hi Naomi,\n\nThe draft financial statements are "
                    "attached for your review ahead of the board meeting. "
                    "The opinion is unmodified; two immaterial adjustments "
                    "are described in the summary schedule. We'll issue "
                    "final once the board signs off.\n\nBest,\nImogen"
                ),
                attachments=(
                    Attachment(
                        filename="draft-financial-statements.docx",
                        media_type=_DOCX,
                        document_id=document_id,
                    ),
                ),
            )

        if day == date(2026, 6, 30):
            self._status(
                drafts,
                at=_t(16, 30),
                ticket=_AUDIT_TICKET,
                actor="per-hana-sato",
                old="review",
                new="closed",
            )
            self._comment(
                drafts,
                at=_t(16, 40),
                ticket=_AUDIT_TICKET,
                actor="per-hana-sato",
                body=(
                    "Final report issued and 990 e-filed; engagement closed for FY2025."
                ),
            )

    def _draft_fs_content(self) -> str:
        return FormattedDocument(
            blocks=(
                HeadingBlock(
                    kind="heading",
                    level=1,
                    text="Harbor Light Foundation — Financial Statements (Draft)",
                ),
                ParagraphBlock(
                    kind="paragraph",
                    text=(
                        "Draft for board review — fiscal year ended June 30, "
                        "2025. Unmodified opinion expected; two immaterial "
                        "passed adjustments summarized below."
                    ),
                ),
                TableBlock(
                    kind="table",
                    columns=("Statement line", "FY2025 ($)", "FY2024 ($)"),
                    rows=(
                        ("Total assets", "4,812,300", "4,505,140"),
                        (
                            "Net assets without donor restrictions",
                            "2,150,870",
                            "2,004,410",
                        ),
                        (
                            "Net assets with donor restrictions",
                            "1,918,600",
                            "1,846,220",
                        ),
                        ("Total revenue and support", "3,268,450", "3,090,780"),
                        ("Total expenses", "3,049,610", "2,957,330"),
                    ),
                ),
                ListBlock(
                    kind="list",
                    ordered=False,
                    items=(
                        "Passed adjustment: $8,140 grant receivable cutoff",
                        "Passed adjustment: $5,920 depreciation true-up",
                    ),
                ),
                ParagraphBlock(
                    kind="paragraph",
                    text=(
                        "Program expenses represent 81 percent of total "
                        "spending, consistent with the prior year."
                    ),
                ),
            )
        ).canonical_json()

    # -- plumbing -----------------------------------------------------------

    @staticmethod
    def _day_offset(day: date) -> int:
        start = date.fromisoformat(WINDOW.start_date)
        return (day - start).days * SECONDS_PER_DAY

    def drafts_for(self, day: str, minter: IdMinter) -> tuple[TimedDraft, ...]:
        current = date.fromisoformat(day)
        rng = derive_rng(self._seed, "calder.arcs", day)
        drafts: list[TimedDraft] = []
        self._closes(current, rng, minter, drafts)
        self._tax_season(current, rng, minter, drafts)
        self._estimates(current, rng, minter, drafts)
        self._arrival(current, rng, minter, drafts)
        self._audit(current, rng, minter, drafts)
        drafts.sort(key=lambda draft: int(draft.at))
        return tuple(drafts)
