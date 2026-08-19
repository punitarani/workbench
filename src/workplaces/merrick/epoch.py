"""Merrick Stanton LLP: a twenty-one-person litigation-and-transactions firm,
recorded over six months.

``epoch_spec(days=N)`` mirrors the other firms' entry points, so the run
manager, the fidelity harness and the task builders work unchanged.

Two things about this world are deliberately unlike the accounting firms
already in the tree, because they are what a law firm has and an audit
practice does not:

**Deadlines are set by somebody else.** A court's scheduling order moves
and the firm rearranges around it. That makes a whole class of fact —
what the deadline *is now*, versus what it was when the matter opened —
recorded rather than derivable, which is the only kind of fact a task
may grade.

**Work product becomes final by leaving the firm.** A brief that is
filed, an agreement that is executed, an opinion that is issued: these
are not drafts anyone edits afterwards. That is what makes the document
formats here real rather than decorative — an issued document is a PDF
because issuing it is what made it one.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from core.seed import Seed
from simulation.director import PoissonCueSchedule
from simulation.gm.grounded import TicketVocabulary
from simulation.workplace.spec import (
    ChannelSpec,
    OrganizationSpec,
    SeedCalendarEvent,
    SeedDocument,
    SeedTicket,
    WorkplaceSpec,
)
from workplaces.merrick.people import (
    MATTER_PRIORITIES,
    MATTER_STATUSES,
    MATTER_TYPES,
    ORGANIZATIONS,
    PEOPLE,
    TZ,
)
from workplaces.merrick.season import CLIENT_PROFILES, season_multipliers

EPOCH_START = "2026-01-05"
FIRM = "Merrick Stanton LLP"
DOMAIN = "merrickstanton.example"

# Six months of calendar days from the first Monday of the year. Weekends
# inside the window are skipped by the runtime day chain, so this is
# roughly 130 workdays.
FULL_WINDOW_DAYS = 180


# (title, description, assignee, requester, status, priority, type, client)
_MATTERS: tuple[tuple[str, str, str, str, str, str, str, str | None], ...] = (
    (
        "Coastal Meridian - regulatory inquiry",
        "Response to the banking regulator's document request concerning "
        "commercial lending practices in 2024-2025. Rolling productions, "
        "privilege log, and two custodial interviews outstanding.",
        "per-hyunwoo-bae",
        "per-marguerite-oyelaran",
        "Discovery",
        "Urgent",
        "Regulatory",
        "org-coastal-meridian",
    ),
    (
        "Coastal Meridian - credit agreement covenant review",
        "Advice on whether the 2023 amendment altered the financial covenant "
        "basket, and what that means for the pending waiver request.",
        "per-elena-vasquez-reyes",
        "per-marguerite-oyelaran",
        "Active",
        "Standard",
        "Advisory",
        "org-coastal-meridian",
    ),
    (
        "Halden Orthopedics - Renwick non-compete",
        "Enforcement of a restrictive covenant against a departing orthopedic "
        "surgeon who has opened a competing practice within the restricted "
        "radius. Preliminary injunction briefing.",
        "per-fionnuala-doherty",
        "per-roland-pesch",
        "Briefing",
        "Urgent",
        "Employment",
        "org-halden-orthopedics",
    ),
    (
        "Halden Orthopedics - Tessaro malpractice defence",
        "Defence of a professional negligence claim arising from a 2024 "
        "procedure. Expert disclosure and mediation scheduling.",
        "per-cecile-marchand",
        "per-roland-pesch",
        "Discovery",
        "Standard",
        "Litigation",
        "org-halden-orthopedics",
    ),
    (
        "Verity Grain - Ardmore elevator acquisition",
        "Acquisition of three grain elevators and associated rail siding. "
        "Purchase agreement, environmental diligence, and financing "
        "coordination with the lender's counsel.",
        "per-ingrid-solheim",
        "per-imelda-frost",
        "Active",
        "Standard",
        "Transaction",
        "org-verity-grain",
    ),
    (
        "Verity Grain - Hollstead supply dispute",
        "Dispute over rejected deliveries and the buyer's claim of "
        "non-conforming goods. Assessing counterclaim for the unpaid "
        "invoices.",
        "per-lucien-abara",
        "per-imelda-frost",
        "Active",
        "Standard",
        "Litigation",
        "org-verity-grain",
    ),
    (
        "Pellumbra - Ravenna collaboration agreement",
        "Negotiation of a research collaboration with contested ownership of "
        "improvements and a disputed field-of-use carve-out.",
        "per-gideon-park",
        "per-teodor-vasiliev",
        "Active",
        "Urgent",
        "IP",
        "org-pellumbra",
    ),
    (
        "Pellumbra - Series C disclosure schedule",
        "Preparation of the disclosure schedule and review of the "
        "representations for the Series C financing.",
        "per-elena-vasquez-reyes",
        "per-teodor-vasiliev",
        "Active",
        "Standard",
        "Transaction",
        "org-pellumbra",
    ),
    (
        "Pellumbra - cross-border clinical data assessment",
        "Assessment of clinical trial data transfers across three "
        "jurisdictions and the contractual mechanisms required.",
        "per-oskar-ravndal",
        "per-teodor-vasiliev",
        "Active",
        "Routine",
        "Regulatory",
        "org-pellumbra",
    ),
    (
        "Northmoor - Sandhurst platform acquisition",
        "Platform acquisition with a management rollover and an incentive "
        "equity plan. Quarter-end close targeted.",
        "per-dov-reinhardt",
        "per-saoirse-mulvaney",
        "Active",
        "Urgent",
        "Transaction",
        "org-northmoor-capital",
    ),
    (
        "Northmoor - Sandhurst add-on diligence",
        "Confirmatory diligence on two bolt-on targets, with quality of "
        "earnings and customer concentration questions outstanding.",
        "per-mira-chandrasekhar",
        "per-saoirse-mulvaney",
        "Active",
        "Standard",
        "Transaction",
        "org-northmoor-capital",
    ),
    (
        "Sable Ridge - driver meal-break collective action",
        "Defence of a collective action alleging unpaid meal and rest breaks "
        "across four distribution centres. Conditional certification briefing.",
        "per-jamal-okonkwo",
        "per-clement-abioye",
        "Briefing",
        "Urgent",
        "Employment",
        "org-sable-ridge",
    ),
    (
        "Sable Ridge - reduction in force planning",
        "Counselling on a twelve percent headcount reduction: selection "
        "criteria, disparate impact analysis, and notice obligations.",
        "per-fionnuala-doherty",
        "per-clement-abioye",
        "Active",
        "Standard",
        "Employment",
        "org-sable-ridge",
    ),
    (
        "Sable Ridge - Devane harassment investigation",
        "Independent investigation into a complaint against a regional "
        "supervisor, conducted under privilege.",
        "per-petra-kovacs",
        "per-clement-abioye",
        "Active",
        "Urgent",
        "Employment",
        "org-sable-ridge",
    ),
    (
        "Atwater Foods - product recall coverage",
        "Coverage analysis and insurer correspondence arising from a "
        "voluntary recall, including the reservation of rights.",
        "per-cecile-marchand",
        "per-yuki-tanabe",
        "Active",
        "Standard",
        "Litigation",
        "org-atwater-foods",
    ),
    (
        "Atwater Foods - trademark oppositions",
        "Two opposition proceedings against the house mark in adjacent "
        "classes, with a consent agreement under discussion in one.",
        "per-klara-bendtsen",
        "per-yuki-tanabe",
        "Active",
        "Routine",
        "IP",
        "org-atwater-foods",
    ),
    (
        "Linden Robotics - Pryor trade secret claim",
        "Claim against a former engineering lead alleging misappropriation of "
        "control-loop source and design files. Expedited discovery and a "
        "forensic protocol.",
        "per-bennett-ashworth",
        "per-priyanka-deshmukh",
        "Discovery",
        "Emergency",
        "IP",
        "org-linden-robotics",
    ),
    (
        "Linden Robotics - Fairmont OEM licence",
        "Negotiation of an OEM licence with a disputed indemnity cap and "
        "field-of-use restriction.",
        "per-klara-bendtsen",
        "per-priyanka-deshmukh",
        "Active",
        "Standard",
        "IP",
        "org-linden-robotics",
    ),
    (
        "Cotswold Mutual - Aldworth professional liability",
        "Panel defence of a professional liability claim, with reserve "
        "reporting and adherence to the insurer's billing guidelines.",
        "per-lucien-abara",
        "per-desmond-achebe",
        "Discovery",
        "Standard",
        "Litigation",
        "org-cotswold-mutual",
    ),
    (
        "Cotswold Mutual - coverage opinion, Brackley claim",
        "Opinion on the insurer's coverage position under the professional "
        "services exclusion.",
        "per-cecile-marchand",
        "per-desmond-achebe",
        "Active",
        "Standard",
        "Advisory",
        "org-cotswold-mutual",
    ),
    (
        "Brightwell Academy - employment complaint",
        "Advice on an internal complaint against a long-serving employee, "
        "including the board's disclosure obligations.",
        "per-petra-kovacs",
        "per-harriet-lindqvist",
        "Active",
        "Standard",
        "Employment",
        "org-brightwell-academy",
    ),
    (
        "Brightwell Academy - handbook and policy revision",
        "Annual revision of the employee handbook and related policies ahead "
        "of the academic year.",
        "per-fionnuala-doherty",
        "per-harriet-lindqvist",
        "Active",
        "Routine",
        "Employment",
        "org-brightwell-academy",
    ),
    # --- non-billable matter codes ---------------------------------------
    #
    # Every firm carries these, and without them a sixth of the world's
    # timekeeping disappears. Measured on the first three recorded days:
    # personas tried to log admin, internal-meeting and practice-group time,
    # had nowhere to put it, invented codes (`internal-000001`,
    # `admin-000001`, `internal-ip-tech-group`), and the referee rejected
    # every one — **84 of 500 attempted entries, 16.8%, dropped**.
    #
    # The referee was right to reject them; the world was wrong not to
    # offer the codes. A utilisation or realization figure computed over a
    # record missing a sixth of its hours is not wrong by a little.
    #
    # `client_ref` is None on all of these, which is the point: they are the
    # firm's own time, and a report that folds them into a client's total is
    # answering a different question than the one the partners asked.
    (
        "Firm - conflicts and new matter intake",
        "Standing matter for conflicts searches, engagement letters, and new "
        "matter opening across the firm.",
        "per-lucien-abara",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
    (
        "Firm - billing, WIP and realization",
        "Standing matter for the monthly billing cycle: prebill release, "
        "invoice issue, write-offs, and the partner reporting pack.",
        "per-ulrich-bergmann",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
    (
        "Firm - administration",
        "Non-billable. General firm administration, practice management, and "
        "time that belongs to no client matter.",
        "per-adaora-nwosu",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
    (
        "Firm - internal meetings",
        "Non-billable. Practice group meetings, partner meetings, docket call, "
        "and firm-wide standing meetings.",
        "per-adaora-nwosu",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
    (
        "Firm - business development",
        "Non-billable. Pitches, client entertainment, proposals, and "
        "relationship work not chargeable to a matter.",
        "per-dov-reinhardt",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
    (
        "Firm - professional development",
        "Non-billable. Continuing legal education, training, andknowledge "
        "management contributions.",
        "per-cecile-marchand",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
    (
        "Firm - pro bono",
        "Non-billable to the firm's clients. Pro bono representation and "
        "community legal work carried at no charge.",
        "per-fionnuala-doherty",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
    (
        "Firm - recruiting",
        "Non-billable. Lateral and campus recruiting, interviews, and "
        "summer programme supervision.",
        "per-gideon-park",
        "per-adaora-nwosu",
        "Active",
        "Routine",
        "Advisory",
        None,
    ),
)


_CHANNELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "firm-announcements",
        tuple(p.person_id for p in PEOPLE if p.affiliation == "internal"),
    ),
    (
        "litigation-group",
        (
            "per-bennett-ashworth",
            "per-cecile-marchand",
            "per-hyunwoo-bae",
            "per-lucien-abara",
            "per-noor-haddad",
            "per-rosalie-duchamp",
        ),
    ),
    (
        "corporate-group",
        (
            "per-dov-reinhardt",
            "per-elena-vasquez-reyes",
            "per-ingrid-solheim",
            "per-mira-chandrasekhar",
            "per-quentin-sarr",
            "per-samir-bhatt",
        ),
    ),
    (
        "employment-group",
        (
            "per-fionnuala-doherty",
            "per-jamal-okonkwo",
            "per-petra-kovacs",
        ),
    ),
    (
        "ip-technology",
        (
            "per-gideon-park",
            "per-klara-bendtsen",
            "per-oskar-ravndal",
        ),
    ),
    (
        "docket-and-deadlines",
        (
            "per-thandiwe-mokoena",
            "per-bennett-ashworth",
            "per-cecile-marchand",
            "per-hyunwoo-bae",
            "per-lucien-abara",
            "per-rosalie-duchamp",
            "per-jamal-okonkwo",
        ),
    ),
    (
        "billing-and-wip",
        (
            "per-ulrich-bergmann",
            "per-adaora-nwosu",
            "per-dov-reinhardt",
            "per-bennett-ashworth",
            "per-fionnuala-doherty",
            "per-gideon-park",
            "per-cecile-marchand",
            "per-elena-vasquez-reyes",
        ),
    ),
    (
        "linden-pryor-trade-secret",
        (
            "per-bennett-ashworth",
            "per-hyunwoo-bae",
            "per-noor-haddad",
            "per-klara-bendtsen",
            "per-rosalie-duchamp",
        ),
    ),
    (
        "northmoor-sandhurst",
        (
            "per-dov-reinhardt",
            "per-ingrid-solheim",
            "per-mira-chandrasekhar",
            "per-quentin-sarr",
            "per-samir-bhatt",
            "per-elena-vasquez-reyes",
        ),
    ),
    (
        "sable-ridge-wage-hour",
        (
            "per-jamal-okonkwo",
            "per-fionnuala-doherty",
            "per-petra-kovacs",
            "per-noor-haddad",
        ),
    ),
)


def _seed_documents() -> tuple[SeedDocument, ...]:
    """Deliberately few. The firm's file room should be what the firm
    produced during the window, not what was placed there before it
    started — a seeded repository grades the author, not the world."""

    rate_card = {
        "sheets": [
            {
                "name": "Standard Rates",
                "rows": [
                    ["Timekeeper", "Title", "Practice", "Standard Rate"],
                    ["Adaora Nwosu", "Managing Partner", "Firm Management", 900],
                    ["Bennett Ashworth", "Partner", "Litigation", 825],
                    ["Cecile Marchand", "Partner", "Litigation", 780],
                    ["Dov Reinhardt", "Partner", "Corporate", 800],
                    ["Elena Vasquez-Reyes", "Partner", "Corporate", 765],
                    ["Fionnuala Doherty", "Partner", "Employment", 710],
                    ["Gideon Park", "Partner", "IP", 675],
                    ["Jamal Okonkwo", "Counsel", "Employment", 560],
                    ["Hyun-woo Bae", "Senior Associate", "Litigation", 520],
                    ["Ingrid Solheim", "Senior Associate", "Corporate", 495],
                    ["Lucien Abara", "Senior Associate", "Litigation", 485],
                    ["Klara Bendtsen", "Senior Associate", "IP", 475],
                    ["Mira Chandrasekhar", "Associate", "Corporate", 415],
                    ["Noor Haddad", "Associate", "Litigation", 405],
                    ["Oskar Ravndal", "Associate", "IP", 395],
                    ["Petra Kovacs", "Associate", "Employment", 385],
                    ["Quentin Sarr", "Associate", "Corporate", 345],
                    ["Rosalie Duchamp", "Senior Paralegal", "Litigation", 255],
                    ["Samir Bhatt", "Paralegal", "Corporate", 195],
                ],
            }
        ]
    }
    import json

    return (
        SeedDocument(
            author="per-ulrich-bergmann",
            title="Standard rate card, effective January 2026",
            path="administration/rates/standard-rate-card-2026.xlsx",
            content_format="spreadsheet",
            content=json.dumps(rate_card),
        ),
    )


def _calendar() -> tuple[SeedCalendarEvent, ...]:
    return (
        SeedCalendarEvent(
            organizer="per-thandiwe-mokoena",
            title="Docket call",
            start_clock="08:45",
            end_clock="09:00",
            attendees=(
                "per-thandiwe-mokoena",
                "per-bennett-ashworth",
                "per-cecile-marchand",
                "per-hyunwoo-bae",
                "per-lucien-abara",
                "per-rosalie-duchamp",
            ),
            description=(
                "Every deadline falling in the next ten days, by matter, with "
                "the owner named."
            ),
            recurrence="daily",
        ),
        SeedCalendarEvent(
            organizer="per-dov-reinhardt",
            title="Corporate deal status",
            start_clock="09:15",
            end_clock="09:45",
            attendees=(
                "per-dov-reinhardt",
                "per-elena-vasquez-reyes",
                "per-ingrid-solheim",
                "per-mira-chandrasekhar",
                "per-quentin-sarr",
                "per-samir-bhatt",
            ),
            description="Live deals, conditions outstanding, and closing dates.",
            recurrence="daily",
        ),
        SeedCalendarEvent(
            organizer="per-fionnuala-doherty",
            title="Employment practice huddle",
            start_clock="09:30",
            end_clock="09:50",
            attendees=(
                "per-fionnuala-doherty",
                "per-jamal-okonkwo",
                "per-petra-kovacs",
            ),
            description="Investigations, filings, and client counselling in flight.",
            recurrence="daily",
        ),
        SeedCalendarEvent(
            organizer="per-adaora-nwosu",
            title="Partner matter review",
            start_clock="16:00",
            end_clock="17:00",
            attendees=(
                "per-adaora-nwosu",
                "per-bennett-ashworth",
                "per-cecile-marchand",
                "per-dov-reinhardt",
                "per-elena-vasquez-reyes",
                "per-fionnuala-doherty",
                "per-gideon-park",
            ),
            description=(
                "Matter status, staffing, budget against estimate, write-offs "
                "for approval, and new matter intake."
            ),
            recurrence="weekly",
        ),
        SeedCalendarEvent(
            organizer="per-ulrich-bergmann",
            title="Billing and WIP review",
            start_clock="11:00",
            end_clock="11:45",
            attendees=(
                "per-ulrich-bergmann",
                "per-adaora-nwosu",
                "per-dov-reinhardt",
                "per-bennett-ashworth",
                "per-fionnuala-doherty",
                "per-gideon-park",
            ),
            description=(
                "Unreleased prebills by billing partner, aged work in progress, "
                "and the write-offs awaiting approval."
            ),
            recurrence="weekly",
        ),
        SeedCalendarEvent(
            organizer="per-gideon-park",
            title="IP and technology group",
            start_clock="10:00",
            end_clock="10:30",
            attendees=(
                "per-gideon-park",
                "per-klara-bendtsen",
                "per-oskar-ravndal",
            ),
            description="Licences in negotiation, filings due, disputes.",
            recurrence="weekly",
        ),
    )


def epoch_spec(days: int = FULL_WINDOW_DAYS) -> WorkplaceSpec:
    """The firm's epoch. ``days`` is calendar days; weekends are skipped."""

    return WorkplaceSpec(
        workplace_id="merrick",
        display_name=FIRM,
        timezone=TZ,
        epoch=datetime.fromisoformat(f"{EPOCH_START}T00:00:00").replace(
            tzinfo=ZoneInfo(TZ)
        ),
        ticket_vocabulary=TicketVocabulary(
            statuses=MATTER_STATUSES,
            priorities=MATTER_PRIORITIES,
            ticket_types=MATTER_TYPES,
        ),
        people=PEOPLE,
        organizations=tuple(
            OrganizationSpec(org_id=org_id, name=name, category=category)
            for org_id, name, category, _label in ORGANIZATIONS
        ),
        channels=tuple(
            ChannelSpec(name=name, members=members) for name, members in _CHANNELS
        ),
        seed_documents=_seed_documents(),
        seed_calendar=_calendar(),
        seed_tickets=tuple(
            SeedTicket(
                title=title,
                description=description,
                actor="per-adaora-nwosu",
                requester=requester,
                assignee=assignee,
                status=status,
                priority=priority,
                ticket_type=ticket_type,
                client_ref=client_ref,
            )
            for (
                title,
                description,
                assignee,
                requester,
                status,
                priority,
                ticket_type,
                client_ref,
            ) in _MATTERS
        ),
        days=days,
        # A lawyer is in a deposition, a negotiation or a hearing for
        # hours at a time; checking mail every ninety minutes is closer to
        # the truth than every thirty, and the whole cast wakes on each
        # tick, so tick count is what a six-month window actually costs.
        wake_grid_minutes=90,
        end_of_day="18:30",
        timesheets=True,
        deliverables=True,
    )


def epoch_director(seed: Seed) -> PoissonCueSchedule:
    return PoissonCueSchedule(
        seed=seed,
        clients=CLIENT_PROFILES,
        season=season_multipliers,
        max_cues_per_day=10,
    )


__all__ = [
    "DOMAIN",
    "EPOCH_START",
    "FIRM",
    "FULL_WINDOW_DAYS",
    "epoch_director",
    "epoch_spec",
]
