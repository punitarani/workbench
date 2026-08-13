"""The Calder & Finch, CPAs cast: sixteen employees at genesis, one staff
accountant who joins mid-window, ten client organizations, and the outside
world the firm corresponds with.

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
        email_address=f"{local}@calderfinch.example",
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
        "per-rosalind-calder",
        "Rosalind Calder",
        "Managing Partner",
        "Tax",
        None,
    ),
    _employee(
        "per-elias-finch",
        "Elias Finch",
        "Partner, Client Accounting & Advisory",
        "Advisory",
        None,
    ),
    _employee(
        "per-hana-sato",
        "Hana Sato",
        "Principal, Assurance",
        "Assurance",
        None,
    ),
    _employee(
        "per-victor-alade",
        "Victor Alade",
        "Tax Manager",
        "Tax",
        "per-rosalind-calder",
    ),
    _employee(
        "per-imogen-carraway",
        "Imogen Carraway",
        "Audit Manager",
        "Assurance",
        "per-hana-sato",
    ),
    _employee(
        "per-desmond-ortiz",
        "Desmond Ortiz",
        "Senior Accountant, Tax",
        "Tax",
        "per-victor-alade",
    ),
    _employee(
        "per-lucia-mendes",
        "Lucia Mendes",
        "Senior Accountant, Tax",
        "Tax",
        "per-victor-alade",
    ),
    _employee(
        "per-theo-brandt",
        "Theo Brandt",
        "Senior Accountant, Assurance",
        "Assurance",
        "per-imogen-carraway",
    ),
    _employee(
        "per-nadia-osman",
        "Nadia Osman",
        "Staff Accountant",
        "Tax",
        "per-victor-alade",
    ),
    _employee(
        "per-colin-mackey",
        "Colin Mackey",
        "Staff Accountant",
        "Tax",
        "per-victor-alade",
    ),
    _employee(
        "per-priscilla-wong",
        "Priscilla Wong",
        "Staff Accountant",
        "Assurance",
        "per-imogen-carraway",
    ),
    _employee(
        "per-gabriel-fontes",
        "Gabriel Fontes",
        "Client Accounting Lead",
        "Advisory",
        "per-elias-finch",
    ),
    _employee(
        "per-sylvia-nakamura",
        "Sylvia Nakamura",
        "Payroll Specialist",
        "Advisory",
        "per-gabriel-fontes",
    ),
    _employee(
        "per-owen-castile",
        "Owen Castile",
        "Office & Billing Manager",
        "Operations",
        "per-rosalind-calder",
    ),
    _employee(
        "per-freya-holt",
        "Freya Holt",
        "Admin Coordinator",
        "Operations",
        "per-owen-castile",
    ),
    _employee(
        "per-raj-malhotra",
        "Raj Malhotra",
        "IT Administrator",
        "Operations",
        "per-owen-castile",
    ),
)

# Maya joins the tax group on 2026-03-02: her person.record is emitted by
# the arrival arc, not genesis, and the procedural cast swaps to include
# her from that date.
ARRIVAL_DATE = "2026-03-02"
ARRIVAL = _employee(
    "per-maya-lindqvist",
    "Maya Lindqvist",
    "Staff Accountant",
    "Tax",
    "per-victor-alade",
)

# Fee earners: everyone who logs billable time to an engagement. Maya
# appears here because she is a timekeeper from her arrival onward; the
# genesis cast simply starts without her.
TIMEKEEPER_IDS: tuple[str, ...] = (
    "per-rosalind-calder",
    "per-elias-finch",
    "per-hana-sato",
    "per-victor-alade",
    "per-imogen-carraway",
    "per-desmond-ortiz",
    "per-lucia-mendes",
    "per-theo-brandt",
    "per-nadia-osman",
    "per-colin-mackey",
    "per-priscilla-wong",
    "per-gabriel-fontes",
    "per-sylvia-nakamura",
    "per-maya-lindqvist",
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
    _org(1, "Kestrel Manufacturing", "client"),
    _org(2, "Blue Fir Restaurant Group", "client"),
    _org(3, "Riverbend Dental Studio", "client"),
    _org(4, "Harbor Light Foundation", "client"),
    _org(5, "Stonebridge Property Group", "client"),
    _org(6, "Cardinal Ridge Builders", "client"),
    _org(7, "Loop & Ladder Software", "client"),
    _org(8, "Juniper & Main Retail", "client"),
    _org(9, "Alder Creek Brewing", "client"),
    _org(10, "Summit Physical Therapy", "client"),
)

OTHER_ORGS: tuple[OrganizationRecordPayload, ...] = (
    _org(11, "Oregon Department of Revenue", "other"),
    _org(12, "Cascade Fidelity Bank", "vendor"),
    _org(13, "TrialWorks Practice Software", "vendor"),
)

ORGS: tuple[OrganizationRecordPayload, ...] = (*CLIENT_ORGS, *OTHER_ORGS)


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


_ODR, _BANK, _SOFTWARE = OTHER_ORGS

EXTERNALS: tuple[PersonRecordPayload, ...] = (
    # Client-side contacts, one per organization, in client-org order.
    _external(
        "per-dana-whitfield",
        "Dana Whitfield",
        "Controller",
        CLIENT_ORGS[0],
        "kestrelmfg.example",
    ),
    _external(
        "per-marco-petrosyan",
        "Marco Petrosyan",
        "Owner",
        CLIENT_ORGS[1],
        "bluefirgroup.example",
    ),
    _external(
        "per-alice-kwon",
        "Alice Kwon",
        "Practice Manager",
        CLIENT_ORGS[2],
        "riverbenddental.example",
    ),
    _external(
        "per-naomi-castellanos",
        "Naomi Castellanos",
        "Executive Director",
        CLIENT_ORGS[3],
        "harborlightfdn.example",
    ),
    _external(
        "per-evan-doyle",
        "Evan Doyle",
        "Chief Financial Officer",
        CLIENT_ORGS[4],
        "stonebridgepg.example",
    ),
    _external(
        "per-frank-osei",
        "Frank Osei",
        "Owner",
        CLIENT_ORGS[5],
        "cardinalridge.example",
    ),
    _external(
        "per-sana-qureshi",
        "Sana Qureshi",
        "Founder & CEO",
        CLIENT_ORGS[6],
        "loopandladder.example",
    ),
    _external(
        "per-margot-ellison",
        "Margot Ellison",
        "Operations Director",
        CLIENT_ORGS[7],
        "junipermain.example",
    ),
    _external(
        "per-reuben-tate",
        "Reuben Tate",
        "General Manager",
        CLIENT_ORGS[8],
        "aldercreekbrewing.example",
    ),
    _external(
        "per-gloria-nunez",
        "Gloria Nunez",
        "Office Manager",
        CLIENT_ORGS[9],
        "summitpt.example",
    ),
    # Agency, bank, and vendor contacts.
    _external(
        "per-denise-archer",
        "Denise Archer",
        "Revenue Agent",
        _ODR,
        "dor.oregon.example",
    ),
    _external(
        "per-hugh-bramwell",
        "Hugh Bramwell",
        "Relationship Manager",
        _BANK,
        "cascadefidelity.example",
    ),
    _external(
        "per-katya-lebedeva",
        "Katya Lebedeva",
        "Support Lead",
        _SOFTWARE,
        "trialworks.example",
        timezone="America/Chicago",
    ),
)
