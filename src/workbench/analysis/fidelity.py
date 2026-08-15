"""Measure a generated world against the committed distribution bands.

The v1 realism review was a pile of one-off SQL. This module is that
work made repeatable: it reads a materialized bundle's databases (and,
where a fact only exists upstream, the world log), computes every metric
named in ``docs/epochs/v2/bands.json``, and reports observed-vs-band with
a verdict per metric.

A metric that cannot be computed because its *surface does not exist
yet* returns ``None`` and reports ABSENT — which is itself a finding, and
exactly what v1 looks like for billing, tax, and the client book.
"""

import json
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from workbench.analysis import stats

BANDS_PATH = Path("docs/epochs/v2/bands.json")
BUSY_SEASON_MONTHS = (2, 3, 4)
SUMMER_MONTHS = (6, 7)
WORK_START_HOUR = 8
WORK_END_HOUR = 18


class Band(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    surface: str
    min: float | None = None
    max: float | None = None
    v1: float | None = None

    def verdict(self, observed: float | None) -> str:
        if observed is None:
            return "ABSENT"
        if self.min is not None and observed < self.min:
            return "FAIL"
        if self.max is not None and observed > self.max:
            return "FAIL"
        return "PASS"

    def rendered(self) -> str:
        if self.min is not None and self.max is not None:
            return f"{self.min:g} – {self.max:g}"
        if self.min is not None:
            return f"≥ {self.min:g}"
        if self.max is not None:
            return f"≤ {self.max:g}"
        return "—"


@dataclass(frozen=True, slots=True)
class Result:
    metric: str
    band: Band
    observed: float | None
    verdict: str
    detail: str = ""


def load_bands(path: Path = BANDS_PATH) -> dict[str, Band]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {key: Band(**value) for key, value in raw["bands"].items()}


# --- helpers -----------------------------------------------------------


def _connect(state_dir: Path, name: str) -> sqlite3.Connection | None:
    path = state_dir / f"{name}.db"
    if not path.exists():
        return None
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _epoch(connection: sqlite3.Connection) -> date:
    row = connection.execute("SELECT value FROM meta WHERE key='epoch'").fetchone()
    return datetime.fromisoformat(row[0]).date()


def _as_date(epoch: date, seconds: int) -> date:
    return epoch + timedelta(seconds=seconds)


def _share(count: int, total: int) -> float | None:
    return None if total == 0 else count / total


def _safe(values: Sequence[float], fn, *args, **kwargs) -> float | None:
    if not values:
        return None
    try:
        return fn(values, *args, **kwargs)
    except ValueError, ZeroDivisionError:
        return None


def _internal(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT person_id FROM people WHERE affiliation='internal'"
        )
    }


# --- per-surface measurement -------------------------------------------


def measure_email(state_dir: Path) -> dict[str, float | None]:
    connection = _connect(state_dir, "gmail")
    if connection is None:
        return {}
    epoch = _epoch(connection)
    internal = _internal(connection)
    messages = connection.execute(
        "SELECT message_id, thread_id, in_reply_to, sender, body, time FROM messages"
    ).fetchall()
    if not messages:
        return {}
    by_id = {row[0]: row for row in messages}
    recipients: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for message_id, person_id, kind in connection.execute(
        "SELECT message_id, person_id, kind FROM recipients"
    ):
        recipients[message_id].append((person_id, kind))
    with_attachment = {
        row[0] for row in connection.execute("SELECT message_id FROM attachments")
    }

    days = {_as_date(epoch, row[5]) for row in messages}
    depths = Counter(row[1] for row in messages)
    depth_values = [float(v) for v in depths.values()]

    external_total = external_attached = internal_total = internal_attached = 0
    single_recipient = cc_carrying = internal_only = 0
    for row in messages:
        message_id, _, _, sender, _, _ = row
        people = recipients.get(message_id, [])
        tos = [p for p, kind in people if kind == "to"]
        ccs = [p for p, kind in people if kind == "cc"]
        parties = {sender, *(p for p, _ in people)}
        is_internal = parties <= internal
        if len(tos) == 1 and not ccs:
            single_recipient += 1
        if ccs:
            cc_carrying += 1
        if is_internal:
            internal_only += 1
            internal_total += 1
            internal_attached += message_id in with_attachment
        else:
            external_total += 1
            external_attached += message_id in with_attachment

    latencies = [
        float(row[5] - by_id[row[2]][5])
        for row in messages
        if row[2] and row[2] in by_id and row[5] >= by_id[row[2]][5]
    ]
    words = [float(len(row[4].split())) for row in messages]
    bodies = [row[4] for row in messages]
    by_sender = Counter(row[3] for row in messages)

    measurements: dict[str, float | None] = {
        "email.per_day": len(messages) / max(1, len(days)),
        "email.thread_depth_median": _safe(depth_values, stats.quantile, 0.5),
        "email.thread_depth_p90": _safe(depth_values, stats.quantile, 0.9),
        "email.thread_depth_max": max(depth_values),
        "email.attachment_rate_external": _share(external_attached, external_total),
        "email.attachment_rate_internal": _share(internal_attached, internal_total),
        "email.body_words_median": _safe(words, stats.quantile, 0.5),
        "email.body_words_p95": _safe(words, stats.quantile, 0.95),
        "email.single_recipient_share": _share(single_recipient, len(messages)),
        "email.cc_share": _share(cc_carrying, len(messages)),
        "email.internal_share": _share(internal_only, len(messages)),
        "email.machine_share": _share(
            sum(1 for row in messages if row[3] not in internal and row[3] == "system"),
            len(messages),
        ),
        "email.distinct_body_share": len(set(bodies)) / len(bodies),
        "email.gini_by_person": _safe(list(by_sender.values()), stats.gini),
        "email.top1_share_by_person": _safe(list(by_sender.values()), stats.top_share),
    }
    if words:
        measurements["email.body_words_lognormal_p"] = _pvalue(
            stats.ks_lognormal, words
        )
    if latencies:
        hours = [value / 3600.0 for value in latencies]
        measurements |= {
            "email.reply_latency_median_hours": stats.quantile(hours, 0.5),
            "email.reply_latency_p95_hours": stats.quantile(hours, 0.95),
            "email.reply_latency_over_72h_share": sum(
                1 for value in hours if value > 72
            )
            / len(hours),
            "email.reply_latency_lognormal_p": _pvalue(stats.ks_lognormal, hours),
            "email.reply_latency_uniform_p": _pvalue(stats.ks_uniform, hours),
        }
    connection.close()
    return measurements


def _pvalue(test, sample: Sequence[float]) -> float | None:
    positive = [value for value in sample if value > 0]
    if len(positive) < 8:
        return None
    try:
        return test(positive)[1]
    except ValueError:
        return None


def measure_slack(state_dir: Path) -> dict[str, float | None]:
    connection = _connect(state_dir, "slack")
    if connection is None:
        return {}
    epoch = _epoch(connection)
    messages = connection.execute(
        "SELECT chat_message_id, conversation_id, reply_to, time FROM messages"
    ).fetchall()
    if not messages:
        return {}
    kinds = dict(
        connection.execute("SELECT conversation_id, kind FROM conversations").fetchall()
    )
    reacted = {
        row[0] for row in connection.execute("SELECT chat_message_id FROM reactions")
    }
    per_channel = Counter(row[1] for row in messages)
    replies = Counter(row[2] for row in messages if row[2])
    roots = [row[0] for row in messages if not row[2]]

    off_hours = busy_off = busy_total = 0
    for _, _, _, seconds in messages:
        when = _as_date(epoch, seconds)
        hour = (seconds % 86400) // 3600
        is_off = when.weekday() >= 5 or hour < WORK_START_HOUR or hour >= WORK_END_HOUR
        off_hours += is_off
        if when.month in BUSY_SEASON_MONTHS:
            busy_total += 1
            busy_off += is_off

    connection.close()
    return {
        "slack.live_channels": float(
            sum(1 for cid, count in per_channel.items() if count > 0)
        ),
        "slack.top_channel_share": _safe(list(per_channel.values()), stats.top_share),
        "slack.dm_share": _share(
            sum(1 for row in messages if kinds.get(row[1]) == "dm"), len(messages)
        ),
        "slack.threaded_reply_share": _share(
            sum(1 for root in roots if replies.get(root, 0) >= 2), len(roots)
        ),
        "slack.zero_reaction_share": _share(
            sum(1 for row in messages if row[0] not in reacted), len(messages)
        ),
        "slack.offhours_share": _share(off_hours, len(messages)),
        "slack.offhours_share_busy_season": _share(busy_off, busy_total),
        "slack.gini_by_channel": _safe(list(per_channel.values()), stats.gini),
    }


def measure_calendar(state_dir: Path, log: WorldLog | None) -> dict[str, float | None]:
    connection = _connect(state_dir, "calendar")
    if connection is None:
        return {}
    events = connection.execute(
        "SELECT calendar_event_id, start_time, end_time, status, summary "
        "FROM calendar_events"
    ).fetchall()
    responses = Counter(
        row[0]
        for row in connection.execute(
            "SELECT response_status FROM attendees"
        ).fetchall()
    )
    attendee_counts = Counter(
        row[0]
        for row in connection.execute(
            "SELECT calendar_event_id FROM attendees"
        ).fetchall()
    )
    connection.close()
    if not events:
        return {}
    total_responses = sum(responses.values())
    minutes = [(row[2] - row[1]) / 60.0 for row in events]
    common = sum(1 for value in minutes if value in (30.0, 60.0))
    tail = sum(1 for value in minutes if value in (15.0, 45.0, 90.0) or value > 90)
    cancelled = sum(1 for row in events if row[3] == "cancelled")
    # A recurring series shows up as repeated summaries at a fixed weekday.
    series = sum(
        1 for _, count in Counter(row[4] for row in events).items() if count > 3
    )

    measurements: dict[str, float | None] = {
        "calendar.rsvp_accepted": _share(responses.get("accepted", 0), total_responses),
        "calendar.rsvp_tentative": _share(
            responses.get("tentative", 0), total_responses
        ),
        "calendar.rsvp_declined": _share(responses.get("declined", 0), total_responses),
        "calendar.rsvp_needsaction": _share(
            responses.get("needsAction", 0), total_responses
        ),
        "calendar.duration_30_60_share": _share(common, len(minutes)),
        "calendar.duration_tail_share": _share(tail, len(minutes)),
        "calendar.recurrence_series": float(series),
        "calendar.cancellation_share": _share(cancelled, len(events)),
    }
    if log is not None:
        multi = [row[0] for row in events if attendee_counts.get(row[0], 0) >= 2]
        measurements["calendar.transcript_share_internal"] = _share(
            log.count("meeting.transcript"), len(multi)
        )
    return measurements


def measure_practice(state_dir: Path) -> dict[str, float | None]:
    """Time, engagements, and the client book, from the practice database."""

    connection = _connect(state_dir, "clio")
    if connection is None:
        return {}
    epoch = _epoch(connection)
    internal = _internal(connection)
    activities = connection.execute(
        "SELECT ticket_id, person, quantity_seconds, time, billable FROM activities"
    ).fetchall()
    matters = connection.execute("SELECT ticket_id, client_org FROM matters").fetchall()
    notes = Counter(
        row[0] for row in connection.execute("SELECT ticket_id FROM notes").fetchall()
    )
    connection.close()

    measurements: dict[str, float | None] = {
        "book.matters": float(len(matters)),
        "cross.matter_note_top1_share": _safe(list(notes.values()), stats.top_share),
    }
    clients = {row[1] for row in matters if row[1]}
    if clients:
        measurements["book.clients"] = float(len(clients))
        measurements["book.matters_per_client_mean"] = len(matters) / len(clients)
    if not activities:
        return measurements

    hours = [row[2] / 3600.0 for row in activities]
    billable_hours = [
        row[2] / 3600.0 for row in activities if row[4] in (1, True, None)
    ]
    days = {_as_date(epoch, row[3]) for row in activities}
    workdays = sorted(days)
    per_person_day: Counter[tuple[str, date]] = Counter()
    for row in activities:
        per_person_day[(row[1], _as_date(epoch, row[3]))] += 1
    # Every internal person on every workday, zeros included: the honest
    # denominator. v1's median lands at 0 precisely because most of the
    # roster never logged anything.
    grid = [
        float(per_person_day.get((person, day), 0))
        for person in internal
        for day in workdays
    ]
    by_matter = Counter()
    for row in activities:
        by_matter[row[0]] += row[2]
    client_hours: Counter[str] = Counter()
    matter_client = {row[0]: row[1] for row in matters}
    for ticket, seconds in by_matter.items():
        client = matter_client.get(ticket)
        if client:
            client_hours[client] += seconds

    measurements |= {
        "billing.total_hours_h1": sum(billable_hours),
        "billing.professionals_logging": float(len({row[1] for row in activities})),
        "billing.entries_per_person_day_median": _safe(grid, stats.quantile, 0.5),
        "billing.entries_per_person_day_p90": _safe(grid, stats.quantile, 0.9),
        "billing.duration_median_hours": _safe(hours, stats.quantile, 0.5),
        "billing.duration_p95_hours": _safe(hours, stats.quantile, 0.95),
        "billing.round_number_share": _safe(hours, stats.round_number_share, 0.5),
        "billing.duration_uniform_p": _pvalue(stats.ks_uniform, hours),
        "billing.nonbillable_share": _share(
            sum(1 for row in activities if row[4] in (0, False)), len(activities)
        ),
        "billing.hours_gini_by_matter": _safe(list(by_matter.values()), stats.gini),
    }
    if client_hours:
        measurements["book.client_gini"] = stats.gini(list(client_hours.values()))
        measurements["book.top10_fee_share"] = stats.top_share(
            list(client_hours.values()), k=10
        )
        dormant = sum(1 for value in client_hours.values() if value < 5 * 3600)
        measurements["book.dormant_client_share"] = _share(dormant, len(clients))
    return measurements


def measure_documents(state_dir: Path, log: WorldLog | None) -> dict[str, float | None]:
    connection = _connect(state_dir, "imanage")
    if connection is None:
        return {}
    documents = connection.execute(
        "SELECT document_id, extension, head_version FROM documents"
    ).fetchall()
    connection.close()
    if not documents:
        return {}
    extensions = Counter(row[1].lower().lstrip(".") for row in documents)
    chains = [float(row[2]) for row in documents]
    total = len(documents)
    measurements: dict[str, float | None] = {
        "documents.count": float(total),
        "documents.version_chain_p90": _safe(chains, stats.quantile, 0.9),
        "documents.version_chain_max": max(chains),
    }
    for name in ("xlsx", "docx", "pdf", "md", "pptx", "csv"):
        measurements[f"documents.format_{name}"] = extensions.get(name, 0) / total
    if log is not None:
        measurements["documents.persona_created_share"] = log.persona_created_share()
        measurements["documents.announced_attached_share"] = (
            log.attachment_promise_rate()
        )
    return measurements


def measure_cross(state_dir: Path) -> dict[str, float | None]:
    gmail = _connect(state_dir, "gmail")
    slack = _connect(state_dir, "slack")
    clio = _connect(state_dir, "clio")
    if gmail is None:
        return {}
    epoch = _epoch(gmail)
    internal = _internal(gmail)
    mail = gmail.execute("SELECT sender, body, time FROM messages").fetchall()

    weekend = {"busy": [0, 0], "summer": [0, 0]}
    for _, _, seconds in mail:
        when = _as_date(epoch, seconds)
        key = (
            "busy"
            if when.month in BUSY_SEASON_MONTHS
            else "summer"
            if when.month in SUMMER_MONTHS
            else None
        )
        if key:
            weekend[key][1] += 1
            weekend[key][0] += when.weekday() >= 5

    by_person_mail = Counter(row[0] for row in mail)
    lengths: dict[str, list[float]] = defaultdict(list)
    for sender, body, _ in mail:
        lengths[sender].append(float(len(body.split())))
    medians = [
        stats.quantile(values, 0.5)
        for sender, values in lengths.items()
        if sender in internal and len(values) >= 5
    ]
    gmail.close()

    measurements: dict[str, float | None] = {
        "cross.weekend_share_busy": _share(*weekend["busy"]),
        "cross.weekend_share_summer": _share(*weekend["summer"]),
    }
    if medians and min(medians) > 0:
        measurements["cross.persona_body_length_ratio"] = max(medians) / min(medians)

    if slack is not None and clio is not None:
        by_person_chat = Counter(
            row[0] for row in slack.execute("SELECT sender FROM messages")
        )
        by_person_hours: Counter[str] = Counter()
        for person, seconds in clio.execute(
            "SELECT person, quantity_seconds FROM activities"
        ):
            by_person_hours[person] += seconds
        people = sorted(internal)
        if len(people) >= 3:
            mail_series = [by_person_mail.get(person, 0) for person in people]
            chat_series = [by_person_chat.get(person, 0) for person in people]
            hour_series = [by_person_hours.get(person, 0) for person in people]
            pairs = [
                stats.spearman(mail_series, chat_series),
                stats.spearman(mail_series, hour_series),
                stats.spearman(chat_series, hour_series),
            ]
            measurements["cross.person_volume_spearman"] = sum(pairs) / len(pairs)
        # Per-engagement coupling: notes against logged time.
        notes = Counter(row[0] for row in clio.execute("SELECT ticket_id FROM notes"))
        hours_by_matter: Counter[str] = Counter()
        for ticket, seconds in clio.execute(
            "SELECT ticket_id, quantity_seconds FROM activities"
        ):
            hours_by_matter[ticket] += seconds
        tickets = sorted(set(notes) | set(hours_by_matter))
        if len(tickets) >= 3:
            measurements["cross.matter_volume_spearman"] = stats.spearman(
                [notes.get(ticket, 0) for ticket in tickets],
                [hours_by_matter.get(ticket, 0) for ticket in tickets],
            )
    if slack is not None:
        slack.close()
    if clio is not None:
        clio.close()
    return measurements


# --- world log (facts that only exist upstream) ------------------------


class WorldLog:
    """Cheap single-pass reader for the facts no database keeps."""

    def __init__(self, path: Path) -> None:
        self.tags: Counter[str] = Counter()
        self._documents: list[tuple[int, str]] = []
        self._attachment_promises = 0
        self._attachments = 0
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            tag = event.get("tag", "")
            self.tags[tag] += 1
            payload = event.get("payload", {})
            if tag == "document.created":
                self._documents.append(
                    (event.get("time", 0), payload.get("author", ""))
                )
            if tag == "email.message":
                body = payload.get("body", "").lower()
                if "attach" in body or "enclosed" in body:
                    self._attachment_promises += 1
                self._attachments += len(payload.get("attachments") or [])

    def count(self, tag: str) -> int:
        return self.tags.get(tag, 0)

    def persona_created_share(self) -> float | None:
        if not self._documents:
            return None
        # Genesis seeds land in the opening moments of day zero; anything
        # later was authored by a persona during the run.
        runtime = sum(1 for when, _ in self._documents if when > 3600)
        return runtime / len(self._documents)

    def attachment_promise_rate(self) -> float | None:
        if self._attachment_promises == 0:
            return None
        return min(1.0, self._attachments / self._attachment_promises)


# --- assembly ----------------------------------------------------------


def measure(state_dir: Path, log_path: Path | None = None) -> dict[str, float | None]:
    log = WorldLog(log_path) if log_path and Path(log_path).exists() else None
    measurements: dict[str, float | None] = {}
    measurements |= measure_email(state_dir)
    measurements |= measure_slack(state_dir)
    measurements |= measure_calendar(state_dir, log)
    measurements |= measure_practice(state_dir)
    measurements |= measure_documents(state_dir, log)
    measurements |= measure_cross(state_dir)
    return measurements


def evaluate(
    measurements: dict[str, float | None], bands: dict[str, Band]
) -> list[Result]:
    results = []
    for metric, band in bands.items():
        observed = measurements.get(metric)
        results.append(Result(metric, band, observed, band.verdict(observed)))
    return results


def summarize(results: Iterable[Result]) -> Counter[str]:
    return Counter(result.verdict for result in results)


def render_markdown(results: Sequence[Result], *, title: str, context: str) -> str:
    counts = summarize(results)
    lines = [
        f"# {title}",
        "",
        context,
        "",
        f"**{counts['PASS']} pass · {counts['FAIL']} fail · "
        f"{counts['ABSENT']} absent** of {len(results)} committed bands.",
        "",
        "ABSENT means the surface that metric measures does not exist in this "
        "world yet — a finding, not a skip.",
        "",
    ]
    by_surface: dict[str, list[Result]] = defaultdict(list)
    for result in results:
        by_surface[result.band.surface].append(result)
    for surface in sorted(by_surface):
        lines += [
            f"## {surface}",
            "",
            "| Metric | Band | Observed | v1 | Verdict |",
            "|---|---|---|---|---|",
        ]
        for result in by_surface[surface]:
            observed = "—" if result.observed is None else f"{result.observed:,.4g}"
            v1 = "—" if result.band.v1 is None else f"{result.band.v1:,.4g}"
            mark = {"PASS": "✅", "FAIL": "❌", "ABSENT": "⚪"}[result.verdict]
            lines.append(
                f"| {result.band.label} | {result.band.rendered()} | "
                f"{observed} | {v1} | {mark} {result.verdict} |"
            )
        lines.append("")
    return "\n".join(lines)
