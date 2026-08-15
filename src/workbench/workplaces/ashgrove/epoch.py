"""Ashgrove Reid LLP: a second firm, for comparison.

Same people, different practice. The seventeen professionals are exactly
Calder's — that is the controlled variable — but they work an
assurance-led book: audits, Single Audits, benefit-plan work, and
transaction advisory, for a different set of clients on a different
calendar (see ``season.py``). Running the same engine over the same cast
with a different book is what makes the two datasets comparable: any
difference in shape belongs to the practice, not to the people or the
machinery.

``epoch_spec(days=N, version=2)`` mirrors Calder's entry point, so the
run manager, the fidelity harness, and the task builders all work
unchanged.
"""

from workbench.core.seed import Seed
from workbench.simulation.actors.client import ClientActorParams
from workbench.simulation.director import PoissonCueSchedule
from workbench.simulation.workplace.spec import (
    ChannelSpec,
    PersonSpec,
    SeedCalendarEvent,
    SeedDocument,
    SeedTicket,
    WorkplaceSpec,
)
from workbench.workplaces.ashgrove.season import CLIENT_PROFILES, season_multipliers
from workbench.workplaces.calder.spec import LIVE_DAY_SPEC

EPOCH_START = "2026-01-05"
FIRM = "Ashgrove Reid LLP"
DOMAIN = "ashgrovereid.example"

# The client book: an assurance practice's clients, not a tax practice's.
_CLIENTS: tuple[tuple[str, str, str, str, str, tuple[str, ...]], ...] = (
    (
        "per-harriet-vance",
        "Harriet Vance",
        "Fairmount Community Foundation",
        "Chief Financial Officer",
        "Board-minded and precise; asks what the auditors will ask.",
        ("Imogen Carraway", "Hana Sato"),
    ),
    (
        "per-desmond-blakely",
        "Desmond Blakely",
        "Rivergate Housing Trust",
        "Finance Director",
        "Grant-funded and compliance-anxious; quotes circular references.",
        ("Imogen Carraway", "Elias Finch"),
    ),
    (
        "per-nora-behrens",
        "Nora Behrens",
        "Kestrel Manufacturing",
        "HR & Benefits Manager",
        "Practical, deadline-driven, apologetic about recordkeeper data.",
        ("Sylvia Nakamura", "Hana Sato"),
    ),
    (
        "per-idris-mensah",
        "Idris Mensah",
        "Cardinal Ridge Builders",
        "Controller",
        "Job-cost fluent, blunt about margins, hates surprises.",
        ("Elias Finch", "Desmond Ortiz"),
    ),
    (
        "per-priya-raman",
        "Priya Raman",
        "Northwind Software",
        "VP Finance",
        "Fast and technical; writes in bullets, expects the same.",
        ("Victor Alade", "Colin Mackey"),
    ),
    (
        "per-tomas-lindgren",
        "Tomas Lindgren",
        "Harbor Light Distribution",
        "Operations Controller",
        "Warehouse-first thinker; schedules around physical reality.",
        ("Hana Sato", "Freya Holt"),
    ),
    (
        "per-adaeze-okonkwo",
        "Adaeze Okonkwo",
        "Meridian Family Health",
        "Practice Administrator",
        "Mission-first, payor-mix literate, careful with patient data.",
        ("Colin Mackey", "Imogen Carraway"),
    ),
    (
        "per-benedict-shaw",
        "Benedict Shaw",
        "Shaw & Associates (peer reviewer)",
        "Peer Review Captain",
        "Formal and procedural; cites standards by number.",
        ("Rosalind Calder", "Imogen Carraway"),
    ),
    (
        "per-lucia-arroyo",
        "Lucia Arroyo",
        "Stonebridge Property Group",
        "Assistant Controller",
        "Organized, asks good questions, keeps her own tie-outs.",
        ("Elias Finch", "Lucia Mendes"),
    ),
    (
        "per-garrett-poole",
        "Garrett Poole",
        "Ashfield Pension Trust",
        "Trustee",
        "Deliberate and formal; thinks in fiduciary duty.",
        ("Hana Sato", "Victor Alade"),
    ),
)

# Engagements open at genesis: what the firm is already doing on day one.
_ENGAGEMENTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "Fairmount Community Foundation — FY2025 financial statement audit",
        "Calendar-year audit with a Single Audit component; fieldwork planned "
        "for February. Materiality memo and risk assessment are open.",
        "per-imogen-carraway",
        "per-harriet-vance",
    ),
    (
        "Fairmount Community Foundation — Single Audit (Uniform Guidance)",
        "Federal expenditures crossed the threshold this year. Major program "
        "determination and the SEFA are the open items.",
        "per-imogen-carraway",
        "per-harriet-vance",
    ),
    (
        "Rivergate Housing Trust — FY2025 audit and Single Audit",
        "HUD-funded programs with subrecipient monitoring questions carried "
        "forward from last year's management letter.",
        "per-elias-finch",
        "per-desmond-blakely",
    ),
    (
        "Kestrel Manufacturing 401(k) — plan year 2025 audit",
        "Limited-scope becomes a full-scope this year. Census reconciliation "
        "is the known problem area; 5500 extension runs to October 15.",
        "per-hana-sato",
        "per-nora-behrens",
    ),
    (
        "Cardinal Ridge Builders — FY2025 audit",
        "Percentage-of-completion revenue, surety wants issuance by March 31. "
        "Two jobs flagged for change-order cutoff testing.",
        "per-elias-finch",
        "per-idris-mensah",
    ),
    (
        "Northwind Software — quality of earnings",
        "Buy-side diligence ahead of a raise; multi-year license revenue "
        "recognition is the central question.",
        "per-victor-alade",
        "per-priya-raman",
    ),
    (
        "Harbor Light Distribution — FY2025 audit",
        "Inventory observation scheduling is unsettled because the warehouse "
        "is mid-move. Prior-year cutoff comment to clear.",
        "per-hana-sato",
        "per-tomas-lindgren",
    ),
    (
        "Meridian Family Health — FY2025 review",
        "Review engagement, not an audit. Receivable aging and payor mix "
        "shifted materially this year.",
        "per-colin-mackey",
        "per-adaeze-okonkwo",
    ),
    (
        "Stonebridge Property Group — FY2025 audit",
        "Real-estate partnerships with related-party leases; internal control "
        "memo needs refreshing after a new location opened.",
        "per-elias-finch",
        "per-lucia-arroyo",
    ),
    (
        "Ashfield Pension Trust — FY2025 audit",
        "Defined-benefit plan; investment statements historically arrive late "
        "and the trustees want an interim report.",
        "per-hana-sato",
        "per-garrett-poole",
    ),
    (
        "Firm — 2026 peer review preparation",
        "Shaw & Associates is the reviewer. Independence documentation and "
        "engagement-letter coverage are the open threads.",
        "per-rosalind-calder",
        "per-benedict-shaw",
    ),
    (
        "Firm — audit methodology refresh",
        "Rolling the quality-management standards into the firm's own "
        "engagement templates and review checklists.",
        "per-imogen-carraway",
        "per-rosalind-calder",
    ),
)


# The 2026 rate sheet. Realization, WIP, and write-offs are meaningless
# without rates, and the roles carrying none are the ones that genuinely do
# not bill: office, admin, IT.
_BILL_RATES: dict[str, int] = {
    "Managing Partner": 47500,
    "Partner, Client Accounting & Advisory": 42500,
    "Principal, Assurance": 40000,
    "Audit Manager": 32500,
    "Tax Manager": 31000,
    "Senior Accountant, Assurance": 24500,
    "Senior Accountant, Tax": 23500,
    "Client Accounting Lead": 21500,
    "Staff Accountant": 17500,
    "Payroll Specialist": 15500,
}


def _client_params(person_id: str) -> ClientActorParams:
    for pid, name, organization, role, temperament, contacts in _CLIENTS:
        if pid == person_id:
            return ClientActorParams(
                person_id=pid,
                name=name,
                organization=organization,
                role=role,
                temperament=temperament,
                contacts=contacts,
            )
    raise KeyError(person_id)


def _people() -> tuple[PersonSpec, ...]:
    """Calder's professionals, re-badged, plus Ashgrove's own clients."""

    people: list[PersonSpec] = []
    for person in LIVE_DAY_SPEC.people:
        if person.affiliation != "internal":
            continue
        local = person.email_address.split("@")[0]
        persona = person.persona
        rate = _BILL_RATES.get(person.title)
        if persona is not None and rate is not None:
            persona = persona.model_copy(update={"bill_rate_cents": rate})
        people.append(
            person.model_copy(
                update={"email_address": f"{local}@{DOMAIN}", "persona": persona}
            )
        )
    for pid, name, organization, role, _temperament, _contacts in _CLIENTS:
        local = name.lower().replace(" ", ".")
        domain = organization.split("(")[0].strip().lower()
        domain = "".join(ch for ch in domain if ch.isalnum() or ch == " ")
        domain = domain.replace(" ", "") + ".example"
        people.append(
            PersonSpec(
                person_id=pid,
                name=name,
                email_address=f"{local}@{domain}",
                title=role,
                department="Client",
                manager=None,
                affiliation="external",
                timezone="America/Los_Angeles",
                persona=None,
                client_persona=_client_params(pid),
            )
        )
    return tuple(people)


def _surfaces() -> tuple[
    tuple[ChannelSpec, ...], tuple[SeedDocument, ...], tuple[SeedTicket, ...]
]:
    staff = tuple(
        person.person_id
        for person in LIVE_DAY_SPEC.people
        if person.affiliation == "internal"
    )
    assurance = tuple(
        pid
        for pid in staff
        if pid
        in (
            "per-imogen-carraway",
            "per-hana-sato",
            "per-elias-finch",
            "per-rosalind-calder",
            "per-freya-holt",
        )
    )
    channels = (
        ChannelSpec(name="firm", members=staff),
        ChannelSpec(name="assurance", members=assurance or staff[:5]),
        ChannelSpec(name="engagements", members=staff),
        ChannelSpec(name="quality", members=assurance or staff[:5]),
    )
    documents = (
        SeedDocument(
            title="Audit Engagement Letter Template",
            path="/firm/templates/audit-engagement-letter.md",
            author="per-rosalind-calder",
            content=(
                "# Audit engagement letter — template\n\n"
                "Scope, responsibilities of management, auditor "
                "responsibilities under GAAS, reporting, fees, and the "
                "independence confirmation. Partner signs; manager sends.\n"
            ),
        ),
        SeedDocument(
            title="Independence & Quality Management Policy",
            path="/firm/policies/independence-policy.md",
            author="per-imogen-carraway",
            content=(
                "# Independence and quality management\n\n"
                "Annual confirmations, engagement-level independence checks, "
                "non-attest service limits, EQCR thresholds, and the "
                "documentation the peer reviewer will ask to see.\n"
            ),
        ),
        SeedDocument(
            title="Single Audit Playbook",
            path="/firm/playbooks/single-audit.md",
            author="per-imogen-carraway",
            content=(
                "# Single Audit (Uniform Guidance)\n\n"
                "Threshold determination, major program selection, SEFA "
                "preparation, subrecipient monitoring, and the reporting "
                "package with its submission deadline.\n"
            ),
        ),
        SeedDocument(
            title="PBC Request Template — Assurance",
            path="/firm/templates/pbc-assurance.md",
            author="per-hana-sato",
            content=(
                "# Prepared-by-client request\n\n"
                "Trial balance, reconciliations, confirmations list, "
                "agreements, minutes, and the inventory or census file where "
                "the engagement calls for one.\n"
            ),
        ),
        SeedDocument(
            title="Standard Rate Sheet 2026",
            path="/firm/billing/rate-sheet-2026.md",
            author="per-theo-brandt",
            content=(
                "# 2026 standard rates\n\n"
                "Partner, principal, manager, senior, and staff rates by "
                "service line, with the realization expectation the firm "
                "budgets each engagement against.\n"
            ),
        ),
    )
    tickets = tuple(
        SeedTicket(
            title=title,
            description=description,
            actor=assignee,
            requester=requester,
            assignee=assignee,
            status="Open",
            priority="Normal",
            ticket_type="engagement",
        )
        for title, description, assignee, requester in _ENGAGEMENTS
    )
    return channels, documents, tickets


def epoch_spec(days: int = 194, *, version: int = 2) -> WorkplaceSpec:
    """Ashgrove's epoch. v2 behaviours are on by default — this firm has no
    v1 recording to stay byte-compatible with."""

    channels, documents, tickets = _surfaces()
    return LIVE_DAY_SPEC.model_copy(
        update={
            "workplace_id": "ashgrove",
            "display_name": FIRM,
            "epoch": _epoch_datetime(),
            "days": days,
            "people": _people(),
            "arrivals": (),
            "channels": channels,
            "seed_documents": documents,
            "seed_tickets": tickets,
            "seed_calendar": (
                SeedCalendarEvent(
                    organizer="per-imogen-carraway",
                    title="Assurance status",
                    start_clock="09:00",
                    end_clock="09:20",
                    attendees=(
                        "per-imogen-carraway",
                        "per-hana-sato",
                        "per-elias-finch",
                        "per-freya-holt",
                    ),
                    description="Fieldwork status, blockers, and review queue.",
                ),
            ),
            "day_script": (),
            "timesheets": version >= 2,
        }
    )


def _epoch_datetime():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.fromisoformat(f"{EPOCH_START}T00:00:00").replace(
        tzinfo=ZoneInfo(LIVE_DAY_SPEC.timezone)
    )


def epoch_director(seed: Seed) -> PoissonCueSchedule:
    return PoissonCueSchedule(
        seed=seed,
        clients=CLIENT_PROFILES,
        season=season_multipliers,
        max_cues_per_day=8,
    )


__all__ = ["EPOCH_START", "FIRM", "epoch_director", "epoch_spec"]
