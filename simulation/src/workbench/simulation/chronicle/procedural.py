"""Seeded background-traffic generators for procedural days.

One rng derived from the seed and the day's date drives every choice, and
ids come from the caller's minter in generation order, so the same inputs
always produce the same drafts byte for byte. Drafts reference only the
cast, channel, and matters they are given, which keeps a chronicle built
from them coherent by construction.
"""

import random

from pydantic import BaseModel, ConfigDict, Field, model_validator

from workbench.core.events.calendar import CalendarEventScheduledPayload
from workbench.core.events.chat import ChatMessagePayload, ChatReactionAddedPayload
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.tickets import TicketCommentedPayload
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.ids import IdMinter
from workbench.core.seed import Seed, derive_rng
from workbench.core.simtime import SimDuration, SimTime
from workbench.simulation.chronicle.builder import TimedDraft
from workbench.simulation.chronicle.calendar import CalendarWindow


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CastMember(_Model):
    person_id: str
    name: str

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    @property
    def entity(self) -> str:
        _, _, rest = self.person_id.partition("-")
        return rest or self.person_id


class OpenMatter(_Model):
    ticket_id: str
    label: str
    assignee: str


class ProceduralCast(_Model):
    """Who generates and receives background traffic, and against what."""

    internal: tuple[CastMember, ...] = Field(min_length=2)
    timekeepers: tuple[CastMember, ...] = Field(min_length=1)
    externals: tuple[CastMember, ...] = Field(min_length=1)
    standup_channel: str
    matters: tuple[OpenMatter, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _timekeepers_are_internal(self) -> ProceduralCast:
        internal_ids = {member.person_id for member in self.internal}
        strangers = [
            member.person_id
            for member in self.timekeepers
            if member.person_id not in internal_ids
        ]
        if strangers:
            raise ValueError(f"timekeepers are not internal cast: {strangers}")
        return self


_STANDUP_LINES = (
    "Morning all. Today: {focus}. No blockers.",
    "Standup: {focus} today, then catching up on email.",
    "In early — plan is {focus}. Ping me if anything urgent lands.",
    "Today: {focus}. Out for a filing run late afternoon.",
    "Picking up where I left off yesterday: {focus}.",
)

_STANDUP_FOCUS = (
    "drafting on {matter}",
    "document review for {matter}",
    "prep for the next deadline on {matter}",
    "revisions to the {matter} papers",
    "chasing signatures on {matter}",
    "a status call about {matter}",
)

_REACTION_EMOJI = ("thumbsup", "coffee", "tada", "eyes", "raised_hands")

_INTERNAL_EMAIL = (
    (
        "Timesheet reminder",
        "Hi {recipient},\n\nFriendly reminder to get last week's time in "
        "before the prebill run on Friday.\n\nThanks,\n{sender}",
    ),
    (
        "Conference room booking",
        "Hi {recipient},\n\nI have the large conference room blocked from "
        "2 to 4 tomorrow — let me know if that collides with anything on "
        "your calendar.\n\n{sender}",
    ),
    (
        "Third-floor copier",
        "Hi {recipient},\n\nThe third-floor copier is jamming again. Use "
        "the one by records until the service tech comes through.\n\n"
        "{sender}",
    ),
    (
        "Supply order going in Thursday",
        "Hi {recipient},\n\nPutting the monthly supply order in Thursday "
        "morning — send me anything you need before then.\n\n{sender}",
    ),
    (
        "Parking validations",
        "Hi {recipient},\n\nFresh parking validation books are at the front "
        "desk. Please log client visits in the sheet as usual.\n\n{sender}",
    ),
    (
        "Lunch for the team meeting",
        "Hi {recipient},\n\nOrdering sandwiches for the team meeting — "
        "reply with your pick by 10:30 or you get my choice.\n\n{sender}",
    ),
)

_INTERNAL_REPLY = (
    "Thanks {sender} — noted.",
    "Got it, thanks for the heads-up.",
    "Works for me, thanks.",
    "Thanks! Will do.",
)

_EXTERNAL_EMAIL = (
    (
        "Scheduling a call",
        "Hello {recipient},\n\nCould we find twenty minutes this week to "
        "speak about the open items on our side? Wednesday or Thursday "
        "afternoon works for us.\n\nRegards,\n{sender}",
    ),
    (
        "Document status",
        "Hello {recipient},\n\nChecking in on the outstanding documents we "
        "discussed. Please let us know where things stand when you have a "
        "moment.\n\nRegards,\n{sender}",
    ),
    (
        "Courtesy copy of correspondence",
        "Hello {recipient},\n\nFor your records, a courtesy note that our "
        "office sent the correspondence discussed last week. Happy to "
        "answer questions.\n\nRegards,\n{sender}",
    ),
    (
        "Availability next week",
        "Hello {recipient},\n\nOur side is available Monday and Tuesday "
        "next week should you wish to confer. Please advise what suits.\n\n"
        "Regards,\n{sender}",
    ),
)

_EXTERNAL_REPLY = (
    "Thank you — we will revert shortly.",
    "Received, thank you. I will come back to you this week.",
    "Thanks for the note; let me check internally and follow up.",
)

_TIME_NOTES = (
    "Draft and revise correspondence re {matter}.",
    "Review documents and update working file for {matter}.",
    "Telephone conference regarding {matter}.",
    "Legal research on open questions in {matter}.",
    "Prepare and organize exhibits for {matter}.",
    "Attention to case management and calendaring for {matter}.",
)

_TIME_MINUTES = (18, 30, 42, 60, 90, 120)

_MATTER_COMMENTS = (
    "Status: on track. Next touch scheduled for later this week.",
    "Waiting on the client for documents; follow-up sent.",
    "Draft circulated internally for comment.",
    "No movement from the other side today; will nudge tomorrow.",
    "Updated the working file; nothing needed from the team yet.",
)

_MEETING_TITLES = (
    "Weekly matter review",
    "Billing sync",
    "Staffing check-in",
    "Client call prep",
    "Docket review",
)

_MEETING_DESCRIPTIONS = (
    "Standing sync — agenda in the invite.",
    "Quick huddle, thirty minutes tops.",
    "Bring your open-items list.",
    "Conference room A unless noted otherwise.",
)

_MORNING = 9 * 3600


def _standups(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    drafts: list[TimedDraft],
) -> list[tuple[str, int]]:
    posted: list[tuple[str, int]] = []
    for member in cast.internal:
        if rng.random() >= 0.85:
            continue
        at = _MORNING + rng.randrange(0, 1200)
        matter = rng.choice(cast.matters)
        focus = rng.choice(_STANDUP_FOCUS).format(matter=matter.label)
        message_id = minter.mint("chm")
        drafts.append(
            TimedDraft(
                at=SimDuration(at),
                source=member.entity,
                payload=ChatMessagePayload(
                    kind="chat.message",
                    chat_message_id=message_id,
                    conversation_id=cast.standup_channel,
                    reply_to=None,
                    sender=member.person_id,
                    body=rng.choice(_STANDUP_LINES).format(focus=focus),
                ),
            )
        )
        posted.append((message_id, at))
    return posted


def _reactions(
    rng: random.Random,
    cast: ProceduralCast,
    posted: list[tuple[str, int]],
    drafts: list[TimedDraft],
) -> None:
    for message_id, at in posted:
        if rng.random() >= 0.35:
            continue
        reactor = rng.choice(cast.internal)
        drafts.append(
            TimedDraft(
                at=SimDuration(at + rng.randrange(120, 1800)),
                source=reactor.entity,
                payload=ChatReactionAddedPayload(
                    kind="chat.reaction.added",
                    conversation_id=cast.standup_channel,
                    chat_message_id=message_id,
                    person_id=reactor.person_id,
                    emoji=rng.choice(_REACTION_EMOJI),
                ),
            )
        )


def _email(
    *,
    at: int,
    minter: IdMinter,
    sender: CastMember,
    recipient: CastMember,
    subject: str,
    body: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
) -> tuple[TimedDraft, str, str]:
    message_id = minter.mint("msg")
    thread = thread_id if thread_id is not None else minter.mint("thr")
    draft = TimedDraft(
        at=SimDuration(at),
        source=sender.entity,
        payload=EmailMessagePayload(
            kind="email.message",
            message_id=message_id,
            thread_id=thread,
            in_reply_to=in_reply_to,
            sender=sender.person_id,
            to=(recipient.person_id,),
            subject=subject,
            body=body,
        ),
    )
    return draft, message_id, thread


def _internal_emails(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(rng.randrange(2, 5)):
        sender, recipient = rng.sample(list(cast.internal), 2)
        subject, template = rng.choice(_INTERNAL_EMAIL)
        at = rng.randrange(10 * 3600, 17 * 3600)
        draft, message_id, thread = _email(
            at=at,
            minter=minter,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=template.format(
                recipient=recipient.first_name, sender=sender.first_name
            ),
        )
        drafts.append(draft)
        if rng.random() < 0.5:
            reply, _, _ = _email(
                at=at + rng.randrange(600, 5400),
                minter=minter,
                sender=recipient,
                recipient=sender,
                subject=f"Re: {subject}",
                body=rng.choice(_INTERNAL_REPLY).format(sender=sender.first_name),
                thread_id=thread,
                in_reply_to=message_id,
            )
            drafts.append(reply)


def _external_emails(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(rng.randrange(1, 4)):
        sender = rng.choice(cast.externals)
        recipient = rng.choice(cast.timekeepers)
        subject, template = rng.choice(_EXTERNAL_EMAIL)
        at = rng.randrange(8 * 3600 + 1800, 16 * 3600)
        draft, message_id, thread = _email(
            at=at,
            minter=minter,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=template.format(recipient=recipient.first_name, sender=sender.name),
        )
        drafts.append(draft)
        if rng.random() < 0.4:
            reply, _, _ = _email(
                at=at + rng.randrange(1800, 7200),
                minter=minter,
                sender=recipient,
                recipient=sender,
                subject=f"Re: {subject}",
                body=rng.choice(_EXTERNAL_REPLY),
                thread_id=thread,
                in_reply_to=message_id,
            )
            drafts.append(reply)


def _time_entries(
    rng: random.Random,
    cast: ProceduralCast,
    drafts: list[TimedDraft],
) -> None:
    for keeper in cast.timekeepers:
        own = tuple(
            matter for matter in cast.matters if matter.assignee == keeper.person_id
        )
        pool = own if own else cast.matters
        for _ in range(rng.randrange(1, 4)):
            matter = rng.choice(pool)
            drafts.append(
                TimedDraft(
                    at=SimDuration(rng.randrange(15 * 3600, 18 * 3600 + 1800)),
                    source=keeper.entity,
                    payload=TimeLoggedPayload(
                        kind="work.time.logged",
                        person_id=keeper.person_id,
                        ticket_id=matter.ticket_id,
                        minutes=rng.choice(_TIME_MINUTES),
                        note=rng.choice(_TIME_NOTES).format(matter=matter.label),
                    ),
                )
            )


def _matter_comments(
    rng: random.Random,
    cast: ProceduralCast,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(rng.randrange(1, 4)):
        matter = rng.choice(cast.matters)
        entity = matter.assignee.partition("-")[2] or matter.assignee
        drafts.append(
            TimedDraft(
                at=SimDuration(rng.randrange(11 * 3600, 17 * 3600)),
                source=entity,
                payload=TicketCommentedPayload(
                    kind="ticket.commented",
                    ticket_id=matter.ticket_id,
                    actor=matter.assignee,
                    body=rng.choice(_MATTER_COMMENTS),
                ),
            )
        )


def _calendar_events(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    day_offset: int,
    drafts: list[TimedDraft],
) -> None:
    if rng.random() >= 0.5:
        return
    organizer = rng.choice(cast.internal)
    others = [
        member for member in cast.internal if member.person_id != organizer.person_id
    ]
    count = min(len(others), rng.randrange(1, 4))
    attendees = (organizer, *rng.sample(others, count))
    start_clock = rng.choice((10, 11, 13, 14, 15, 16)) * 3600 + rng.choice((0, 1800))
    duration = rng.choice((1800, 3600))
    drafts.append(
        TimedDraft(
            at=SimDuration(rng.randrange(8 * 3600, 10 * 3600)),
            source=organizer.entity,
            payload=CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=minter.mint("cal"),
                organizer=organizer.person_id,
                title=rng.choice(_MEETING_TITLES),
                start=SimTime(day_offset + start_clock),
                end=SimTime(day_offset + start_clock + duration),
                attendees=tuple(member.person_id for member in attendees),
                description=rng.choice(_MEETING_DESCRIPTIONS),
            ),
        )
    )


def procedural_day(
    *,
    seed: Seed,
    window: CalendarWindow,
    day_index: int,
    cast: ProceduralCast,
    minter: IdMinter,
) -> tuple[TimedDraft, ...]:
    """One workday of background traffic, sorted by intra-day clock."""

    day = window.iso_date(day_index)
    day_offset = int(window.day_offset(day_index))
    rng = derive_rng(seed, "chronicle.procedural", day)

    drafts: list[TimedDraft] = []
    posted = _standups(rng, cast, minter, drafts)
    _reactions(rng, cast, posted, drafts)
    _internal_emails(rng, cast, minter, drafts)
    _external_emails(rng, cast, minter, drafts)
    _time_entries(rng, cast, drafts)
    _matter_comments(rng, cast, drafts)
    _calendar_events(rng, cast, minter, day_offset, drafts)

    # Stable sort: replies and reactions were generated after (and later
    # than) their targets, so ordering by clock keeps every reference
    # resolvable at validation time.
    drafts.sort(key=lambda draft: int(draft.at))
    return tuple(drafts)
