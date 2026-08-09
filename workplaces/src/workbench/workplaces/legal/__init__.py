"""The Argent Systems legal department: the Phase 1 demonstration workplace.

The unwritten vendor-NDA standard lives only in Daniel's head (persona
knowledge, share_policy if_asked). The litmus phrases below must never
appear in any seeded document or day-script body — the acceptance suite
proves the knowledge flowed person -> conversation -> artifact during the
simulated day, not from the seeds.
"""

from datetime import datetime
from importlib import resources
from zoneinfo import ZoneInfo

from workbench.simulation.gm.grounded import TicketVocabulary
from workbench.simulation.workplace.spec import (
    ChannelSpec,
    ExogenousEmail,
    SeedCalendarEvent,
    SeedDocument,
    WorkplaceSpec,
)
from workbench.workplaces.legal.people import CAST

UNWRITTEN_STANDARD_PHRASES = ("two-year term cap", "redlined on sight")


def _doc(name: str) -> str:
    return (
        resources.files("workbench.workplaces.legal")
        .joinpath("seed_docs", name)
        .read_text(encoding="utf-8")
    )


_LEGAL_TEAM = (
    "per-meredith-chao",
    "per-daniel-reyes",
    "per-priya-nair",
    "per-tom-okafor",
)

WORKPLACE = WorkplaceSpec(
    workplace_id="argent-legal",
    display_name="Argent Systems — Legal",
    timezone="America/Los_Angeles",
    epoch=datetime(2026, 3, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
    ticket_vocabulary=TicketVocabulary(
        statuses=("open", "in-review", "blocked", "closed"),
        priorities=("low", "normal", "high", "urgent"),
        ticket_types=("nda-review", "contract-review", "question", "general"),
    ),
    people=CAST,
    channels=(
        ChannelSpec(name="#legal", members=_LEGAL_TEAM),
        ChannelSpec(
            name="#deals",
            members=("per-jess-alvarez", "per-meredith-chao", "per-daniel-reyes"),
        ),
    ),
    seed_documents=(
        SeedDocument(
            author="per-daniel-reyes",
            title="NDA Review Playbook — Customer Agreements",
            path="/legal/playbooks/nda-playbook.md",
            content=_doc("nda_playbook.md"),
        ),
        SeedDocument(
            author="per-daniel-reyes",
            title="Mutual NDA (Standard Form)",
            path="/legal/templates/nda-template.md",
            content=_doc("nda_template.md"),
        ),
        SeedDocument(
            author="per-daniel-reyes",
            title="Executed NDA — Acme Manufacturing",
            path="/legal/executed/precedent-nda-acme.md",
            content=_doc("precedent_nda_acme.md"),
        ),
        SeedDocument(
            author="per-priya-nair",
            title="Executed NDA — Northwind Logistics",
            path="/legal/executed/precedent-nda-northwind.md",
            content=_doc("precedent_nda_northwind.md"),
        ),
    ),
    seed_calendar=(
        SeedCalendarEvent(
            organizer="per-meredith-chao",
            title="Legal stand-up",
            start_clock="09:30",
            end_clock="09:45",
            attendees=_LEGAL_TEAM,
            description="Daily sync: intake, blockers, escalations.",
        ),
    ),
    day_script=(
        ExogenousEmail(
            at="09:40",
            sender="per-ravi-deshmukh",
            to=("per-tom-okafor",),
            cc=("per-jess-alvarez",),
            subject="Vantage Data Services — NDA for evaluation",
            body=(
                "Hello,\n\nAhead of the product evaluation Jess and our team "
                "discussed, please find our standard non-disclosure agreement "
                "attached. We would appreciate a signed copy this week so the "
                "pilot can begin on schedule.\n\nRegards,\nRavi Deshmukh\n"
                "Counsel, Vantage Data Services"
            ),
            attachment=SeedDocument(
                author="per-ravi-deshmukh",
                title="Vantage NDA (inbound draft)",
                path="/attachments/inbound-nda-vantage.md",
                content=_doc("inbound_nda_vantage.md"),
            ),
        ),
        ExogenousEmail(
            at="11:15",
            sender="per-jess-alvarez",
            to=("per-daniel-reyes",),
            cc=("per-tom-okafor",),
            subject="Vantage NDA — timing?",
            body=(
                "Hi Daniel!\n\nAny early read on the Vantage NDA Ravi sent "
                "over this morning? Their pilot pricing expires end of month "
                "so I'm trying to keep us moving.\n\nThanks!!\nJess"
            ),
        ),
    ),
    end_of_day="17:30",
)
