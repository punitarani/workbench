"""Merrick Stanton's year: a litigation-and-transactions calendar.

An accounting firm's year has one shape — a filing deadline everyone
converges on. A law firm has two clocks running at once and they are not
in phase.

The transactional clock is quarterly: deals converge on the last two
weeks of March and June because that is when funds, lenders and boards
want them, and the fortnight before a quarter close is the busiest
stretch a corporate group has.

The litigation clock belongs to the court, not the firm. Discovery
cutoffs and dispositive-motion deadlines land where a scheduling order
put them, which is why the litigation peaks here sit mid-quarter rather
than at its edge, and why they do not move when the deal calendar does.

Employment work follows neither: it spikes when something happens to a
client, and it has a genuine seasonal component only around the spring
reduction-in-force cycle and pre-academic-year policy work.

Rates are expected cues per workday in thousandths, and multipliers are
also thousandths (1000 = unchanged).
"""

from collections.abc import Mapping
from datetime import date

from simulation.director import ClientProfile

CLIENT_PROFILES: tuple[ClientProfile, ...] = (
    ClientProfile(
        entity="marguerite-oyelaran",
        rate_millis=540,
        situations=(
            (
                "The regulator has come back with a second request and a "
                "three-week clock.",
                "regulatory",
            ),
            (
                "Our board wants to know the realistic exposure before Thursday.",
                "regulatory",
            ),
            (
                "I need to know whether the covenant language was ever amended.",
                "advisory",
            ),
            (
                "We are over the budget I committed to. Walk me through why.",
                "billing",
            ),
        ),
    ),
    ClientProfile(
        entity="roland-pesch",
        rate_millis=470,
        situations=(
            (
                "One of our surgeons has resigned and is opening two miles away.",
                "employment",
            ),
            (
                "The plaintiff's counsel is pushing for a mediation date.",
                "litigation",
            ),
            (
                "Can we resolve this without an admission of anything?",
                "litigation",
            ),
        ),
    ),
    ClientProfile(
        entity="imelda-frost",
        rate_millis=520,
        situations=(
            (
                "Where are we on the elevator acquisition? Give me a date.",
                "transaction",
            ),
            ("The supplier is refusing delivery. Do we counterclaim?", "litigation"),
            ("Diligence has thrown up an environmental item. How bad?", "transaction"),
            ("I need the fee estimate updated before the board call.", "billing"),
        ),
    ),
    ClientProfile(
        entity="teodor-vasiliev",
        rate_millis=500,
        situations=(
            (
                "The collaboration partner is claiming joint ownership of the "
                "improvements.",
                "ip",
            ),
            (
                "Our clinical data sits in three jurisdictions and the investors "
                "have asked about it.",
                "regulatory",
            ),
            ("The disclosure schedule has a gap I cannot close.", "transaction"),
        ),
    ),
    ClientProfile(
        entity="saoirse-mulvaney",
        rate_millis=610,
        situations=(
            ("Are we closing this quarter or not?", "transaction"),
            ("Which of these diligence flags actually matter?", "transaction"),
            (
                "The management incentive mechanics do not work. Fix them.",
                "transaction",
            ),
            ("I want a call with the managing partner about staffing.", "advisory"),
        ),
    ),
    ClientProfile(
        entity="clement-abioye",
        rate_millis=480,
        situations=(
            (
                "The drivers have filed a collective action over meal breaks.",
                "employment",
            ),
            ("We need to reduce headcount by twelve percent. How?", "employment"),
            ("There is a complaint about a supervisor and I need help.", "employment"),
        ),
    ),
    ClientProfile(
        entity="yuki-tanabe",
        rate_millis=430,
        situations=(
            ("The insurer is reserving rights on the recall. Read this.", "litigation"),
            ("Supplier renewals are due and the terms have moved.", "transaction"),
            ("We have been opposed in two trademark applications.", "ip"),
        ),
    ),
    ClientProfile(
        entity="priyanka-deshmukh",
        rate_millis=560,
        situations=(
            (
                "Our former engineering lead has taken the control-loop work with him.",
                "ip",
            ),
            ("The OEM will not move off an uncapped indemnity. Options?", "ip"),
            ("Are the patent filings going to make the deadline?", "ip"),
        ),
    ),
    ClientProfile(
        entity="desmond-achebe",
        rate_millis=390,
        situations=(
            ("We are reserving on this claim. Give me your assessment.", "litigation"),
            ("Your invoice does not comply with the panel guidelines.", "billing"),
            ("Has anything changed that affects the reserve?", "litigation"),
        ),
    ),
    ClientProfile(
        entity="harriet-lindqvist",
        rate_millis=360,
        situations=(
            (
                "A staff member has raised a complaint and I need guidance.",
                "employment",
            ),
            ("The handbook needs updating before the year starts.", "employment"),
            ("What does the board have to be told, and when?", "advisory"),
        ),
    ),
)

# Who moves with which clock. A client can sit on more than one.
_TRANSACTIONAL = ("imelda-frost", "saoirse-mulvaney", "teodor-vasiliev", "yuki-tanabe")
_LITIGATION = (
    "marguerite-oyelaran",
    "roland-pesch",
    "desmond-achebe",
    "priyanka-deshmukh",
)
_EMPLOYMENT = ("clement-abioye", "harriet-lindqvist", "roland-pesch")


def season_multipliers(day: str) -> Mapping[str, int]:
    """Per-client cue multipliers in thousandths (1000 = unchanged)."""

    when = date.fromisoformat(day)
    multipliers: dict[str, int] = {}

    # The transactional clock. Deals converge on a quarter close, and the
    # fortnight before it is the corporate group's whole year in miniature.
    quarter_end_month = when.month in (3, 6, 9, 12)
    if quarter_end_month and when.day >= 17:
        for entity in _TRANSACTIONAL:
            multipliers[entity] = 2500
    elif quarter_end_month:
        for entity in _TRANSACTIONAL:
            multipliers[entity] = 1500
    # The week after a close is the quietest the corporate group gets.
    elif when.month in (1, 4, 7, 10) and when.day <= 7:
        for entity in _TRANSACTIONAL:
            multipliers[entity] = 700

    # The litigation clock belongs to the court. These are the mid-quarter
    # stretches the scheduling orders in this window actually put the
    # discovery cutoffs and dispositive-motion deadlines on, which is why
    # they do not line up with the quarter ends above.
    if (when.month == 2 and when.day >= 10) or (when.month == 3 and when.day <= 6):
        for entity in _LITIGATION:
            multipliers[entity] = 2200
    if (when.month == 5 and when.day >= 4) or (when.month == 6 and when.day <= 12):
        for entity in _LITIGATION:
            multipliers[entity] = 2000

    # Employment: the spring reduction-in-force cycle, then policy work
    # ahead of the academic and fiscal year.
    if when.month in (3, 4):
        for entity in _EMPLOYMENT:
            multipliers[entity] = 1700
    if when.month in (6, 7):
        for entity in _EMPLOYMENT:
            multipliers[entity] = max(multipliers.get(entity, 0), 1400)

    return multipliers


__all__ = ["CLIENT_PROFILES", "season_multipliers"]
