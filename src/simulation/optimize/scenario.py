"""The optimization half-day and its mechanical scorecard.

Targets the weaknesses the recorded legal day exposed: personas never chose
chat, and courtesy acknowledgments crept into email. Two beats — an
external email that deserves one substantive on-thread reply with a stated
turnaround, and an internal request to post a status update in chat, where
replying by email instead is exactly the anti-pattern. Every check is
mechanical over the world log; an invalid log scores zero.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from core.events import Event
from core.worldlog import validate_events
from simulation.gm.grounded import TicketVocabulary
from simulation.persona.params import (
    ChannelStyle,
    ProfessionalWorkerParams,
)
from simulation.workplace.spec import (
    ChannelSpec,
    ExogenousEmail,
    PersonSpec,
    SeedDocument,
    WorkplaceSpec,
)

ANN = "per-ann-liu"
RAVI = "per-ravi-dee"
OMAR = "per-omar-diaz"

WEIGHTS = {
    "reply_on_thread": 0.25,
    "turnaround_stated": 0.05,
    "chat_status": 0.30,
    "revision_delivered": 0.20,
    "channel_discipline": 0.20,
}

_DONE_CLAIMS = ("fixed", "corrected", "updated the", "revised", "redlined", "done")

# Scenario nouns that must never appear in a proposed instruction: an
# instruction that quotes the evaluation day is reward hacking.
BANNED_INSTRUCTION_TERMS = (
    "forty-five",
    "thirty",
    "sow",
    "#general",
    "ravi",
    "omar",
    "payment",
    "data services",
)

_TURNAROUND_MARKERS = (
    "today",
    "tomorrow",
    "end of day",
    "eod",
    "by ",
    "within",
    "friday",
)


def ann_persona() -> ProfessionalWorkerParams:
    return ProfessionalWorkerParams(
        person_id=ANN,
        name="Ann Liu",
        title="Counsel",
        seniority="mid",
        role_description=(
            "Reviews commercial agreements; keeps the team informed on review status."
        ),
        personality="Organized, concise, keeps commitments.",
        channel_style=ChannelStyle(
            email_register="Professional and brief; signs 'Best, Ann'.",
            chat_register="Short, informal, first person.",
            quirks="",
        ),
        working_hours="09:00-17:30",
        manager=None,
    )


def optimization_spec() -> WorkplaceSpec:
    return WorkplaceSpec(
        workplace_id="optim-day",
        display_name="Mini Co",
        timezone="UTC",
        epoch="2026-03-12T00:00:00+00:00",
        ticket_vocabulary=TicketVocabulary(
            statuses=("open", "closed"),
            priorities=("normal",),
            ticket_types=("general",),
        ),
        people=(
            PersonSpec(
                person_id=ANN,
                name="Ann Liu",
                email_address="ann@mini.example",
                title="Counsel",
                department="Legal",
                manager=None,
                affiliation="internal",
                persona=ann_persona(),
            ),
            PersonSpec(
                person_id=RAVI,
                name="Ravi Dee",
                email_address="ravi@outside.example",
                title="Outside Counsel",
                department="External",
                manager=None,
                affiliation="external",
                persona=None,
            ),
            PersonSpec(
                person_id=OMAR,
                name="Omar Diaz",
                email_address="omar@mini.example",
                title="Operations Lead",
                department="Operations",
                manager=None,
                affiliation="internal",
                persona=None,
            ),
        ),
        channels=(ChannelSpec(name="#general", members=(ANN, OMAR)),),
        seed_documents=(
            SeedDocument(
                author=ANN,
                title="Data Services SOW (working draft)",
                path="/legal/drafts/data-services-sow.md",
                content=(
                    "# Data Services SOW\n\nSection 3. Payment. Invoices are "
                    "due within thirty (30) days of receipt.\n"
                ),
            ),
        ),
        day_script=(
            ExogenousEmail(
                at="09:40",
                sender=RAVI,
                to=(ANN,),
                cc=(),
                subject="Revised SOW — receipt and turnaround?",
                body=(
                    "Sending over the revised SOW for the data services "
                    "engagement. Can you confirm you have it and give me an "
                    "expected turnaround for your review? Also, per our call, "
                    "section 3 of your working draft should say forty-five "
                    "(45) days, not thirty (30) — please make that correction "
                    "in the draft today."
                ),
            ),
            ExogenousEmail(
                at="11:00",
                sender=OMAR,
                to=(ANN,),
                cc=(),
                subject="SOW review visibility",
                body=(
                    "Heads-up: leadership is watching the SOW review. Make "
                    "sure the team knows where it stands today."
                ),
            ),
            ExogenousEmail(
                at="11:45",
                sender=RAVI,
                to=(ANN,),
                cc=(),
                subject="Thanks!",
                body="Thanks — appreciated. Talk soon.",
            ),
        ),
        end_of_day="13:00",
    )


class ScoreCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    components: dict[str, float]
    findings: tuple[str, ...]

    @property
    def total(self) -> float:
        return round(sum(self.components.values()), 4)


def score_day(events: Sequence[Event]) -> ScoreCard:
    report = validate_events(list(events))
    if not report.ok:
        return ScoreCard(
            components={name: 0.0 for name in WEIGHTS},
            findings=("world log failed validation",),
        )

    emails = [e for e in events if e.payload.kind == "email.message"]
    chats = [e for e in events if e.payload.kind == "chat.message"]
    ravi_thread = next(
        (e.payload.thread_id for e in emails if e.payload.sender == RAVI), None
    )
    bait_threads = {
        e.payload.thread_id
        for e in emails
        if e.payload.sender == RAVI and "thanks" in e.payload.subject.lower()
    }
    omar_thread = next(
        (e.payload.thread_id for e in emails if e.payload.sender == OMAR), None
    )
    general = next(
        (
            e.payload.conversation_id
            for e in events
            if e.payload.kind == "chat.conversation.created"
            and e.payload.name == "#general"
        ),
        None,
    )
    ann_emails = [e for e in emails if e.payload.sender == ANN]

    components: dict[str, float] = {}
    findings: list[str] = []

    replies = [
        e
        for e in ann_emails
        if e.payload.thread_id == ravi_thread and e.payload.in_reply_to is not None
    ]
    components["reply_on_thread"] = WEIGHTS["reply_on_thread"] if replies else 0.0
    if not replies:
        findings.append(
            "never replied on the external SOW thread; the sender's direct "
            "question went unanswered"
        )

    stated = any(
        marker in e.payload.body.lower()
        for e in replies
        for marker in _TURNAROUND_MARKERS
    )
    components["turnaround_stated"] = WEIGHTS["turnaround_stated"] if stated else 0.0
    if replies and not stated:
        findings.append(
            "the SOW reply gave no expected turnaround, though one was asked for"
        )

    status_posts = [
        e
        for e in chats
        if e.payload.sender == ANN
        and e.payload.conversation_id == general
        and len(e.payload.body.strip()) >= 20
    ]
    components["chat_status"] = WEIGHTS["chat_status"] if status_posts else 0.0
    if not status_posts:
        findings.append(
            "the team was never told where the review stands: internal "
            "status updates belong in the shared chat channel, not in "
            "private email"
        )

    revisions = [
        e
        for e in events
        if e.payload.kind == "document.revised"
        and e.payload.author == ANN
        and "forty-five" in e.payload.content.lower()
    ]
    components["revision_delivered"] = (
        WEIGHTS["revision_delivered"] if revisions else 0.0
    )
    if not revisions:
        findings.append(
            "the requested correction (forty-five day payment term) was "
            "never made in the repository draft; the work itself, not a "
            "message about it, is the deliverable"
        )

    discipline = 1.0
    claimed_done = any(
        claim in e.payload.body.lower()
        for e in (*ann_emails, *[c for c in chats if c.payload.sender == ANN])
        for claim in _DONE_CLAIMS
    )
    if claimed_done and not revisions:
        discipline -= 0.5
        findings.append(
            "claimed in a message that the correction was made, but no "
            "repository revision exists — announcing work is not doing it"
        )
    if any(
        e.payload.thread_id == omar_thread or e.payload.thread_id in bait_threads
        for e in ann_emails
    ):
        discipline -= 0.5
        findings.append(
            "answered an internal heads-up or a thank-you note by email — "
            "acknowledgment messages that needed no reply at all"
        )
    if len(status_posts) > 1:
        discipline -= 0.5
        findings.append(
            f"posted the same status update {len(status_posts)} times in "
            "chat; a status is given once and repeated only when it changes"
        )
    if len(ann_emails) > 2:
        discipline -= 0.25
        findings.append(
            f"sent {len(ann_emails)} emails in a half-day with one real "
            "thread; extra messages are noise"
        )
    components["channel_discipline"] = WEIGHTS["channel_discipline"] * max(
        discipline, 0.0
    )

    return ScoreCard(components=components, findings=tuple(findings))
