"""Seeded background-traffic generators for procedural days.

One rng derived from the seed and the day's date drives every choice, and
ids come from the caller's minter in generation order, so the same inputs
always produce the same drafts byte for byte. Drafts reference only the
cast, channel, and matters they are given, which keeps a chronicle built
from them coherent by construction.

Prose is not stored here. The caller supplies a :class:`ProceduralVoice`
of slot-filled templates, so a workplace owns its own register and the
generators own only the shape of a day: how many messages, from whom,
against which matter, at what hour. Templates compose with the slot pools
at generation time, which is what keeps a season of traffic from
collapsing into a handful of repeated strings.
"""

import random
import string
from collections.abc import Mapping, Sequence

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
from workbench.simulation.chronicle.calendar import SECONDS_PER_DAY, CalendarWindow
from workbench.simulation.errors import ChronicleError


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


class Timekeeper(_Model):
    """A fee earner, their billable-day target, and their hourly rate."""

    member: CastMember
    daily_hours: float = Field(gt=0.0, le=12.0)
    rate_cents: int = Field(ge=0)


class OpenMatter(_Model):
    """A live matter and how much of the firm's effort it absorbs.

    ``weight`` is relative complexity: a matter at 2.0 draws twice the
    entries of one at 1.0 from the people staffed on it, which is what
    makes per-matter totals track the work rather than the clock.
    """

    ticket_id: str
    label: str
    assignee: str
    weight: float = Field(default=1.0, gt=0.0)
    staff: tuple[str, ...] = ()

    def team(self) -> tuple[str, ...]:
        return self.staff if self.staff else (self.assignee,)


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


class EmailForm(_Model):
    subject: str
    body: str


class ProceduralVoice(_Model):
    """Slot-filled phrasings the generators compose bodies from.

    Every string is a template: ``{name}`` is replaced either from the
    generator's context (``matter``, ``first``, ``me``, ``focus``) or by a
    seeded draw from ``slots``. Slot values may themselves carry slots.
    """

    standup: tuple[str, ...] = Field(min_length=1)
    standup_focus: tuple[str, ...] = Field(min_length=1)
    reactions: tuple[str, ...] = Field(min_length=1)
    matter_lines: tuple[str, ...] = Field(min_length=1)
    matter_replies: tuple[str, ...] = Field(min_length=1)
    billing_lines: tuple[str, ...] = Field(min_length=1)
    billing_replies: tuple[str, ...] = Field(min_length=1)
    it_lines: tuple[str, ...] = Field(min_length=1)
    it_replies: tuple[str, ...] = Field(min_length=1)
    dm_openers: tuple[str, ...] = Field(min_length=1)
    dm_replies: tuple[str, ...] = Field(min_length=1)
    dm_closers: tuple[str, ...] = Field(min_length=1)
    # Verbatim house phrasings for the firm's standing one-to-one asks.
    # These are never slot-filled: the point is that they read identically
    # every time, the way a habitual request does.
    standing_requests: tuple[str, ...] = ()
    standing_request_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    internal_email: tuple[EmailForm, ...] = Field(min_length=1)
    internal_replies: tuple[str, ...] = Field(min_length=1)
    external_email: tuple[EmailForm, ...] = Field(min_length=1)
    external_replies: tuple[str, ...] = Field(min_length=1)
    time_notes: tuple[str, ...] = Field(min_length=1)
    matter_notes: tuple[str, ...] = Field(min_length=1)
    meeting_titles: tuple[str, ...] = Field(min_length=1)
    meeting_descriptions: tuple[str, ...] = Field(min_length=1)
    slots: Mapping[str, tuple[str, ...]] = Field(default_factory=dict)


class ProceduralCast(_Model):
    """Who generates and receives background traffic, and against what.

    ``channel_silent`` members participate in email, DM, and timekeeping
    traffic but never post to channels: the world model fixes a
    conversation's membership at creation, so someone who joins the firm
    after genesis cannot appear in the genesis channels.
    """

    internal: tuple[CastMember, ...] = Field(min_length=2)
    channel_silent: tuple[CastMember, ...] = ()
    timekeepers: tuple[Timekeeper, ...] = Field(min_length=1)
    externals: tuple[CastMember, ...] = Field(min_length=1)
    standup_channel: str
    matters_channel: ChatChannel
    billing_channel: ChatChannel
    it_channel: ChatChannel
    matters: tuple[OpenMatter, ...] = Field(min_length=1)
    dms: tuple[DmThread, ...] = ()

    @model_validator(mode="after")
    def _timekeepers_are_internal(self) -> ProceduralCast:
        internal_ids = {
            member.person_id for member in (*self.internal, *self.channel_silent)
        }
        strangers = [
            keeper.member.person_id
            for keeper in self.timekeepers
            if keeper.member.person_id not in internal_ids
        ]
        if strangers:
            raise ValueError(f"timekeepers are not internal cast: {strangers}")
        return self


class DayProfile(_Model):
    """How much of a normal working day a given date carries.

    ``intensity`` scales every generator's expected volume, so a Saturday
    or an observed holiday produces the same kinds of traffic as a Tuesday
    at a fraction of the rate rather than the silence of a synthetic
    calendar.
    """

    kind: str = Field(pattern=r"^(workday|weekend|holiday)$")
    intensity: float = Field(gt=0.0, le=1.0)


WORKDAY = DayProfile(kind="workday", intensity=1.0)

_FORMATTER = string.Formatter()

# Clock spans. Office hours carry the bulk; a small share of every
# workday lands before the office opens or well after it empties, and
# non-working days spread across daylight instead.
_OFFICE_OPEN = 8 * 3600 + 1800
_OFFICE_CLOSE = 18 * 3600
_EARLY = (6 * 3600 + 1800, _OFFICE_OPEN)
_LATE = (_OFFICE_CLOSE + 1800, 22 * 3600 + 1800)
_OFF_DAY = (8 * 3600, 20 * 3600)
_EARLY_RATE = 0.025
_LATE_RATE = 0.045

_MORNING = 9 * 3600

# Billing increments a firm actually records: tenths of an hour, weighted
# toward the short-to-medium entries that make up most of a day. Laid out
# as a table because the shape of the distribution is the point.
# fmt: off
_DURATION_WEIGHTS: tuple[tuple[int, int], ...] = (
    (6, 5), (12, 9), (18, 13), (24, 14), (30, 15), (36, 13),
    (42, 12), (48, 11), (54, 9), (60, 12), (72, 9), (84, 7),
    (90, 8), (102, 5), (114, 4), (120, 6), (138, 3), (150, 3),
    (168, 2), (180, 3), (210, 2), (240, 1),
)
# fmt: on
_DURATIONS = tuple(minutes for minutes, _ in _DURATION_WEIGHTS)
_WEIGHTS = tuple(weight for _, weight in _DURATION_WEIGHTS)
_NON_BILLABLE_RATE = 0.11
_MAX_ENTRIES_PER_DAY = 11


def fill(
    rng: random.Random, voice: ProceduralVoice, template: str, **context: str
) -> str:
    """Resolve ``{slot}`` placeholders from context, then from the pools."""

    text = template
    for _ in range(4):
        fields = [name for _, name, _, _ in _FORMATTER.parse(text) if name]
        if not fields:
            return text
        values: dict[str, str] = {}
        for name in dict.fromkeys(fields):
            if name in context:
                values[name] = context[name]
                continue
            pool = voice.slots.get(name)
            if pool is None:
                raise ChronicleError(
                    f"template {template!r} needs slot {name!r}, which the voice "
                    "does not define"
                )
            values[name] = rng.choice(pool)
        text = text.format(**values)
    raise ChronicleError(f"template {template!r} did not resolve in four passes")


def _pick(
    rng: random.Random, voice: ProceduralVoice, pool: Sequence[str], **c: str
) -> str:
    return fill(rng, voice, rng.choice(pool), **c)


def _count(rng: random.Random, mean: float) -> int:
    whole = int(mean)
    return whole + (1 if rng.random() < mean - whole else 0)


def _clock(rng: random.Random, profile: DayProfile, low: int, high: int) -> int:
    if profile.kind != "workday":
        return rng.randrange(*_OFF_DAY)
    roll = rng.random()
    if roll < _EARLY_RATE:
        return rng.randrange(*_EARLY)
    if roll < _EARLY_RATE + _LATE_RATE:
        return rng.randrange(*_LATE)
    return rng.randrange(low, high)


def _after(rng: random.Random, at: int, low: int, high: int) -> int:
    return min(at + rng.randrange(low, high), SECONDS_PER_DAY - 1)


def _standups(
    rng: random.Random,
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> list[tuple[str, int]]:
    posted: list[tuple[str, int]] = []
    for member in cast.internal:
        if rng.random() >= 0.85 * profile.intensity:
            continue
        at = (
            _MORNING + rng.randrange(0, 1800)
            if profile.kind == "workday"
            else rng.randrange(*_OFF_DAY)
        )
        matter = rng.choice(cast.matters)
        focus = _pick(rng, voice, voice.standup_focus, matter=matter.label)
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
                    body=_pick(rng, voice, voice.standup, focus=focus),
                ),
            )
        )
        posted.append((message_id, at))
    return posted


def _reactions(
    rng: random.Random,
    voice: ProceduralVoice,
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
                at=SimDuration(_after(rng, at, 120, 1800)),
                source=reactor.entity,
                payload=ChatReactionAddedPayload(
                    kind="chat.reaction.added",
                    conversation_id=cast.standup_channel,
                    chat_message_id=message_id,
                    person_id=reactor.person_id,
                    emoji=rng.choice(voice.reactions),
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
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(_count(rng, 1.1 * profile.intensity)):
        matter = rng.choice(cast.matters)
        at = _clock(rng, profile, _MORNING + 1800, 17 * 3600)
        body = _pick(rng, voice, voice.matter_lines, matter=matter.label)
        message_id, sender = _channel_message(
            rng, cast.matters_channel, minter, drafts, at=at, body=body
        )
        if rng.random() < 0.4:
            _channel_message(
                rng,
                cast.matters_channel,
                minter,
                drafts,
                at=_after(rng, at, 180, 2400),
                body=_pick(rng, voice, voice.matter_replies, matter=matter.label),
                reply_to=message_id,
                exclude=sender,
            )


def _billing_chatter(
    rng: random.Random,
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(_count(rng, 0.9 * profile.intensity)):
        matter = rng.choice(cast.matters)
        at = _clock(rng, profile, 10 * 3600, 16 * 3600)
        message_id, asker = _channel_message(
            rng,
            cast.billing_channel,
            minter,
            drafts,
            at=at,
            body=_pick(rng, voice, voice.billing_lines, matter=matter.label),
        )
        if rng.random() < 0.35:
            _channel_message(
                rng,
                cast.billing_channel,
                minter,
                drafts,
                at=_after(rng, at, 300, 3600),
                body=_pick(rng, voice, voice.billing_replies, matter=matter.label),
                reply_to=message_id,
                exclude=asker,
            )


def _it_chatter(
    rng: random.Random,
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(_count(rng, 0.6 * profile.intensity)):
        at = _clock(rng, profile, 9 * 3600, 16 * 3600)
        message_id, asker = _channel_message(
            rng,
            cast.it_channel,
            minter,
            drafts,
            at=at,
            body=_pick(rng, voice, voice.it_lines),
        )
        if rng.random() < 0.5:
            _channel_message(
                rng,
                cast.it_channel,
                minter,
                drafts,
                at=_after(rng, at, 300, 3600),
                body=_pick(rng, voice, voice.it_replies),
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
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    for thread in cast.dms:
        for _ in range(_count(rng, thread.traffic * profile.intensity)):
            first, second = thread.members
            if rng.random() < 0.5:
                first, second = second, first
            at = _clock(rng, profile, _MORNING, 17 * 3600)
            if voice.standing_requests and rng.random() < voice.standing_request_rate:
                opener = rng.choice(voice.standing_requests)
            else:
                opener = _pick(rng, voice, voice.dm_openers)
            _dm_message(thread, first, minter, drafts, at=at, body=opener)
            if rng.random() < 0.85:
                at = _after(rng, at, 60, 900)
                _dm_message(
                    thread,
                    second,
                    minter,
                    drafts,
                    at=at,
                    body=_pick(rng, voice, voice.dm_replies),
                )
                if rng.random() < 0.4:
                    _dm_message(
                        thread,
                        first,
                        minter,
                        drafts,
                        at=_after(rng, at, 30, 600),
                        body=_pick(rng, voice, voice.dm_closers),
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
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(_count(rng, 3.0 * profile.intensity)):
        sender, recipient = rng.sample([*cast.internal, *cast.channel_silent], 2)
        form = rng.choice(voice.internal_email)
        context = {"first": recipient.first_name, "me": sender.first_name}
        at = _clock(rng, profile, 10 * 3600, 17 * 3600)
        draft, message_id, thread = _email(
            at=at,
            minter=minter,
            sender=sender,
            recipient=recipient,
            subject=fill(rng, voice, form.subject, **context),
            body=fill(rng, voice, form.body, **context),
        )
        drafts.append(draft)
        if rng.random() < 0.5:
            reply, _, _ = _email(
                at=_after(rng, at, 600, 5400),
                minter=minter,
                sender=recipient,
                recipient=sender,
                subject=f"Re: {draft.payload.subject}",
                body=_pick(
                    rng,
                    voice,
                    voice.internal_replies,
                    first=sender.first_name,
                    me=recipient.first_name,
                ),
                thread_id=thread,
                in_reply_to=message_id,
            )
            drafts.append(reply)


def _external_emails(
    rng: random.Random,
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(_count(rng, 2.0 * profile.intensity)):
        sender = rng.choice(cast.externals)
        recipient = rng.choice(cast.timekeepers).member
        form = rng.choice(voice.external_email)
        context = {"first": recipient.first_name, "me": sender.name}
        at = _clock(rng, profile, 8 * 3600 + 1800, 16 * 3600)
        draft, message_id, thread = _email(
            at=at,
            minter=minter,
            sender=sender,
            recipient=recipient,
            subject=fill(rng, voice, form.subject, **context),
            body=fill(rng, voice, form.body, **context),
        )
        drafts.append(draft)
        if rng.random() < 0.4:
            reply, _, _ = _email(
                at=_after(rng, at, 1800, 7200),
                minter=minter,
                sender=recipient,
                recipient=sender,
                subject=f"Re: {draft.payload.subject}",
                body=_pick(
                    rng,
                    voice,
                    voice.external_replies,
                    first=sender.first_name,
                    me=recipient.first_name,
                ),
                thread_id=thread,
                in_reply_to=message_id,
            )
            drafts.append(reply)


def _away_days(seed: Seed, window: CalendarWindow, person_id: str) -> frozenset[str]:
    """The person's out-of-office blocks, stable as a horizon grows.

    Absence is contiguous: a fee earner takes a week, not seven scattered
    Tuesdays, and the resulting holes are what make a season of billing
    look recorded rather than generated. Select against complete calendar
    years rather than the requested window: otherwise extending a simulation
    changes the random indices—and therefore the historical record—inside its
    already-materialized prefix.
    """

    away: set[str] = set()
    first_year = int(window.start_date[:4])
    last_year = int(window.end_date[:4])
    for year in range(first_year, last_year + 1):
        annual = CalendarWindow(
            start_date=f"{year}-01-01",
            end_date=f"{year}-12-31",
            timezone=window.timezone,
        )
        rng = derive_rng(seed, "chronicle.absence", person_id, str(year))
        workdays = annual.workdays()
        for _ in range(rng.randrange(2, 4)):
            start = rng.randrange(0, len(workdays))
            length = rng.choice((1, 1, 2, 3, 5, 5))
            for index in workdays[start : start + length]:
                away.add(annual.iso_date(index))
    return frozenset(away)


def _scoped_away_days(
    seed: Seed, scope: CalendarWindow, person_id: str
) -> frozenset[str]:
    """Reproduce an explicitly versioned dataset's absence cohort."""

    rng = derive_rng(seed, "chronicle.absence", person_id)
    workdays = scope.workdays()
    away: set[str] = set()
    for _ in range(rng.randrange(2, 4)):
        start = rng.randrange(0, len(workdays))
        length = rng.choice((1, 1, 2, 3, 5, 5))
        for index in workdays[start : start + length]:
            away.add(scope.iso_date(index))
    return frozenset(away)


def _day_factor(rng: random.Random) -> float:
    roll = rng.random()
    if roll < 0.11:
        return rng.uniform(0.3, 0.65)
    if roll > 0.86:
        return rng.uniform(1.2, 1.55)
    return rng.uniform(0.82, 1.12)


def _matter_for(
    rng: random.Random, cast: ProceduralCast, keeper: Timekeeper
) -> OpenMatter:
    staffed = [
        matter for matter in cast.matters if keeper.member.person_id in matter.team()
    ]
    pool = staffed if staffed else list(cast.matters)
    return rng.choices(pool, weights=[matter.weight for matter in pool])[0]


def _time_entries(
    rng: random.Random,
    voice: ProceduralVoice,
    cast: ProceduralCast,
    seed: Seed,
    window: CalendarWindow,
    day: str,
    profile: DayProfile,
    drafts: list[TimedDraft],
    absence_scope: CalendarWindow | None,
) -> None:
    for keeper in cast.timekeepers:
        person_id = keeper.member.person_id
        if profile.kind == "workday":
            away = (
                _away_days(seed, window, person_id)
                if absence_scope is None
                else _scoped_away_days(seed, absence_scope, person_id)
            )
            if day in away:
                continue
            target = keeper.daily_hours * _day_factor(rng) * 60
        else:
            if rng.random() >= profile.intensity:
                continue
            target = keeper.daily_hours * rng.uniform(0.25, 0.7) * 60

        logged = 0.0
        entries = 0
        while logged < target - 9 and entries < _MAX_ENTRIES_PER_DAY:
            minutes = rng.choices(_DURATIONS, weights=_WEIGHTS)[0]
            matter = _matter_for(rng, cast, keeper)
            drafts.append(
                TimedDraft(
                    at=SimDuration(_clock(rng, profile, 9 * 3600, 19 * 3600)),
                    source=keeper.member.entity,
                    payload=TimeLoggedPayload(
                        kind="work.time.logged",
                        person_id=person_id,
                        ticket_id=matter.ticket_id,
                        minutes=minutes,
                        note=_pick(rng, voice, voice.time_notes, matter=matter.label),
                        rate_cents=keeper.rate_cents,
                        billable=True,
                    ),
                )
            )
            logged += minutes
            entries += 1
        if entries and rng.random() < _NON_BILLABLE_RATE:
            matter = _matter_for(rng, cast, keeper)
            drafts.append(
                TimedDraft(
                    at=SimDuration(_clock(rng, profile, 9 * 3600, 19 * 3600)),
                    source=keeper.member.entity,
                    payload=TimeLoggedPayload(
                        kind="work.time.logged",
                        person_id=person_id,
                        ticket_id=matter.ticket_id,
                        minutes=rng.choices(_DURATIONS, weights=_WEIGHTS)[0],
                        note=_pick(rng, voice, voice.time_notes, matter=matter.label),
                        rate_cents=keeper.rate_cents,
                        billable=False,
                    ),
                )
            )


def _matter_comments(
    rng: random.Random,
    voice: ProceduralVoice,
    cast: ProceduralCast,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    for _ in range(_count(rng, 2.2 * profile.intensity)):
        matter = rng.choice(cast.matters)
        entity = matter.assignee.partition("-")[2] or matter.assignee
        drafts.append(
            TimedDraft(
                at=SimDuration(_clock(rng, profile, 10 * 3600, 18 * 3600)),
                source=entity,
                payload=TicketCommentedPayload(
                    kind="ticket.commented",
                    ticket_id=matter.ticket_id,
                    actor=matter.assignee,
                    body=_pick(rng, voice, voice.matter_notes, matter=matter.label),
                ),
            )
        )


def _calendar_events(
    rng: random.Random,
    voice: ProceduralVoice,
    cast: ProceduralCast,
    minter: IdMinter,
    day_offset: int,
    profile: DayProfile,
    drafts: list[TimedDraft],
) -> None:
    if rng.random() >= 0.5 * profile.intensity:
        return
    organizer = rng.choice(cast.internal)
    others = [
        member for member in cast.internal if member.person_id != organizer.person_id
    ]
    count = min(len(others), rng.randrange(1, 4))
    attendees = (organizer, *rng.sample(others, count))
    matter = rng.choice(cast.matters)
    start_clock = rng.choice((10, 11, 13, 14, 15, 16)) * 3600 + rng.choice((0, 1800))
    duration = rng.choice((1800, 3600))
    drafts.append(
        TimedDraft(
            at=SimDuration(_clock(rng, profile, 8 * 3600, 10 * 3600)),
            source=organizer.entity,
            payload=CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=minter.mint("cal"),
                organizer=organizer.person_id,
                title=_pick(rng, voice, voice.meeting_titles, matter=matter.label),
                start=SimTime(day_offset + start_clock),
                end=SimTime(day_offset + start_clock + duration),
                attendees=tuple(member.person_id for member in attendees),
                description=_pick(rng, voice, voice.meeting_descriptions),
            ),
        )
    )


def procedural_day(
    *,
    seed: Seed,
    window: CalendarWindow,
    day_index: int,
    cast: ProceduralCast,
    voice: ProceduralVoice,
    minter: IdMinter,
    profile: DayProfile = WORKDAY,
    absence_scope: CalendarWindow | None = None,
) -> tuple[TimedDraft, ...]:
    """One day of background traffic, sorted by intra-day clock.

    The default absence schedule is horizon-stable. ``absence_scope`` exists
    only for a dataset that has committed an earlier finite-window schedule
    and needs to extend its future without rewriting that historical prefix.
    """

    day = window.iso_date(day_index)
    day_offset = int(window.day_offset(day_index))
    rng = derive_rng(seed, "chronicle.procedural", day)

    drafts: list[TimedDraft] = []
    posted = _standups(rng, voice, cast, minter, profile, drafts)
    _reactions(rng, voice, cast, posted, drafts)
    _matter_chatter(rng, voice, cast, minter, profile, drafts)
    _billing_chatter(rng, voice, cast, minter, profile, drafts)
    _it_chatter(rng, voice, cast, minter, profile, drafts)
    _dm_chatter(rng, voice, cast, minter, profile, drafts)
    _internal_emails(rng, voice, cast, minter, profile, drafts)
    _external_emails(rng, voice, cast, minter, profile, drafts)
    _time_entries(
        rng,
        voice,
        cast,
        seed,
        window,
        day,
        profile,
        drafts,
        absence_scope,
    )
    _matter_comments(rng, voice, cast, profile, drafts)
    _calendar_events(rng, voice, cast, minter, day_offset, profile, drafts)

    # Stable sort: replies and reactions were generated after (and later
    # than) their targets, so ordering by clock keeps every reference
    # resolvable at validation time.
    drafts.sort(key=lambda draft: int(draft.at))
    return tuple(drafts)
