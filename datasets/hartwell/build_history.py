"""Build the Hartwell & Marsh history: genesis plus procedural workdays,
with the five storyline arcs directed onto their dates in full mode.

    uv run python datasets/hartwell/build_history.py [--out out/hartwell]
        [--seed 42] [--days 5|all] [--check]

Pilot mode (``--days N``) is fully offline: procedural traffic only,
projected into ``pilot-workspace/``. Full mode (``--days all``) authors
storyline prose through the content cache (LM on cache miss, hard-capped),
builds all 87 workdays, validates, materializes into ``workspace/`` (seat
unset), prints per-month tag counts, and audits the storyline evidence.
``--check`` builds twice into temporary directories and fails unless the
bytes are identical; in full mode it requires a warmed content cache.
"""

import argparse
import asyncio
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping
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
from workbench.core.events.tickets import TicketCommentedPayload, TicketUpdatedPayload
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.environment import materialize
from workbench.simulation.chronicle.builder import Chronicle
from workbench.simulation.chronicle.content import ContentStore
from workbench.simulation.chronicle.minter import minter_from_events
from workbench.simulation.chronicle.procedural import ProceduralCast, procedural_day
from workbench.simulation.lm.budget import BudgetedLM
from workbench.simulation.lm.fake import FakeLM
from workbench.simulation.lm.openrouter import DEFAULT_MODEL, OpenRouterLM
from workbench.tools import check_coherence
from workbench.workplaces.hartwell import WINDOW, build_genesis, procedural_cast
from workbench.workplaces.hartwell.storylines import (
    ARCHWAY_NDA_TITLE,
    ARROYO_HEARING_TITLE,
    BAYMARK_NDA_TITLE,
    CASCADIA_LETTER_TITLE,
    INDEMNITY_PARAGRAPH,
    IRONCLAD_NDA_TITLE,
    LEXIPOINT_NDA_TITLE,
    LUMEN_AGREEMENT_TITLE,
    LUMEN_SOW_TITLE,
    PLAYBOOK_TITLE,
    S1_IRONCLAD_THREAD_REPLY,
    S2_CUTOFF_CHAT,
    S2_TICKET,
    S4_CLOSED_DATE,
    S4_TICKET,
    S5_DM_CORRECTION,
    S5_RECAP_SUBJECT,
    StorylineDirector,
    author_content,
    missing_content,
)

PILOT_WORKDAYS = 5


def build_world(
    out_dir: Path,
    seed: Seed,
    *,
    day_count: int | None = PILOT_WORKDAYS,
    texts: Mapping[str, str] | None = None,
) -> Path:
    """``day_count=None`` builds every workday; ``texts`` enables storylines."""

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

    workdays = WINDOW.workdays()
    if day_count is not None:
        workdays = workdays[:day_count]
    for day_index in workdays:
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
                minter=minter,
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
    for title in (BAYMARK_NDA_TITLE, ARCHWAY_NDA_TITLE):
        conforming = dict(docs[title])
        check(
            f"distractor NDA conforms in every version: {title.split(' — ')[1]}",
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
        f"diligence spike after Apr 3: {len(spike)} entries, "
        f"{total_minutes} min joins to the May 8 dispute email",
        len(spike) >= 5 and total_minutes > 600 and len(dispute) == 1,
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
        f"{len(decoys)} near-miss diligence entries before the cutoff",
        len(decoys) >= 3,
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
        f"reaction counts decline across the arc: {counts_in_order}",
        len(cascadia_chats) >= 5
        and counts_in_order[0] == max(counts_in_order)
        and counts_in_order[-2:] == [0, 0],
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
        "a post-correction recap email restates the superseded June 18 date",
        bool(corrections)
        and len(recaps) == 1
        and _event_date(recaps[0]) == "2026-06-16"
        and "June 18" in recaps[0].payload.body
        and int(recaps[0].time) > int(corrections[0].time),
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
        default=str(PILOT_WORKDAYS),
        help="number of workdays, or 'all' for the full directed history",
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
    workspace_name = "workspace" if full else "pilot-workspace"
    workspace = materialize(log_path, args.out / workspace_name)
    print_summary(log_path, by_month=full)
    print(
        f"{workspace.event_count} events -> {workspace.workspace} "
        f"({workspace.document_files} document files)"
    )
    if full:
        return audit(log_path, workspace.workspace / "state")
    return 0


if __name__ == "__main__":
    sys.exit(main())
