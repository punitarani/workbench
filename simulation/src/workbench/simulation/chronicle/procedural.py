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


class ChatChannel(_Model):
    conversation_id: str
    members: tuple[CastMember, ...] = Field(min_length=1)


class DmThread(_Model):
    """A standing two-person DM that carries routine background traffic.

    ``traffic`` is the expected number of exchanges on a workday: a pair
    at 0.3 talks a couple of times a week, a pair at 2.0 twice most days.
    Rates above 1 exist so a hot thread (a partner and the docketing
    paralegal) accretes hundreds of messages across a season.
    """

    conversation_id: str
    members: tuple[CastMember, CastMember]
    traffic: float = Field(gt=0.0, le=4.0)

    @model_validator(mode="after")
    def _two_distinct_people(self) -> DmThread:
        if self.members[0].person_id == self.members[1].person_id:
            raise ValueError(f"dm {self.conversation_id} pairs a person with itself")
        return self


class ProceduralCast(_Model):
    """Who generates and receives background traffic, and against what."""

    internal: tuple[CastMember, ...] = Field(min_length=2)
    timekeepers: tuple[CastMember, ...] = Field(min_length=1)
    externals: tuple[CastMember, ...] = Field(min_length=1)
    standup_channel: str
    matters_channel: ChatChannel
    billing_channel: ChatChannel
    it_channel: ChatChannel
    matters: tuple[OpenMatter, ...] = Field(min_length=1)
    dms: tuple[DmThread, ...] = ()

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

_MATTER_LINES = (
    "Where are we on {matter}? Client asked for a status this morning.",
    "Filed the latest on {matter}; the working file is up to date.",
    "{matter}: still waiting on the other side. Will chase Thursday.",
    "New documents landed on {matter} — review pass set for this week.",
    "Anyone have cycles for a quick cite-check on {matter}?",
    "Calendar note: next internal deadline on {matter} is end of week.",
)

_MATTER_REPLIES = (
    "On it — update by end of day.",
    "Adding it to tomorrow's list.",
    "Thanks for the heads-up.",
    "Can take that after lunch.",
)

_BILLING_LINES = (
    "Prebills circulate Thursday. Edits back to me by Friday noon, please.",
    "Trust balances reconciled through last month; shortfalls flagged separately.",
    "Reminder: narratives need enough detail to survive client review.",
    "Invoices on {matter} went out this morning.",
    "Two receivables are past sixty days — escalating next week.",
    "Rate table updates posted; check your matters before month-end.",
)

_IT_LINES = (
    "The scanner on three is offline again. Ticket logged with the vendor.",
    "Anyone else getting certificate warnings on the research portal?",
    "Password resets roll out Friday — watch for the prompt at login.",
    "Docking stations for the new monitors arrive Wednesday.",
    "If the wifi drops in the small conference room, use the wall jack.",
    "Backup window moves to 9 pm tonight; save early.",
)

_IT_REPLIES = (
    "Looking at it now — will follow up here.",
    "Known issue; fix is on the way.",
    "A restart cured it for me.",
)

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

_DM_OPENERS = (
    "got a minute before your next call?",
    "lunch run to the corner place — want anything?",
    "can you resend that last version when you get a chance?",
    "conference room b is double booked again — can we grab yours?",
    "heads up, running about ten minutes late this morning.",
    "do you still have the sign-in sheet from yesterday?",
    "quick one: is the template on the shared drive current?",
    "coffee downstairs in fifteen?",
    "can you cover my phone for an hour this afternoon?",
    "did the courier package show up yet?",
    "are you in tomorrow or working remote?",
    "mind taking a quick look at my draft before it goes out?",
)

_DM_REPLIES = (
    "sure thing.",
    "yep — give me ten.",
    "on it.",
    "can do, after lunch ok?",
    "thanks for the heads up.",
    "sorry, slammed today. tomorrow?",
    "just sent it over.",
    "works for me.",
)

_DM_CLOSERS = (
    "perfect, thanks.",
    "great.",
    "appreciate it.",
    "ok, talk then.",
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


def _channel_message(
    rng: random.Random,
    channel: ChatChannel,
    minter: IdMinter,
    drafts: list[TimedDraft],
    *,
    at: int,
    body: str,
    reply_to: str | None = None,
    exclude: str | None = None,
) -> tuple[str, str]:
    pool = [member for member in channel.members if member.person_id != exclude]
    sender = rng.choice(pool if pool else list(channel.members))
    message_id = minter.mint("chm")
    drafts.append(
        TimedDraft(
            at=SimDuration(at),
            source=sender.entity,
            payload=ChatMessagePayload(
                kind="chat.message",
                chat_message_id=message_id,
                conversation_id=channel.conversation_id,
                reply_to=reply_to,
                sender=sender.person_id,
                body=body,
            ),
        )
    )
    return message_id, sender.person_id


def _matter_chatter(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(rng.randrange(0, 3)):
        matter = rng.choice(cast.matters)
        at = rng.randrange(9 * 3600 + 1800, 17 * 3600)
        body = rng.choice(_MATTER_LINES).format(matter=matter.label)
        message_id, sender = _channel_message(
            rng, cast.matters_channel, minter, drafts, at=at, body=body
        )
        if rng.random() < 0.4:
            _channel_message(
                rng,
                cast.matters_channel,
                minter,
                drafts,
                at=at + rng.randrange(180, 2400),
                body=rng.choice(_MATTER_REPLIES),
                reply_to=message_id,
                exclude=sender,
            )


def _billing_chatter(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    drafts: list[TimedDraft],
) -> None:
    if rng.random() >= 0.55:
        return
    for _ in range(rng.randrange(1, 3)):
        matter = rng.choice(cast.matters)
        body = rng.choice(_BILLING_LINES).format(matter=matter.label)
        _channel_message(
            rng,
            cast.billing_channel,
            minter,
            drafts,
            at=rng.randrange(10 * 3600, 16 * 3600),
            body=body,
        )


def _it_chatter(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    drafts: list[TimedDraft],
) -> None:
    if rng.random() >= 0.35:
        return
    at = rng.randrange(9 * 3600, 16 * 3600)
    message_id, asker = _channel_message(
        rng, cast.it_channel, minter, drafts, at=at, body=rng.choice(_IT_LINES)
    )
    if rng.random() < 0.5:
        _channel_message(
            rng,
            cast.it_channel,
            minter,
            drafts,
            at=at + rng.randrange(300, 3600),
            body=rng.choice(_IT_REPLIES),
            reply_to=message_id,
            exclude=asker,
        )


def _dm_message(
    thread: DmThread,
    sender: CastMember,
    minter: IdMinter,
    drafts: list[TimedDraft],
    *,
    at: int,
    body: str,
) -> None:
    drafts.append(
        TimedDraft(
            at=SimDuration(at),
            source=sender.entity,
            payload=ChatMessagePayload(
                kind="chat.message",
                chat_message_id=minter.mint("chm"),
                conversation_id=thread.conversation_id,
                reply_to=None,
                sender=sender.person_id,
                body=body,
            ),
        )
    )


def _dm_chatter(
    rng: random.Random,
    cast: ProceduralCast,
    minter: IdMinter,
    drafts: list[TimedDraft],
) -> None:
    for thread in cast.dms:
        whole, fraction = divmod(thread.traffic, 1.0)
        exchanges = int(whole) + (1 if rng.random() < fraction else 0)
        for _ in range(exchanges):
            first, second = thread.members
            if rng.random() < 0.5:
                first, second = second, first
            at = rng.randrange(9 * 3600, 17 * 3600)
            _dm_message(
                thread, first, minter, drafts, at=at, body=rng.choice(_DM_OPENERS)
            )
            if rng.random() < 0.85:
                at += rng.randrange(60, 900)
                _dm_message(
                    thread, second, minter, drafts, at=at, body=rng.choice(_DM_REPLIES)
                )
                if rng.random() < 0.4:
                    at += rng.randrange(30, 600)
                    _dm_message(
                        thread,
                        first,
                        minter,
                        drafts,
                        at=at,
                        body=rng.choice(_DM_CLOSERS),
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
    _matter_chatter(rng, cast, minter, drafts)
    _billing_chatter(rng, cast, minter, drafts)
    _it_chatter(rng, cast, minter, drafts)
    _dm_chatter(rng, cast, minter, drafts)
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
