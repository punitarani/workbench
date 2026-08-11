"""Build the Hartwell & Marsh history: genesis plus procedural workdays,
with the five storyline arcs directed onto their dates in full mode.

    uv run python datasets/hartwell/build_history.py [--out out/hartwell]
        [--seed 42] [--days 5|all] [--check]

Pilot mode (``--days N``) is fully offline: procedural traffic only, for
the first N calendar days, projected into ``pilot-bundle/``. Full mode
(``--days all``) authors storyline prose through the content cache (LM on
cache miss, hard-capped), builds all 121 calendar days — weekends and
observed holidays included, at their own reduced rates — validates,
materializes into ``bundle/`` (seat unset), prints per-month tag counts,
and audits the storyline evidence. ``--check`` builds twice into
temporary directories and fails unless the bytes are identical; in full
mode it requires a warmed content cache.
"""

import argparse
import asyncio
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.core.events import Event
from workbench.core.events.calendar import CalendarEventScheduledPayload
from workbench.core.events.chat import ChatMessagePayload, ChatReactionAddedPayload
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.environment import materialize
from workbench.simulation.chronicle.builder import Chronicle
from workbench.simulation.chronicle.calendar import CalendarWindow
from workbench.simulation.chronicle.content import ContentStore
from workbench.simulation.chronicle.minter import minter_from_events
from workbench.simulation.chronicle.procedural import ProceduralCast, procedural_day
from workbench.simulation.lm.budget import BudgetedLM
from workbench.simulation.lm.fake import FakeLM
from workbench.simulation.lm.openrouter import DEFAULT_MODEL, OpenRouterLM
from workbench.tools import check_coherence
from workbench.workplaces.hartwell import (
    FEDERAL_HOLIDAYS_2026,
    VOICE,
    WINDOW,
    build_genesis,
    day_profile,
    procedural_cast,
)
from workbench.workplaces.hartwell.storylines import (
    ARCHWAY_NDA_TITLE,
    ARROYO_HEARING_TITLE,
    BAYMARK_NDA_TITLE,
    CASCADIA_LETTER_TITLE,
    CONFORMING_NDA_TITLES,
    DOC_MENTION_MARKERS,
    INDEMNITY_PARAGRAPH,
    IRONCLAD_NDA_TITLE,
    LEXIPOINT_NDA_TITLE,
    LUMEN_AGREEMENT_TITLE,
    LUMEN_SOW_TITLE,
    MATTER_DOCUMENTS,
    PLAYBOOK_TITLE,
    S1_IRONCLAD_THREAD_REPLY,
    S2_CUTOFF_CHAT,
    S2_SUPPORT_MARKERS,
    S2_TICKET,
    S3_TICKET,
    S4_CLOSED_DATE,
    S4_TICKET,
    S5_DM_CORRECTION,
    S5_RECAP_SUBJECT,
    StorylineDirector,
    author_content,
    missing_content,
)

PILOT_DAYS = 5
LEGACY_AUDIT_END = "2026-06-30"
LEGACY_ABSENCE_SCOPE = CalendarWindow(
    start_date="2026-03-02",
    end_date=LEGACY_AUDIT_END,
    timezone=WINDOW.timezone,
)
CHALLENGE_ABSENCE_SCOPE = CalendarWindow(
    start_date="2026-07-01",
    end_date="2026-09-30",
    timezone=WINDOW.timezone,
)


def build_world(
    out_dir: Path,
    seed: Seed,
    *,
    day_count: int | None = PILOT_DAYS,
    texts: Mapping[str, str] | None = None,
) -> Path:
    """``day_count=None`` builds the whole window; ``texts`` enables storylines."""

    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "world.jsonl"
    if log_path.exists():
        log_path.unlink()

    genesis = build_genesis(seed)
    chronicle = Chronicle(log_path, window=WINDOW)
    chronicle.write_genesis(genesis.events)

    minter = minter_from_events(genesis.events)
    cast = procedural_cast(genesis)
    closed_cast = _without_matter(cast, S4_TICKET)
    director = (
        StorylineDirector(genesis=genesis, texts=texts) if texts is not None else None
    )

    span = WINDOW.day_count if day_count is None else min(day_count, WINDOW.day_count)
    for day_index in range(span):
        day = WINDOW.iso_date(day_index)
        active_cast = cast
        if director is not None and day > S4_CLOSED_DATE:
            active_cast = closed_cast
        drafts = list(
            procedural_day(
                seed=seed,
                window=WINDOW,
                day_index=day_index,
                cast=active_cast,
                voice=VOICE,
                minter=minter,
                profile=day_profile(seed, day_index),
                absence_scope=(
                    LEGACY_ABSENCE_SCOPE
                    if day <= LEGACY_AUDIT_END
                    else CHALLENGE_ABSENCE_SCOPE
                ),
            )
        )
        if director is not None:
            drafts.extend(director.drafts_for(day, minter))
        drafts.sort(key=lambda draft: int(draft.at))
        chronicle.add_procedural_day(day_index, drafts)
    chronicle.finish()
    return log_path


def _without_matter(cast: ProceduralCast, ticket_id: str) -> ProceduralCast:
    return cast.model_copy(
        update={
            "matters": tuple(
                matter for matter in cast.matters if matter.ticket_id != ticket_id
            )
        }
    )


async def _resolve_texts(
    cache_dir: Path, seed: Seed, *, max_calls: int
) -> tuple[dict[str, str], int, object]:
    store = ContentStore(cache_dir)
    missing = missing_content(store, model=DEFAULT_MODEL, seed=seed)
    if not missing:
        # Fully cached: a budget of zero makes any unexpected miss fail loud.
        lm = BudgetedLM(FakeLM(), max_calls=0)
        texts = await author_content(store=store, lm=lm, model=DEFAULT_MODEL, seed=seed)
        return texts, 0, lm.usage
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit(
            f"{len(missing)} content pieces are uncached and OPENROUTER_API_KEY "
            "is unset; warm the content cache first"
        )
    inner = OpenRouterLM(api_key=api_key)
    lm = BudgetedLM(inner, max_calls=max_calls)
    try:
        texts = await author_content(store=store, lm=lm, model=DEFAULT_MODEL, seed=seed)
    finally:
        await inner.close()
    return texts, lm.calls, lm.usage


def print_summary(log_path: Path, *, by_month: bool) -> None:
    events = read_events(log_path)
    counts: dict[str, Counter[str]] = {}
    order: list[str] = []
    bucket = "genesis"
    counts[bucket] = Counter()
    order.append(bucket)
    for event in events:
        if event.tag == "sim.day.started":
            day = event.payload.day
            bucket = day[:7] if by_month else day
            if bucket not in counts:
                counts[bucket] = Counter()
                order.append(bucket)
        counts[bucket][event.tag] += 1
    for bucket in order:
        total = sum(counts[bucket].values())
        print(f"{bucket}: {total} events")
        for tag, count in sorted(counts[bucket].items()):
            print(f"  {tag}: {count}")
    print(f"total: {len(events)} events")


def _document_versions(events: list[Event]) -> dict[str, list[tuple[int, str]]]:
    titles: dict[str, str] = {}
    versions: dict[str, list[tuple[int, str]]] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, DocumentCreatedPayload):
            titles[payload.document_id] = payload.title
            versions.setdefault(payload.title, []).append((1, payload.content))
        elif isinstance(payload, DocumentRevisedPayload):
            title = titles[payload.document_id]
            versions[title].append((payload.revision, payload.content))
    return versions


def _event_date(event: Event) -> str:
    return WINDOW.iso_date(int(event.time) // 86_400)


def _audit_fabric(events: list[Event], check: Callable[[str, bool], None]) -> None:
    """Gate the record against the degeneracy an expert reader notices.

    Verbatim repetition, a calendar with no weekends, a firm that bills a
    third of a real day, and money that exists only as prose are all
    tells. Each is measured here so a regression fails the build rather
    than shipping into a task.
    """

    surfaces: dict[str, list[str]] = {}
    conversations = {
        event.payload.conversation_id: (
            event.payload.name or "dm",
            event.payload.conversation_type,
        )
        for event in events
        if event.payload.kind == "chat.conversation.created"
    }
    for event in events:
        payload = event.payload
        if isinstance(payload, ChatMessagePayload):
            name, kind = conversations[payload.conversation_id]
            surfaces.setdefault("dm" if kind == "dm" else name, []).append(payload.body)
    worst = max(
        (
            (max(Counter(bodies).values()) / len(bodies), name)
            for name, bodies in surfaces.items()
        ),
        default=(0.0, ""),
    )
    check(
        f"no chat surface repeats one body more than 5% of the time "
        f"(worst {worst[1]} at {worst[0]:.1%})",
        worst[0] <= 0.05,
    )
    dms = surfaces.get("dm", [])
    check(
        f"the DM fabric carries {len(set(dms))} distinct bodies across "
        f"{len(dms)} messages (>= 800)",
        len(set(dms)) >= 800,
    )
    mail = [
        event.payload.body
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
    ]
    check(
        f"mail bodies are {len(set(mail))} distinct across {len(mail)} "
        "messages (>= 85%)",
        len(set(mail)) >= 0.85 * len(mail),
    )

    entries = [
        event for event in events if isinstance(event.payload, TimeLoggedPayload)
    ]
    narratives = {event.payload.note for event in entries}
    durations = Counter(event.payload.minutes for event in entries)
    check(
        f"{len(narratives)} distinct billing narratives across "
        f"{len(entries)} entries (>= 500)",
        len(narratives) >= 500,
    )
    check(
        f"no single duration covers more than 15% of entries "
        f"({durations.most_common(1)[0][1] / len(entries):.1%})",
        durations.most_common(1)[0][1] <= 0.15 * len(entries),
    )
    rated = [event for event in entries if event.payload.rate_cents is not None]
    non_billable = [event for event in entries if not event.payload.billable]
    billed_cents = sum(
        event.payload.amount_cents or 0 for event in entries if event.payload.billable
    )
    check(
        f"every time entry carries a rate ({len(rated)}/{len(entries)}) and "
        f"{len(non_billable)} are written off; the window bills "
        f"${billed_cents / 100:,.0f}",
        len(rated) == len(entries) and non_billable,
    )

    workdays = {WINDOW.iso_date(index): True for index in WINDOW.workdays()}
    hours: Counter[str] = Counter()
    for event in entries:
        if event.payload.billable:
            hours[event.payload.person_id] += event.payload.minutes
    per_day = {
        person: minutes / 60 / len(workdays) for person, minutes in hours.items()
    }
    low, high = min(per_day.values()), max(per_day.values())
    average = sum(per_day.values()) / len(per_day)
    check(
        f"fee earners bill {average:.2f} hrs/workday on average "
        f"({low:.2f}-{high:.2f} across the eight), inside 5.5-7.0",
        5.5 <= average <= 7.0 and low >= 4.0 and high <= 8.0,
    )

    by_matter = Counter()
    for event in entries:
        by_matter[event.payload.ticket_id] += event.payload.minutes
    spread = max(by_matter.values()) / min(by_matter.values())
    check(
        f"per-matter hours track complexity: {spread:.1f}x between the "
        "heaviest and lightest matter (>= 4x)",
        spread >= 4.0,
    )

    off_calendar = Counter()
    holidays = {day for day, _, _ in FEDERAL_HOLIDAYS_2026}
    for event in events:
        if event.tag.startswith("sim."):
            continue
        day = _event_date(event)
        if day in holidays:
            off_calendar["holiday"] += 1
        elif date.fromisoformat(day).weekday() >= 5:
            off_calendar["weekend"] += 1
    body = [event for event in events if not event.tag.startswith("sim.")]
    share = (off_calendar["weekend"] + off_calendar["holiday"]) / len(body)
    check(
        f"{off_calendar['weekend']} weekend and {off_calendar['holiday']} "
        f"holiday events, {share:.1%} of the record (1%-8%)",
        0.01 <= share <= 0.08
        and off_calendar["weekend"] > 0
        and off_calendar["holiday"] > 0,
    )
    clocks = Counter(int(event.time) % 86_400 // 3600 for event in entries)
    out_of_hours = sum(
        count for hour, count in clocks.items() if hour < 8 or hour >= 19
    )
    check(
        f"time entries span {min(clocks)}:00-{max(clocks)}:00 with "
        f"{out_of_hours} logged outside 08:00-19:00",
        len(clocks) >= 10 and out_of_hours > 0,
    )

    documented = {document.ticket for document in MATTER_DOCUMENTS} | {S3_TICKET}
    matters = {
        event.payload.ticket_id
        for event in events
        if isinstance(event.payload, TicketCreatedPayload)
    }
    check(
        f"every matter carries working documents ({len(documented)}/{len(matters)})",
        matters <= documented,
    )
    history = sum(
        len(event.payload.changes)
        for event in events
        if isinstance(event.payload, TicketUpdatedPayload)
    )
    check(f"matter history carries {history} field changes (>= 10)", history >= 10)


def audit(log_path: Path, state_dir: Path) -> int:
    events = read_events(log_path)
    report = validate_events(events)
    print(f"validate_events: {'ok' if report.findings == () else report.findings[:5]}")
    findings = check_coherence(state_dir)
    print(f"check_coherence: {findings if findings else '()'}")
    failures = 0 if report.findings == () and not findings else 1

    docs = _document_versions(events)

    def check(label: str, passed: bool) -> None:
        nonlocal failures
        print(f"  [{'ok' if passed else 'FAIL'}] {label}")
        if not passed:
            failures += 1

    print("S1 vendor NDA drift:")
    playbook = dict(docs[PLAYBOOK_TITLE])
    lexipoint = dict(docs[LEXIPOINT_NDA_TITLE])
    ironclad = dict(docs[IRONCLAD_NDA_TITLE])
    check(
        "playbook has 3 revisions, standard stays three (3) years",
        (len(playbook) == 3 and "three (3) years" in playbook[3]),
    )
    check(
        "LexiPoint NDA v1 three (3) years -> v2 five (5) years",
        ("three (3) years" in lexipoint[1] and "five (5) years" in lexipoint[2]),
    )
    check(
        "Ironclad NDA v2 adds the residuals clause the playbook rejects",
        (
            "Residual Knowledge" not in ironclad[1]
            and "Residual Knowledge" in ironclad[2]
            and "Reject any residual-knowledge clause" in playbook[3]
        ),
    )
    nda_titles = {title for title in docs if title.startswith("Mutual NDA")}
    check(
        f"the vendor NDA corpus holds exactly 9 drafts ({len(nda_titles)})",
        len(nda_titles) == 9
        and nda_titles
        == {LEXIPOINT_NDA_TITLE, IRONCLAD_NDA_TITLE, *CONFORMING_NDA_TITLES},
    )
    for title in CONFORMING_NDA_TITLES:
        conforming = dict(docs[title])
        check(
            f"conforming NDA holds in every version: {title.split(' — ')[1]}",
            len(conforming) >= 2
            and all(
                "three (3) years" in content and "Residual Knowledge" not in content
                for content in conforming.values()
            ),
        )
    ironclad_emails = [
        event.payload.body
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and "Ironclad NDA" in event.payload.subject
    ]
    chat_bodies = [
        event.payload.body
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
    ]
    check(
        "Ironclad flip is invisible to keyword search: no email or chat "
        "says 'residual'",
        len(ironclad_emails) >= 2
        and all("residual" not in body.lower() for body in ironclad_emails)
        and all("residual" not in body.lower() for body in chat_bodies),
    )
    nda_email_bodies = [
        event.payload.body
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and "NDA" in event.payload.subject
    ]
    five = re.compile(r"\bfive\b|\(5\)|5-year", re.IGNORECASE)
    check(
        "term drift is invisible to keyword search: no NDA email or any "
        "chat names the accepted length",
        not any(five.search(body) for body in nda_email_bodies)
        and not any(five.search(body) for body in chat_bodies),
    )
    check(
        "the concession is discussed only in the oblique #matters reply",
        sum(1 for body in chat_bodies if body == S1_IRONCLAD_THREAD_REPLY) == 1,
    )

    print("S2 Meridian fee dispute:")
    spike = [
        (_event_date(event), event.payload.minutes)
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S2_TICKET
        and (
            "diligence" in event.payload.note.lower()
            or "data room" in event.payload.note.lower()
        )
        and "2026-04-03" < _event_date(event) <= "2026-04-30"
    ]
    dispute = [
        event
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and event.payload.subject.startswith("Re: Hartwell & Marsh")
        and _event_date(event) == "2026-05-08"
    ]
    notes = [
        event
        for event in events
        if isinstance(event.payload, TicketCommentedPayload)
        and event.payload.ticket_id == S2_TICKET
        and len(event.payload.body) > 400
    ]
    total_minutes = sum(minutes for _, minutes in spike)
    check(
        f"diligence spike after Apr 3: exactly {len(spike)} entries / "
        f"{total_minutes} min (ground truth) joins to the May 8 dispute email",
        len(spike) == 7 and total_minutes == 890 and len(dispute) == 1,
    )
    decoys = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S2_TICKET
        and (
            "diligence" in event.payload.note.lower()
            or "data room" in event.payload.note.lower()
        )
        and _event_date(event) <= "2026-04-03"
    ]
    check(
        f"{len(decoys)} near-miss diligence entries on or before the cutoff, "
        "including one dated the cutoff day itself",
        len(decoys) >= 4
        and any(_event_date(event) == "2026-04-03" for event in decoys),
    )
    cross_matter = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id != S2_TICKET
        and (
            "diligence" in event.payload.note.lower()
            or "data room" in event.payload.note.lower()
        )
        and _event_date(event) > "2026-04-03"
    ]
    check(
        f"{len(cross_matter)} post-cutoff diligence-worded decoys on other matters",
        len(cross_matter) >= 2,
    )
    unworded = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S2_TICKET
        and "scope expansion" in event.payload.note.lower()
        and "diligence" not in event.payload.note.lower()
        and "data room" not in event.payload.note.lower()
        and _event_date(event) > "2026-04-03"
    ]
    check(
        "a post-cutoff Meridian entry describes the expanded scope without "
        "the diligence wording",
        len(unworded) >= 1,
    )
    check("long Clio resolution note on the matter", len(notes) >= 1)
    date_pattern = re.compile(r"April\s+0?3\b|2026-04-03|\b4/3\b")
    note_bodies = [event.payload.body for event in notes]
    check(
        "the note keeps the narrative but no dates, figures, or client names",
        all(
            not date_pattern.search(body)
            and "$" not in body
            and not re.search(r"2026-\d\d-\d\d", body)
            and "Priya" not in body
            and "Raman" not in body
            for body in note_bodies
        ),
    )
    email_bodies = [
        event.payload.body
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and "Meridian" in event.payload.subject
    ]
    cutoff_chats = [
        event
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.body == S2_CUTOFF_CHAT
    ]
    check(
        "the Apr 3 cutoff is stated only in the billing-channel message",
        len(cutoff_chats) == 1
        and not any(date_pattern.search(body) for body in email_bodies),
    )

    # Support audit: every Meridian entry in the disputed window either
    # has a same-day message naming the engagement or is an orphan; the
    # orphan set is a graded deliverable, so its shape is gated here.
    dm_conversations = {
        event.payload.conversation_id
        for event in events
        if event.payload.kind == "chat.conversation.created"
        and event.payload.conversation_type == "dm"
    }

    def referenced(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in S2_SUPPORT_MARKERS)

    coverage: dict[str, set[str]] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, EmailMessagePayload):
            text = f"{payload.subject} {payload.body}"
            if referenced(text):
                kind = "email-name" if "meridian" in text.lower() else "email-oblique"
                coverage.setdefault(_event_date(event), set()).add(kind)
        elif isinstance(payload, ChatMessagePayload) and referenced(payload.body):
            kind = (
                "chat-dm"
                if payload.conversation_id in dm_conversations
                else "chat-public"
            )
            coverage.setdefault(_event_date(event), set()).add(kind)

    matter_entries = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.ticket_id == S2_TICKET
    ]
    window_entries = [
        event
        for event in matter_entries
        if "2026-04-03" < _event_date(event) <= "2026-04-30"
    ]
    orphans = [event for event in window_entries if _event_date(event) not in coverage]
    orphan_days = sorted({_event_date(event) for event in orphans})
    check(
        f"the matter carries {len(matter_entries)} entries, "
        f"{len(window_entries)} in the disputed window (>= 60 / >= 30)",
        len(matter_entries) >= 60 and len(window_entries) >= 30,
    )
    check(
        f"exactly 47 window entries have no same-day support: "
        f"{len(orphans)} on {orphan_days}",
        len(orphans) == 47
        and orphan_days
        == ["2026-04-04", "2026-04-13", "2026-04-20", "2026-04-22", "2026-04-25"],
    )
    window_days = sorted({_event_date(event) for event in window_entries})
    dm_only = [day for day in window_days if coverage.get(day) == {"chat-dm"}]
    oblique_only = [
        day for day in window_days if coverage.get(day) == {"email-oblique"}
    ]
    check(
        f"some window days are supported only through a DM ({dm_only}) "
        f"and some only through a client-nameless email ({oblique_only})",
        len(dm_only) >= 1 and len(oblique_only) >= 1,
    )
    marcus_peter = next(
        event.payload.conversation_id
        for event in events
        if event.payload.kind == "chat.conversation.created"
        and event.payload.conversation_type == "dm"
        and set(event.payload.members) == {"per-marcus-liang", "per-peter-novak"}
    )
    april_by_dm = Counter(
        event.payload.conversation_id
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.conversation_id in dm_conversations
        and "2026-04-01" <= _event_date(event) <= "2026-04-30"
    )
    heavy = [conversation for conversation, count in april_by_dm.items() if count > 100]
    check(
        f"the deal-team DM carries {april_by_dm[marcus_peter]} April "
        f"messages and {len(heavy)} DM threads exceed 100 for the month "
        "(each costs more than one windowed read)",
        april_by_dm[marcus_peter] > 100 and len(heavy) >= 3,
    )

    print("S3 dropped indemnity:")
    lumen = dict(docs[LUMEN_AGREEMENT_TITLE])
    check(
        "seven versions; indemnity present in v1-v3, silently absent from v4 on",
        (
            len(lumen) == 7
            and all(INDEMNITY_PARAGRAPH in lumen[v] for v in (1, 2, 3))
            and all(INDEMNITY_PARAGRAPH not in lumen[v] for v in (4, 5, 6, 7))
        ),
    )
    revisions = {
        event.payload.revision: event.payload.change_summary
        for event in events
        if isinstance(event.payload, DocumentRevisedPayload)
        and event.payload.content.startswith("# Software License and Support")
    }
    check(
        "every change summary is innocuous; only v4's says 'conformed'",
        set(revisions) == {2, 3, 4, 5, 6, 7}
        and all("indemn" not in summary.lower() for summary in revisions.values())
        and "conform" in revisions[4].lower()
        and not any(
            "conform" in summary.lower()
            for revision, summary in revisions.items()
            if revision != 4
        ),
    )
    sow = dict(docs[LUMEN_SOW_TITLE])
    check(
        "the decoy Lumen SOW has a clean four-version history",
        len(sow) == 4
        and all("Indemnification" not in content for content in sow.values()),
    )
    multi = {title: v for title, v in docs.items() if len(v) >= 2}
    deep = [title for title, v in multi.items() if len(v) >= 3]
    check(
        f"the multi-version corpus holds {len(multi)} documents "
        f"({len(deep)} with 3+ versions); the clean-list deliverable is "
        f"{len(multi) - 1} numbers",
        len(multi) == 32 and len(deep) >= 5,
    )
    quotes = [
        event
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and INDEMNITY_PARAGRAPH in event.payload.body
    ]
    check(
        "the old indemnity text is quoted in email after the drop "
        + (f"({_event_date(quotes[0])})" if quotes else "(<missing>)"),
        len(quotes) == 1 and _event_date(quotes[0]) == "2026-06-09",
    )

    print("S4 Cascadia souring:")
    reactions = Counter(
        event.payload.chat_message_id
        for event in events
        if isinstance(event.payload, ChatReactionAddedPayload)
    )
    # Procedural chatter cites the matter by its full label; the storyline
    # voice never does, which isolates the sentiment arc.
    cascadia_chats = [
        (event, reactions.get(event.payload.chat_message_id, 0))
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and ("Cascadia" in event.payload.body or "Hollis" in event.payload.body)
        and "Cascadia supplier dispute" not in event.payload.body
    ]
    counts_in_order = [count for _, count in cascadia_chats]
    closed = [
        event
        for event in events
        if isinstance(event.payload, TicketUpdatedPayload)
        and event.payload.ticket_id == S4_TICKET
        and any(
            change.field == "status" and change.new == "closed"
            for change in event.payload.changes
        )
    ]
    check(
        f"reaction counts decline across the arc, exactly {counts_in_order} "
        "(ground truth trajectory)",
        counts_in_order == [3, 2, 1, 0, 0, 0],
    )
    check(
        "matter closed on "
        + (_event_date(closed[0]) if closed else "<missing>")
        + " with a disengagement letter on file",
        len(closed) == 1
        and _event_date(closed[0]) == S4_CLOSED_DATE
        and CASCADIA_LETTER_TITLE in docs,
    )

    print("S5 hearing rescheduled three times:")
    hearings = [
        event
        for event in events
        if isinstance(event.payload, CalendarEventScheduledPayload)
        and ARROYO_HEARING_TITLE in event.payload.title
    ]
    calendar_says = [
        WINDOW.iso_date(int(event.payload.start) // 86_400) for event in hearings
    ]
    dm_ids = {
        event.payload.conversation_id
        for event in events
        if event.payload.kind == "chat.conversation.created"
        and event.payload.conversation_type == "dm"
    }
    corrections = [
        event
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.body == S5_DM_CORRECTION
    ]
    check(
        f"three calendar settings {calendar_says}; the correction lives "
        "only in a DM at ts="
        + (str(int(corrections[0].time)) if corrections else "<missing>"),
        len(hearings) == 3
        and calendar_says == ["2026-04-28", "2026-05-20", "2026-06-18"]
        and len(corrections) == 1
        and _event_date(corrections[0]) == "2026-06-11"
        and corrections[0].payload.conversation_id in dm_ids,
    )
    dm_messages = [
        event
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.conversation_id in dm_ids
    ]
    check(
        f"DM fabric: {len(dm_ids)} DM conversations carrying "
        f"{len(dm_messages)} messages (need >= 8 threads, >= 1200 messages "
        "so an end-to-end skim costs real turns)",
        len(dm_ids) >= 8 and len(dm_messages) >= 1200,
    )
    thread = [
        event
        for event in dm_messages
        if corrections
        and event.payload.conversation_id == corrections[0].payload.conversation_id
    ]
    position = next(
        (
            index
            for index, event in enumerate(thread)
            if event.payload.body == S5_DM_CORRECTION
        ),
        -1,
    )
    check(
        f"the correction is buried mid-stream in a {len(thread)}-message DM "
        f"(position {position}: >= 200 before it, >= 40 after it)",
        len(thread) >= 350 and position >= 200 and len(thread) - 1 - position >= 40,
    )
    public_chats = [
        event.payload.body
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.conversation_id not in dm_ids
    ]
    all_email_bodies = [
        event.payload.body
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
    ]
    check(
        "no public channel, email, or calendar entry carries the operative date",
        not any(
            "June 25" in text or "the 25th" in text
            for text in (*public_chats, *all_email_bodies)
        )
        and "2026-06-25" not in calendar_says,
    )
    recaps = [
        event
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and event.payload.subject == S5_RECAP_SUBJECT
    ]
    check(
        "a post-correction recap email restates the superseded June 18 date "
        "and carries the clerk-call breadcrumb (fair pointer to the DM window)",
        bool(corrections)
        and len(recaps) == 1
        and _event_date(recaps[0]) == "2026-06-16"
        and "June 18" in recaps[0].payload.body
        and int(recaps[0].time) > int(corrections[0].time)
        and "clerk" in recaps[0].payload.body
        and "we'll confirm" in recaps[0].payload.body,
    )

    print("Fabric realism:")
    _audit_fabric(events, check)

    print("Round-6 reconciliation sets:")
    histories: dict[str, list[tuple[int, str, str]]] = {}
    doc_titles: dict[str, str] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, DocumentCreatedPayload):
            doc_titles[payload.document_id] = payload.title
            histories.setdefault(payload.title, []).append(
                (1, payload.content, _event_date(event))
            )
        elif isinstance(payload, DocumentRevisedPayload):
            histories[doc_titles[payload.document_id]].append(
                (payload.revision, payload.content, _event_date(event))
            )

    def email_texts() -> list[tuple[str, str, int]]:
        found = []
        for event in events:
            payload = event.payload
            if isinstance(payload, EmailMessagePayload):
                attachment_names = " ".join(
                    attachment.filename for attachment in payload.attachments
                )
                text = f"{payload.subject} {payload.body} {attachment_names}"
                found.append((text.lower(), _event_date(event), int(event.time)))
        return found

    emails = email_texts()
    public_chat_texts = [
        (event.payload.body.lower(), _event_date(event), int(event.time))
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.conversation_id not in dm_conversations
    ]

    # (a) S1 silent substantive NDA versions: v2+ whose operative text
    # changed (notices-only edits excluded) with no same-day email naming
    # the vendor or carrying the file.
    def strip_notices(content: str) -> str:
        sections = content.split("\n## ")
        kept = [sections[0]] + [
            section for section in sections[1:] if not section.startswith("Notices")
        ]
        return "\n## ".join(kept)

    nda_titles_all = (LEXIPOINT_NDA_TITLE, IRONCLAD_NDA_TITLE, *CONFORMING_NDA_TITLES)
    silent_substantive: list[tuple[str, int]] = []
    covered_substantive: list[tuple[str, int]] = []
    nonsubstantive_diffs: list[tuple[str, int]] = []
    nda_versions_reviewed = 0
    unchanged_nda_versions = 0
    nda_covering_emails = 0
    for title in nda_titles_all:
        vendor = title.split(" — ")[1].split()[0].lower()
        ordered = sorted(histories[title])
        for (_, previous, _), (version, current, day) in zip(
            ordered, ordered[1:], strict=False
        ):
            nda_versions_reviewed += 1
            if previous == current:
                unchanged_nda_versions += 1
                continue
            if strip_notices(previous) == strip_notices(current):
                nonsubstantive_diffs.append((title, version))
                continue
            covering_emails = [
                text
                for text, text_day, _ in emails
                if text_day == day and vendor in text
            ]
            covered = bool(covering_emails)
            nda_covering_emails += len(covering_emails)
            bucket = covered_substantive if covered else silent_substantive
            bucket.append((title, version))

    def short(pairs: list[tuple[str, int]]) -> list[tuple[str, int]]:
        return sorted((title.split(" — ")[1].split()[0], v) for title, v in pairs)

    check(
        f"silent substantive NDA versions are exactly "
        f"{short(silent_substantive)} (Trueline/Cobalt/Archway/Summit v3)",
        short(silent_substantive)
        == [("Archway", 3), ("Cobalt", 3), ("Summit", 3), ("Trueline", 3)],
    )
    check(
        f"covered substantive NDA versions are exactly "
        f"{short(covered_substantive)} (LexiPoint/Ironclad v2, "
        "BayMark/Harborlight v3)",
        short(covered_substantive)
        == [("BayMark", 3), ("Harborlight", 3), ("Ironclad", 2), ("LexiPoint", 2)],
    )
    check(
        f"a real-but-nonsubstantive diff exists as near-miss noise "
        f"({short(nonsubstantive_diffs)})",
        short(nonsubstantive_diffs) == [("Brightwater", 3)],
    )
    check(
        "NDA version audit has 16 post-v1 saves: 8 substantive, "
        "1 notices-only, 7 unchanged, and 4 exact covering emails",
        nda_versions_reviewed == 16
        and len(silent_substantive) + len(covered_substantive) == 8
        and len(nonsubstantive_diffs) == 1
        and unchanged_nda_versions == 7
        and nda_covering_emails == 4,
    )

    # (b) unreviewed revisions: v2+ of any multi-version document whose
    # save day carries no email or public-channel message with one of the
    # document's mention markers.
    unreviewed: list[tuple[str, int]] = []
    revisions_reviewed = 0
    covered_revisions = 0
    covering_communications = 0
    for title, markers in DOC_MENTION_MARKERS.items():
        ordered = sorted(histories[title])
        if len(ordered) < 2:
            continue
        for version, _, day in ordered[1:]:
            email_matches = [
                text
                for text, text_day, _ in emails
                if text_day == day and any(marker in text for marker in markers)
            ]
            chat_matches = [
                text
                for text, text_day, _ in public_chat_texts
                if text_day == day and any(marker in text for marker in markers)
            ]
            mentioned = bool(email_matches or chat_matches)
            revisions_reviewed += 1
            covering_communications += len(email_matches) + len(chat_matches)
            if mentioned:
                covered_revisions += 1
            else:
                unreviewed.append((title, version))
    check(
        "revision evidence ledger has 57 post-v1 saves, 52 covered, "
        "5 unreviewed, and 53 exact citations",
        revisions_reviewed == 57
        and covered_revisions == 52
        and len(unreviewed) == 5
        and covering_communications == 53,
    )
    check(
        f"unreviewed revisions are exactly {sorted(unreviewed)} "
        "(BayMark v2, Archway v2, hold v2, Lumen agreement v4, SOW v3)",
        sorted(unreviewed)
        == [
            ("Litigation Hold Notice (Template)", 2),
            (ARCHWAY_NDA_TITLE, 2),
            (BAYMARK_NDA_TITLE, 2),
            (LUMEN_AGREEMENT_TITLE, 4),
            (LUMEN_SOW_TITLE, 3),
        ],
    )
    multi_titles = {title for title, v in histories.items() if len(v) >= 2}
    check(
        f"every multi-version document carries a mention rule "
        f"({len(multi_titles)} docs)",
        multi_titles == set(DOC_MENTION_MARKERS),
    )

    # (c) billing hygiene: every billable timekeeper-day is classified by
    # sent communication and same-matter other-person work evidence.
    time_entries = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and _event_date(event) <= LEGACY_AUDIT_END
    ]
    billable_entries = [event for event in time_entries if event.payload.billable]
    sent_person_days = {
        (event.payload.sender, _event_date(event))
        for event in events
        if isinstance(event.payload, EmailMessagePayload | ChatMessagePayload)
        and _event_date(event) <= LEGACY_AUDIT_END
    }
    work_participants: dict[tuple[str, str], set[str]] = {}
    for event in time_entries:
        work_participants.setdefault(
            (event.payload.ticket_id, _event_date(event)), set()
        ).add(event.payload.person_id)
    for event in events:
        if (
            isinstance(event.payload, TicketCommentedPayload)
            and _event_date(event) <= LEGACY_AUDIT_END
        ):
            work_participants.setdefault(
                (event.payload.ticket_id, _event_date(event)), set()
            ).add(event.payload.actor)
    billable_person_days: dict[tuple[str, str], list[Event]] = {}
    for event in billable_entries:
        billable_person_days.setdefault(
            (_event_date(event), event.payload.person_id), []
        ).append(event)
    billing_dispositions: Counter[str] = Counter()
    anomalous_billing_entries = 0
    corroborated_billing_entries = 0
    for (entry_day, person), person_entries in billable_person_days.items():
        corroborated = [
            event
            for event in person_entries
            if work_participants[(event.payload.ticket_id, entry_day)] - {person}
        ]
        corroborated_billing_entries += len(corroborated)
        if (person, entry_day) in sent_person_days:
            billing_dispositions["cleared_by_communication"] += 1
        elif corroborated:
            billing_dispositions["anomalous"] += 1
            anomalous_billing_entries += len(corroborated)
        else:
            billing_dispositions["cleared_no_corroboration"] += 1
    check(
        "billing hygiene workpaper has 4,233 billable entries across 655 "
        "person-days, with 3,786 entries carrying same-day corroboration",
        len(billable_entries) == 4_233
        and len(billable_person_days) == 655
        and corroborated_billing_entries == 3_786,
    )
    check(
        "billing person-days split 637 communication-cleared, 15 silent "
        "without corroboration, and 3 anomalous carrying 18 affected entries",
        billing_dispositions
        == {
            "cleared_by_communication": 637,
            "cleared_no_corroboration": 15,
            "anomalous": 3,
        }
        and anomalous_billing_entries == 18,
    )

    # (d) unanswered client emails on the Cascadia engagement: thread
    # anti-join — no later in-thread reply from a firm-side sender.
    internal_people = {
        event.payload.person_id
        for event in events
        if event.payload.kind == "person.record"
        and event.payload.affiliation == "internal"
    }
    mail_events = [
        event for event in events if isinstance(event.payload, EmailMessagePayload)
    ]
    client_mail = [
        event
        for event in mail_events
        if event.payload.sender == "per-tom-hollis"
        and "Cascadia" in event.payload.subject
    ]
    unanswered_days = sorted(
        _event_date(event)
        for event in client_mail
        if not any(
            other.payload.thread_id == event.payload.thread_id
            and int(other.time) > int(event.time)
            and other.payload.sender in internal_people
            for other in mail_events
        )
    )
    check(
        f"exactly 4 client emails were never answered in-thread "
        f"({unanswered_days}); the rest drew firm replies "
        f"({len(client_mail)} client emails total)",
        unanswered_days == ["2026-04-24", "2026-05-06", "2026-05-20", "2026-06-08"]
        and len(client_mail) >= 9,
    )

    # (e) stale calendar references: communications citing a superseded
    # hearing date after its supersession record, negations excluded.
    supersession_times = {
        "2026-04-28": None,
        "2026-05-20": None,
        "2026-06-18": None,
    }
    for event in mail_events:
        if (
            "hearing setting" in event.payload.subject
            and _event_date(event) == "2026-04-17"
        ):
            supersession_times["2026-04-28"] = int(event.time)
        if (
            "hearing setting" in event.payload.subject
            and _event_date(event) == "2026-05-13"
        ):
            supersession_times["2026-05-20"] = int(event.time)
    if corrections:
        supersession_times["2026-06-18"] = int(corrections[0].time)
    arroyo_tokens = ("arroyo", "dept. 511", "fruitvale")
    date_forms = {
        "2026-04-28": ("april 28", "the 28th"),
        "2026-05-20": ("may 20", "the 20th"),
        "2026-06-18": ("june 18", "the 18th"),
    }
    stale: list[tuple[str, str]] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, EmailMessagePayload):
            text = f"{payload.subject} {payload.body}".lower()
            kind = "email"
        elif isinstance(payload, ChatMessagePayload):
            text = payload.body.lower()
            kind = "chat"
        else:
            continue
        for superseded, forms in date_forms.items():
            cutover = supersession_times[superseded]
            if cutover is None or int(event.time) <= cutover:
                continue
            if not any(token in text for token in arroyo_tokens):
                continue
            hit_forms = [form for form in forms if form in text]
            if not hit_forms:
                continue
            if any(f"not {form}" in text for form in hit_forms):
                continue
            stale.append((kind, _event_date(event)))
    check(
        f"stale citations of superseded hearing dates are exactly {sorted(stale)}",
        sorted(stale)
        == [
            ("chat", "2026-05-15"),
            ("chat", "2026-06-15"),
            ("email", "2026-04-21"),
            ("email", "2026-06-12"),
            ("email", "2026-06-16"),
        ],
    )

    return failures


def run_check(
    seed: Seed, *, day_count: int | None, texts: Mapping[str, str] | None
) -> int:
    def build_bytes() -> bytes:
        with TemporaryDirectory(prefix="hartwell-check-") as tmp:
            return build_world(
                Path(tmp), seed, day_count=day_count, texts=texts
            ).read_bytes()

    first, second = build_bytes(), build_bytes()
    if first != second:
        print("determinism check FAILED: two builds differ", file=sys.stderr)
        return 1
    print(f"determinism check passed: {len(first)} identical bytes")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out/hartwell"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--days",
        default=str(PILOT_DAYS),
        help="number of calendar days, or 'all' for the full directed history",
    )
    parser.add_argument(
        "--content-cache",
        type=Path,
        default=Path("out/hartwell/content-cache"),
        help="LM content cache directory (full mode only)",
    )
    parser.add_argument("--max-lm-calls", type=int, default=2500)
    parser.add_argument(
        "--check",
        action="store_true",
        help="build twice into temp dirs and compare bytes",
    )
    args = parser.parse_args(argv)
    seed = Seed(root=args.seed)
    full = args.days == "all"
    day_count = None if full else int(args.days)

    texts: dict[str, str] | None = None
    if full:
        if args.check:
            store = ContentStore(args.content_cache)
            missing = missing_content(store, model=DEFAULT_MODEL, seed=seed)
            if missing:
                print(
                    f"--check needs a warmed content cache; {len(missing)} "
                    "pieces missing",
                    file=sys.stderr,
                )
                return 1
        texts, lm_calls, usage = asyncio.run(
            _resolve_texts(args.content_cache, seed, max_calls=args.max_lm_calls)
        )
        print(
            f"content: {len(texts)} pieces, {lm_calls} LM calls, "
            f"usage {usage.prompt_tokens}p/{usage.completion_tokens}c tokens"
        )

    if args.check:
        return run_check(seed, day_count=day_count, texts=texts)

    log_path = build_world(args.out, seed, day_count=day_count, texts=texts)
    bundle_name = "bundle" if full else "pilot-bundle"
    bundle = materialize(log_path, args.out / bundle_name)
    print_summary(log_path, by_month=full)
    print(
        f"{bundle.event_count} events -> {bundle.bundle} "
        f"({bundle.document_files} document files)"
    )
    if full:
        return audit(log_path, bundle.bundle / "state")
    return 0


if __name__ == "__main__":
    sys.exit(main())
