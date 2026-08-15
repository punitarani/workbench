"""Ashgrove's year: an assurance practice, not a tax practice.

Calder's calendar is driven by the 1040/1120 filing season — a single
April crescendo with month-end closes underneath. An audit-led firm has a
different shape entirely, and that difference is the point of running a
second firm: fieldwork for calendar-year clients runs January through
March, nonprofit Single Audits and 990s pile onto a May 15 deadline,
employee-benefit-plan audits back up against the October 15 Form 5500
extension, and the rest of the year is planning, interim testing, and
the peer-review cycle.
"""

from collections.abc import Mapping
from datetime import date

from workbench.simulation.director import ClientProfile

CLIENT_PROFILES: tuple[ClientProfile, ...] = (
    ClientProfile(
        entity="harriet-vance",
        rate_millis=520,
        situations=(
            ("The board wants the audit timeline before the March meeting.", "audit"),
            ("Our controller found a reconciling item in the grant ledger.", "audit"),
            ("The bank is asking when the audited statements will be issued.", "audit"),
            ("A restricted-donation classification is being questioned.", "audit"),
        ),
    ),
    ClientProfile(
        entity="desmond-blakely",
        rate_millis=470,
        situations=(
            ("Our federal expenditures crossed the Single Audit threshold.", "audit"),
            ("A subrecipient's documentation is thinner than we expected.", "audit"),
            ("The program officer wants the schedule of expenditures early.", "audit"),
        ),
    ),
    ClientProfile(
        entity="nora-behrens",
        rate_millis=430,
        situations=(
            ("Our 401(k) census file has participants we cannot place.", "benefits"),
            ("The recordkeeper changed the plan year data mid-stream.", "benefits"),
            ("We need the plan audit done before the 5500 extension runs.", "benefits"),
        ),
    ),
    ClientProfile(
        entity="idris-mensah",
        rate_millis=400,
        situations=(
            ("Percentage-of-completion on two jobs looks off to me.", "audit"),
            ("The surety wants reviewed statements sooner this year.", "audit"),
            ("A change order was booked in the wrong period.", "audit"),
        ),
    ),
    ClientProfile(
        entity="priya-raman",
        rate_millis=380,
        situations=(
            (
                "Our revenue recognition on multi-year licenses needs a look.",
                "advisory",
            ),
            ("Due diligence for the raise starts next month.", "advisory"),
            ("The investors asked for a quality-of-earnings summary.", "advisory"),
        ),
    ),
    ClientProfile(
        entity="tomas-lindgren",
        rate_millis=360,
        situations=(
            (
                "Inventory count date needs to move — the warehouse is mid-move.",
                "audit",
            ),
            ("Our cutoff testing last year raised a comment we want closed.", "audit"),
        ),
    ),
    ClientProfile(
        entity="adaeze-okonkwo",
        rate_millis=340,
        situations=(
            ("The clinic's payor mix changed and receivables aged badly.", "audit"),
            ("We need help with the cost report before the deadline.", "advisory"),
        ),
    ),
    ClientProfile(
        entity="benedict-shaw",
        rate_millis=300,
        situations=(
            (
                "Our peer reviewer asked about your independence documentation.",
                "quality",
            ),
            ("The engagement letter needs updating for the new scope.", "quality"),
        ),
    ),
    ClientProfile(
        entity="lucia-arroyo",
        rate_millis=280,
        situations=(
            ("Our internal controls memo from last year needs refreshing.", "audit"),
            ("A new location opened and nobody told accounting.", "audit"),
        ),
    ),
    ClientProfile(
        entity="garrett-poole",
        rate_millis=240,
        situations=(
            ("The trustees want an interim report before year end.", "audit"),
            ("Our investment statements arrived late again.", "audit"),
        ),
    ),
)

_FIELDWORK_CLIENTS = (
    "harriet-vance",
    "idris-mensah",
    "tomas-lindgren",
    "lucia-arroyo",
)
_SINGLE_AUDIT_CLIENTS = ("harriet-vance", "desmond-blakely")
_BENEFIT_PLAN_CLIENTS = ("nora-behrens",)


def season_multipliers(day: str) -> Mapping[str, int]:
    """Per-client cue multipliers in thousandths (1000 = unchanged).

    Three peaks rather than Calder's one: calendar-year fieldwork,
    the May 15 nonprofit deadline, and the autumn 5500 crunch.
    """

    when = date.fromisoformat(day)
    multipliers: dict[str, int] = {}

    # Fieldwork season: January through mid-March, tightest in February.
    if when.month in (1, 2, 3):
        peak = 2200 if when.month == 2 else 1600
        for entity in _FIELDWORK_CLIENTS:
            multipliers[entity] = peak

    # Nonprofit Single Audit and Form 990 both land on May 15.
    if (when.month == 4) or (when.month == 5 and when.day <= 15):
        for entity in _SINGLE_AUDIT_CLIENTS:
            multipliers[entity] = 2400 if when.month == 5 else 1700

    # Benefit-plan audits back up against the October 15 5500 extension.
    if when.month in (8, 9) or (when.month == 10 and when.day <= 15):
        for entity in _BENEFIT_PLAN_CLIENTS:
            multipliers[entity] = 2600 if when.month == 10 else 1800

    # Quarter ends stir everyone a little; audit clients still close books.
    if when.month in (1, 4, 7, 10) and when.day <= 10:
        for profile in CLIENT_PROFILES:
            multipliers.setdefault(profile.entity, 1300)

    return multipliers
