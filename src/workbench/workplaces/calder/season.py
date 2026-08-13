"""The accounting calendar as cue-rate multipliers and situations.

Pure data plus one pure function: given an ISO date, how stirred is each
client (in thousandths, 1000 = baseline)? Filing season swells the tax
clients, month-end swells the close clients, estimate deadlines prod the
estimate payers, and January wakes everyone who receives a 1099.
"""

from collections.abc import Mapping
from datetime import date

from workbench.simulation.director.schedule import ClientProfile

# Baseline cue rates (expected inbound per workday, thousandths).
CLIENT_PROFILES: tuple[ClientProfile, ...] = (
    ClientProfile(
        entity="dana-whitfield",
        rate_millis=500,
        situations=(
            ("The monthly close package raised a question about a line item.", "close"),
            ("The board wants a margin number explained before Thursday.", "close"),
            ("A new equipment purchase needs the right depreciation answer.", "tax"),
            ("The bank asked for interim statements for the line renewal.", "close"),
            ("Payroll added two people and withholding setup is unclear.", "payroll"),
        ),
    ),
    ClientProfile(
        entity="marco-petrosyan",
        rate_millis=450,
        situations=(
            ("A location manager reported a POS/deposit mismatch.", "close"),
            ("Tip reporting for the quarter looks off to him.", "payroll"),
            ("He is weighing a fourth location and wants a gut check.", "advisory"),
            ("A vendor invoice hit twice and he wants it found.", "close"),
        ),
    ),
    ClientProfile(
        entity="evan-doyle",
        rate_millis=400,
        situations=(
            ("A lender wants the reporting package earlier this quarter.", "close"),
            ("A partner asked when the K-1s will land.", "tax"),
            ("A property sale is closing and the allocation matters.", "tax"),
            ("CAM reconciliation disputes are back for one tenant.", "close"),
        ),
    ),
    ClientProfile(
        entity="reuben-tate",
        rate_millis=350,
        situations=(
            ("Keg deposit liability doesn't match his own tally.", "close"),
            ("The excise filing deadline is close and he lost a form.", "tax"),
            ("Margins by channel came out strange last month.", "close"),
        ),
    ),
    ClientProfile(
        entity="alice-kwon",
        rate_millis=250,
        situations=(
            ("She found another shoebox of uncategorized receipts.", "bookkeeping"),
            ("The practice software migration scrambled an export.", "bookkeeping"),
            ("An associate dentist buy-in question came up.", "advisory"),
        ),
    ),
    ClientProfile(
        entity="frank-osei",
        rate_millis=300,
        situations=(
            ("A job closed way under margin and he wants to know why.", "advisory"),
            ("Retention on a big contract is due and cash is tight.", "tax"),
            ("His bonding company wants fresh financials.", "close"),
        ),
    ),
    ClientProfile(
        entity="sana-qureshi",
        rate_millis=250,
        situations=(
            ("Investors asked about the R&D credit in diligence.", "advisory"),
            ("A new revenue contract has an unusual billing shape.", "advisory"),
            ("She wants the estimated payment double-checked.", "tax"),
        ),
    ),
    ClientProfile(
        entity="margot-ellison",
        rate_millis=200,
        situations=(
            ("Inventory shrink at one store looks wrong in the books.", "bookkeeping"),
            ("She is comparing payroll providers and wants advice.", "payroll"),
        ),
    ),
    ClientProfile(
        entity="gloria-nunez",
        rate_millis=250,
        situations=(
            ("A partner wants their draw restructured.", "tax"),
            ("An insurer's audit letter needs a financial answer.", "close"),
            ("The estimated payment voucher never arrived, she says.", "tax"),
        ),
    ),
    ClientProfile(
        entity="naomi-castellanos",
        rate_millis=250,
        situations=(
            ("A grantor requested an audited-statement excerpt.", "audit"),
            ("The board treasurer challenged a restriction release.", "audit"),
            ("A new grant has odd reporting conditions.", "advisory"),
        ),
    ),
    ClientProfile(
        entity="denise-archer",
        rate_millis=60,
        situations=(
            ("A withholding discrepancy notice is going out to a client.", "notice"),
            ("A filing needs clarification before processing.", "notice"),
        ),
    ),
)

_TAX_CLIENTS = (
    "dana-whitfield",
    "evan-doyle",
    "frank-osei",
    "gloria-nunez",
    "sana-qureshi",
)
_CLOSE_CLIENTS = (
    "dana-whitfield",
    "marco-petrosyan",
    "evan-doyle",
    "reuben-tate",
)
_ESTIMATE_CLIENTS = ("sana-qureshi", "frank-osei", "gloria-nunez")


def season_multipliers(day: str) -> Mapping[str, int]:
    """Cue-rate multipliers (thousandths) for one calendar day."""

    current = date.fromisoformat(day)
    multipliers: dict[str, int] = {}

    def boost(entities: tuple[str, ...], factor: int) -> None:
        for entity in entities:
            multipliers[entity] = max(multipliers.get(entity, 1000), factor)

    # Month-end close window: the 25th through the 7th.
    if current.day >= 25 or current.day <= 7:
        boost(_CLOSE_CLIENTS, 1700)
    # Filing season, swelling toward the deadline.
    if date(current.year, 2, 1) <= current <= date(current.year, 4, 15):
        boost(_TAX_CLIENTS, 1600)
        if current >= date(current.year, 4, 8):
            boost(_TAX_CLIENTS, 2500)
            boost(("denise-archer",), 1500)
    # Quarterly estimates: the week before Jan 15, Apr 15, Jun 15, Sep 15.
    for month, deadline in ((1, 15), (4, 15), (6, 15), (9, 15)):
        due = date(current.year, month, deadline)
        if 0 <= (due - current).days <= 7:
            boost(_ESTIMATE_CLIENTS, 1500)
    # January: 1099s and year-end questions stir everyone a little.
    if current.month == 1:
        for profile in CLIENT_PROFILES:
            multipliers.setdefault(profile.entity, 1200)
    return multipliers
