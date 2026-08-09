"""Genesis for Hartwell & Marsh LLP: the world as it stands on Monday
2026-03-02, before the four-month history begins.

Everything is data assembled into time-zero events. Every minted id comes
from one IdMinter; the statically declared org ids are re-minted against it
so the exported counter state is provably truthful.
"""

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
from workbench.core.seed import Seed
from workbench.simulation.chronicle.calendar import CalendarWindow
from workbench.simulation.chronicle.procedural import (
    CastMember,
    ChatChannel,
    OpenMatter,
    ProceduralCast,
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

WINDOW = CalendarWindow(
    start_date="2026-03-02", end_date="2026-06-30", timezone=TIMEZONE
)

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

    channels = {
        event.payload.name: event.payload
        for event in genesis.events
        if isinstance(event.payload, ChatConversationCreatedPayload)
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

    matters = tuple(
        OpenMatter(
            ticket_id=event.payload.ticket_id,
            label=event.payload.title,
            assignee=event.payload.assignee,
        )
        for event in genesis.events
        if isinstance(event.payload, TicketCreatedPayload)
        and event.payload.assignee is not None
    )
    return ProceduralCast(
        internal=tuple(member(person) for person in EMPLOYEES),
        timekeepers=tuple(
            CastMember(person_id=person_id, name=names[person_id])
            for person_id in TIMEKEEPER_IDS
        ),
        externals=tuple(member(person) for person in EXTERNALS),
        standup_channel=channel("#general").conversation_id,
        matters_channel=channel("#matters"),
        billing_channel=channel("#billing"),
        it_channel=channel("#it-help"),
        matters=matters,
    )
