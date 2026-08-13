"""Build the Calder & Finch history: genesis plus procedural workdays
with the five directed arcs, fully offline — no LM, no cache, no network.

    uv run python datasets/calder/build_history.py [--out out/calder]
        [--seed 42] [--days 10|all] [--check]

Pilot mode (``--days N``) builds the first N calendar days into
``pilot-bundle/``. Full mode (``--days all``) builds all 194 calendar
days — weekends and observed holidays included, at their own reduced
rates — validates, materializes into ``bundle/`` (seat unset), prints
per-month tag counts, audits the fabric and the arcs, and writes
``metrics.json`` with build timings. ``--check`` builds twice into
temporary directories and fails unless the bytes are identical.
"""

import argparse
import json
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.core.events import Event
from workbench.core.events.chat import ChatMessagePayload, ChatReactionAddedPayload
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.tickets import TicketUpdatedPayload
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.environment import materialize
from workbench.simulation.chronicle.builder import Chronicle
from workbench.simulation.chronicle.procedural import procedural_day
from workbench.tools import check_coherence
from workbench.workplaces.calder import (
    ARRIVAL,
    ARRIVAL_DATE,
    FEDERAL_HOLIDAYS_2026,
    VOICE,
    WINDOW,
    build_genesis,
    day_profile,
    procedural_cast,
)
from workbench.workplaces.calder.arcs import (
    DRAFT_FS_TITLE,
    PBC_LIST_TITLE,
    CalderDirector,
)

PILOT_DAYS = 10


def build_world(
    out_dir: Path, seed: Seed, *, day_count: int | None = PILOT_DAYS
) -> Path:
    """``day_count=None`` builds the whole window."""

    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "world.jsonl"
    if log_path.exists():
        log_path.unlink()

    genesis = build_genesis(seed)
    minter = genesis.minter
    director = CalderDirector(genesis, seed, minter)
    before = procedural_cast(genesis)
    after = procedural_cast(genesis, arrival_dm_id=director.arrival_dm_id)

    chronicle = Chronicle(log_path, window=WINDOW)
    chronicle.write_genesis(genesis.events)

    span = WINDOW.day_count if day_count is None else min(day_count, WINDOW.day_count)
    for day_index in range(span):
        day = WINDOW.iso_date(day_index)
        cast = after if day > ARRIVAL_DATE else before
        drafts = list(
            procedural_day(
                seed=seed,
                window=WINDOW,
                day_index=day_index,
                cast=cast,
                voice=VOICE,
                minter=minter,
                profile=day_profile(seed, day_index),
            )
        )
        drafts.extend(director.drafts_for(day, minter))
        drafts.sort(key=lambda draft: int(draft.at))
        chronicle.add_procedural_day(day_index, drafts)
    chronicle.finish()
    return log_path


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


def _event_date(event: Event) -> str:
    return WINDOW.iso_date(int(event.time) // 86_400)


def _audit_fabric(events: list[Event], check) -> None:
    """Gate the record against the degeneracy an expert reader notices."""

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
        f"{len(dms)} messages (>= 1200)",
        len(set(dms)) >= 1200,
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
        f"{len(entries)} entries (>= 700)",
        len(narratives) >= 700,
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
        len(rated) == len(entries) and bool(non_billable),
    )

    workdays = [WINDOW.iso_date(index) for index in WINDOW.workdays()]
    hours: Counter[str] = Counter()
    for event in entries:
        if event.payload.billable:
            hours[event.payload.person_id] += event.payload.minutes
    per_day = {
        person: minutes / 60 / len(workdays) for person, minutes in hours.items()
    }
    # Maya's average is diluted by the pre-arrival stretch; measure her
    # against her own tenure instead.
    tenure_workdays = [day for day in workdays if day > ARRIVAL_DATE]
    if ARRIVAL.person_id in per_day:
        per_day[ARRIVAL.person_id] = (
            hours[ARRIVAL.person_id] / 60 / len(tenure_workdays)
        )
    low, high = min(per_day.values()), max(per_day.values())
    average = sum(per_day.values()) / len(per_day)
    check(
        f"fee earners bill {average:.2f} hrs/workday on average "
        f"({low:.2f}-{high:.2f} across {len(per_day)}), inside 5.0-7.0",
        5.0 <= average <= 7.0 and low >= 4.0 and high <= 8.2,
    )

    by_matter = Counter()
    for event in entries:
        by_matter[event.payload.ticket_id] += event.payload.minutes
    spread = max(by_matter.values()) / min(by_matter.values())
    check(
        f"per-engagement hours track complexity: {spread:.1f}x between the "
        "heaviest and lightest engagement (>= 3.5x)",
        spread >= 3.5,
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
        f"holiday events, {share:.1%} of the record (1%-9%)",
        0.01 <= share <= 0.09
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


def _audit_arcs(events: list[Event], check) -> None:
    """The directed storylines landed exactly as scripted."""

    maya = ARRIVAL.person_id
    records = [
        event
        for event in events
        if event.payload.kind == "person.record" and event.payload.person_id == maya
    ]
    check(
        "Maya's person.record lands exactly once, on "
        + (_event_date(records[0]) if records else "<missing>"),
        len(records) == 1 and _event_date(records[0]) == ARRIVAL_DATE,
    )

    conversations = {
        event.payload.conversation_id: event.payload.conversation_type
        for event in events
        if event.payload.kind == "chat.conversation.created"
    }
    maya_chats = Counter(
        conversations[event.payload.conversation_id]
        for event in events
        if isinstance(event.payload, ChatMessagePayload)
        and event.payload.sender == maya
    )
    maya_time = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and event.payload.person_id == maya
    ]
    maya_mail = [
        event
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and (event.payload.sender == maya or maya in event.payload.to)
    ]
    check(
        f"Maya is channel-silent but present: {maya_chats.get('channel', 0)} "
        f"channel posts, {maya_chats.get('dm', 0)} DMs, {len(maya_mail)} "
        f"emails, {len(maya_time)} time entries",
        maya_chats.get("channel", 0) == 0
        and maya_chats.get("dm", 0) >= 20
        and len(maya_mail) >= 10
        and len(maya_time) >= 50
        and all(_event_date(event) >= ARRIVAL_DATE for event in maya_time),
    )

    packages = [
        event
        for event in events
        if isinstance(event.payload, DocumentCreatedPayload)
        and event.payload.title.startswith("Reporting Package")
    ]
    check(
        f"the close cycle produced {len(packages)} spreadsheet reporting "
        "packages (7 cycles x 4 clients)",
        len(packages) == 28
        and all(event.payload.content_format == "spreadsheet" for event in packages),
    )
    attached = [
        event
        for event in events
        if isinstance(event.payload, EmailMessagePayload) and event.payload.attachments
    ]
    check(
        f"{len(attached)} emails carry attachments (packages, letters, "
        "PBC list, draft FS; >= 34)",
        len(attached) >= 34,
    )

    revisions = [
        event for event in events if isinstance(event.payload, DocumentRevisedPayload)
    ]
    pbc_docs = [
        event
        for event in events
        if isinstance(event.payload, DocumentCreatedPayload)
        and event.payload.title == PBC_LIST_TITLE
    ]
    pbc_revs = [
        event.payload.revision
        for event in revisions
        if pbc_docs and event.payload.document_id == pbc_docs[0].payload.document_id
    ]
    check(
        f"the PBC list is revised twice ({pbc_revs})",
        len(pbc_docs) == 1 and pbc_revs == [2, 3],
    )
    check(
        "the draft financial statements ship as a formatted document",
        any(
            isinstance(event.payload, DocumentCreatedPayload)
            and event.payload.title == DRAFT_FS_TITLE
            and event.payload.content_format == "formatted"
            for event in events
        ),
    )

    closes = [
        event
        for event in events
        if isinstance(event.payload, TicketUpdatedPayload)
        and any(
            change.field == "status" and change.new == "closed"
            for change in event.payload.changes
        )
    ]
    check(
        "the audit engagement closes on "
        + (_event_date(closes[0]) if closes else "<missing>"),
        len(closes) == 1 and _event_date(closes[0]) == "2026-06-30",
    )

    extensions = [
        event
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and "extension filed" in event.payload.subject
    ]
    check(
        f"exactly 2 extension confirmations on April 15 "
        f"({sorted(_event_date(event) for event in extensions)})",
        len(extensions) == 2
        and all(_event_date(event) == "2026-04-15" for event in extensions),
    )

    estimates = [
        event
        for event in events
        if isinstance(event.payload, EmailMessagePayload)
        and "estimated payment reminder" in event.payload.subject
    ]
    check(
        f"{len(estimates)} quarterly estimate reminders across three rounds",
        len(estimates) == 8,
    )

    deadline_reactions = [
        event
        for event in events
        if isinstance(event.payload, ChatReactionAddedPayload)
        and _event_date(event) == "2026-04-15"
    ]
    check(
        f"deadline day celebrates: {len(deadline_reactions)} reactions on April 15",
        len(deadline_reactions) >= 6,
    )

    season = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and "2026-03-01" <= _event_date(event) <= "2026-04-15"
    ]
    off_season = [
        event
        for event in events
        if isinstance(event.payload, TimeLoggedPayload)
        and "2026-05-01" <= _event_date(event) <= "2026-06-15"
    ]
    season_days = sum(
        1
        for index in WINDOW.workdays()
        if "2026-03-01" <= WINDOW.iso_date(index) <= "2026-04-15"
    )
    off_days = sum(
        1
        for index in WINDOW.workdays()
        if "2026-05-01" <= WINDOW.iso_date(index) <= "2026-06-15"
    )
    season_rate = len(season) / season_days
    off_rate = len(off_season) / off_days
    check(
        f"filing season runs hotter than the shoulder: {season_rate:.1f} "
        f"vs {off_rate:.1f} entries per workday (>= 1.1x)",
        season_rate >= 1.1 * off_rate,
    )


def audit(log_path: Path, state_dir: Path) -> int:
    events = read_events(log_path)
    report = validate_events(events)
    print(f"validate_events: {'ok' if report.findings == () else report.findings[:5]}")
    findings = check_coherence(state_dir)
    print(f"check_coherence: {findings if findings else '()'}")
    failures = 0 if report.findings == () and not findings else 1

    def check(label: str, passed: bool) -> None:
        nonlocal failures
        print(f"  [{'ok' if passed else 'FAIL'}] {label}")
        if not passed:
            failures += 1

    print("Fabric realism:")
    _audit_fabric(events, check)
    print("Directed arcs:")
    _audit_arcs(events, check)
    return failures


def run_check(seed: Seed, *, day_count: int | None) -> int:
    def build_bytes() -> bytes:
        with TemporaryDirectory(prefix="calder-check-") as tmp:
            return build_world(Path(tmp), seed, day_count=day_count).read_bytes()

    started = time.perf_counter()
    first, second = build_bytes(), build_bytes()
    elapsed = time.perf_counter() - started
    if first != second:
        print("determinism check FAILED: two builds differ", file=sys.stderr)
        return 1
    print(
        f"determinism check passed: {len(first)} identical bytes "
        f"(two builds in {elapsed:.1f}s)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out/calder"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--days",
        default=str(PILOT_DAYS),
        help="number of calendar days, or 'all' for the full six months",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="build twice into temp dirs and compare bytes",
    )
    args = parser.parse_args(argv)
    seed = Seed(root=args.seed)
    full = args.days == "all"
    day_count = None if full else int(args.days)

    if args.check:
        return run_check(seed, day_count=day_count)

    metrics: dict[str, object] = {
        "seed": args.seed,
        "calendar_days": WINDOW.day_count if full else day_count,
    }
    started = time.perf_counter()
    log_path = build_world(args.out, seed, day_count=day_count)
    metrics["build_seconds"] = round(time.perf_counter() - started, 3)

    started = time.perf_counter()
    events = read_events(log_path)
    report = validate_events(events)
    metrics["validate_seconds"] = round(time.perf_counter() - started, 3)
    if not report.ok:
        print(f"validation failed: {report.findings[:5]}", file=sys.stderr)
        return 1
    metrics["events"] = len(events)
    metrics["bytes"] = log_path.stat().st_size
    metrics["events_per_second"] = round(len(events) / metrics["build_seconds"], 1)

    bundle_name = "bundle" if full else "pilot-bundle"
    started = time.perf_counter()
    bundle = materialize(log_path, args.out / bundle_name)
    metrics["materialize_seconds"] = round(time.perf_counter() - started, 3)
    metrics["document_files"] = bundle.document_files
    metrics["skipped_renders"] = list(bundle.skipped_renders)
    metrics["bundle_bytes"] = sum(
        item.stat().st_size for item in bundle.bundle.rglob("*") if item.is_file()
    )

    print_summary(log_path, by_month=full)
    print(
        f"{bundle.event_count} events -> {bundle.bundle} "
        f"({bundle.document_files} document files, "
        f"{len(bundle.skipped_renders)} renders skipped)"
    )
    (args.out / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    print(f"metrics -> {args.out / 'metrics.json'}: {json.dumps(metrics)}")
    if full:
        return audit(log_path, bundle.bundle / "state")
    return 0


if __name__ == "__main__":
    sys.exit(main())
