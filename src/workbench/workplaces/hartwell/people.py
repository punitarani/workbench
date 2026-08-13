"""The Hartwell & Marsh LLP cast: twelve employees, twelve client
organizations, and the outside world the firm corresponds with.

Person ids are stable slugs; organization ids use the minted ``org-NNNNNN``
form in declaration order, and genesis re-mints them from its single
IdMinter to prove the declared ids and the counter state agree.
"""

from typing import Literal

from workbench.core.events.people import (
    OrganizationRecordPayload,
    PersonRecordPayload,
)

_TZ = "America/Los_Angeles"


def _employee(
    person_id: str,
    name: str,
    title: str,
    department: str,
    manager: str | None,
) -> PersonRecordPayload:
    local = name.lower().replace(" ", ".")
    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{local}@hartwellmarsh.example",
        title=title,
        department=department,
        manager=manager,
        affiliation="internal",
        timezone=_TZ,
        organization=None,
    )


# Declaration order is genesis order: managers precede their reports.
EMPLOYEES: tuple[PersonRecordPayload, ...] = (
    _employee(
        "per-eleanor-hartwell",
        "Eleanor Hartwell",
        "Managing Partner",
        "Corporate",
        None,
    ),
    _employee("per-samuel-marsh", "Samuel Marsh", "Partner", "Litigation", None),
    _employee(
        "per-diane-okonkwo",
        "Diane Okonkwo",
        "Of Counsel",
        "Real Estate",
        "per-eleanor-hartwell",
    ),
    _employee(
        "per-marcus-liang",
        "Marcus Liang",
        "Senior Associate",
        "Corporate",
        "per-eleanor-hartwell",
    ),
    _employee(
        "per-sofia-ramirez",
        "Sofia Ramirez",
        "Associate",
        "Litigation",
        "per-samuel-marsh",
    ),
    _employee(
        "per-noah-feldstein",
        "Noah Feldstein",
        "Associate",
        "Real Estate",
        "per-diane-okonkwo",
    ),
    _employee(
        "per-grace-adeyemi",
        "Grace Adeyemi",
        "Senior Paralegal",
        "Litigation",
        "per-samuel-marsh",
    ),
    _employee(
        "per-peter-novak",
        "Peter Novak",
        "Paralegal",
        "Corporate",
        "per-eleanor-hartwell",
    ),
    _employee(
        "per-anita-bailey",
        "Anita Bailey",
        "Operations Manager",
        "Operations",
        "per-eleanor-hartwell",
    ),
    _employee(
        "per-carl-jensen",
        "Carl Jensen",
        "Billing Coordinator",
        "Operations",
        "per-anita-bailey",
    ),
    _employee(
        "per-tessa-nguyen",
        "Tessa Nguyen",
        "IT & Facilities Administrator",
        "Operations",
        "per-anita-bailey",
    ),
    _employee(
        "per-omar-haddad",
        "Omar Haddad",
        "Records Clerk",
        "Operations",
        "per-anita-bailey",
    ),
)

# Attorneys and paralegals: the people who log billable time.
TIMEKEEPER_IDS: tuple[str, ...] = (
    "per-eleanor-hartwell",
    "per-samuel-marsh",
    "per-diane-okonkwo",
    "per-marcus-liang",
    "per-sofia-ramirez",
    "per-noah-feldstein",
    "per-grace-adeyemi",
    "per-peter-novak",
)


def _org(
    number: int,
    name: str,
    category: Literal["client", "vendor", "court", "opposing", "other"],
) -> OrganizationRecordPayload:
    return OrganizationRecordPayload(
        kind="org.record",
        org_id=f"org-{number:06d}",
        name=name,
        category=category,
    )


CLIENT_ORGS: tuple[OrganizationRecordPayload, ...] = (
    _org(1, "Meridian BioLabs", "client"),
    _org(2, "Cascadia Outfitters", "client"),
    _org(3, "Veridian Energy Cooperative", "client"),
    _org(4, "Brightline Logistics", "client"),
    _org(5, "Solstice Vineyards", "client"),
    _org(6, "Northgate Medical Group", "client"),
    _org(7, "Pelican Bay Marina", "client"),
    _org(8, "Arroyo Construction", "client"),
    _org(9, "Lumen Software", "client"),
    _org(10, "Goldleaf Hospitality Group", "client"),
    _org(11, "Tidewater Imports", "client"),
    _org(12, "Redwood Family Trust", "client"),
)

OPPOSING_ORGS: tuple[OrganizationRecordPayload, ...] = (
    _org(13, "Crane & Whitaker LLP", "opposing"),
    _org(14, "Strauss Denning LLP", "opposing"),
    _org(15, "Pacific Counsel Group", "opposing"),
)

VENDOR_ORGS: tuple[OrganizationRecordPayload, ...] = (
    _org(16, "LexiPoint Research", "vendor"),
    _org(17, "Ironclad Discovery Services", "vendor"),
    _org(18, "BayMark IT Solutions", "vendor"),
)

COURT_ORGS: tuple[OrganizationRecordPayload, ...] = (
    _org(19, "Alameda County Superior Court", "court"),
    _org(20, "U.S. District Court, N.D. Cal.", "court"),
)

ORGS: tuple[OrganizationRecordPayload, ...] = (
    *CLIENT_ORGS,
    *OPPOSING_ORGS,
    *VENDOR_ORGS,
    *COURT_ORGS,
)


def _external(
    person_id: str,
    name: str,
    title: str,
    organization: OrganizationRecordPayload,
    domain: str,
    timezone: str = _TZ,
) -> PersonRecordPayload:
    local = name.lower().replace(" ", ".")
    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{local}@{domain}",
        title=title,
        department=organization.name,
        manager=None,
        affiliation="external",
        timezone=timezone,
        organization=organization.org_id,
    )


_CRANE, _STRAUSS, _PACIFIC = OPPOSING_ORGS
_LEXIPOINT, _IRONCLAD, _BAYMARK = VENDOR_ORGS
_ALAMEDA, _NDCAL = COURT_ORGS

EXTERNALS: tuple[PersonRecordPayload, ...] = (
    # Opposing counsel.
    _external(
        "per-victor-crane", "Victor Crane", "Partner", _CRANE, "cranewhitaker.example"
    ),
    _external(
        "per-ingrid-sorensen",
        "Ingrid Sorensen",
        "Senior Associate",
        _CRANE,
        "cranewhitaker.example",
    ),
    _external(
        "per-derek-strauss",
        "Derek Strauss",
        "Partner",
        _STRAUSS,
        "straussdenning.example",
    ),
    _external(
        "per-mia-denning",
        "Mia Denning",
        "Associate",
        _STRAUSS,
        "straussdenning.example",
    ),
    _external(
        "per-caleb-fontaine",
        "Caleb Fontaine",
        "Partner",
        _PACIFIC,
        "pacificcounsel.example",
    ),
    _external(
        "per-yuki-tanaka",
        "Yuki Tanaka",
        "Of Counsel",
        _PACIFIC,
        "pacificcounsel.example",
    ),
    # Vendor contacts.
    _external(
        "per-ruth-calloway",
        "Ruth Calloway",
        "Account Manager",
        _LEXIPOINT,
        "lexipoint.example",
        timezone="America/New_York",
    ),
    _external(
        "per-stan-obrien",
        "Stan Obrien",
        "Project Manager",
        _IRONCLAD,
        "ironcladdiscovery.example",
    ),
    _external(
        "per-felix-mora",
        "Felix Mora",
        "Support Engineer",
        _BAYMARK,
        "baymarkit.example",
    ),
    # Court clerks.
    _external(
        "per-dawn-mcallister",
        "Dawn McAllister",
        "Courtroom Clerk",
        _ALAMEDA,
        "alameda.courts.example",
    ),
    _external(
        "per-hector-ruiz",
        "Hector Ruiz",
        "Deputy Clerk",
        _NDCAL,
        "cand.uscourts.example",
    ),
    # Client-side individuals.
    _external(
        "per-priya-raman",
        "Priya Raman",
        "Chief Operating Officer",
        CLIENT_ORGS[0],
        "meridianbiolabs.example",
    ),
    _external(
        "per-tom-hollis",
        "Tom Hollis",
        "Owner",
        CLIENT_ORGS[1],
        "cascadiaoutfitters.example",
    ),
    _external(
        "per-june-akana",
        "June Akana",
        "General Counsel",
        CLIENT_ORGS[8],
        "lumensoftware.example",
    ),
    _external(
        "per-olivia-chen",
        "Olivia Chen",
        "General Counsel",
        CLIENT_ORGS[9],
        "goldleafhospitality.example",
    ),
)
