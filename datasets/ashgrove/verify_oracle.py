"""Re-derive every oracle from the world log and report where it disagrees.

    uv run python datasets/ashgrove/verify_oracle.py
    uv run python datasets/ashgrove/verify_oracle.py --task work-product-review

Each reference solver reads the materialized ``state/*.db``. So does the
grader. So a wrong rule in a solver does not fail anything — it becomes the
answer key, and the first thing anyone hears about it is a frontier model
"missing" a criterion it actually got right.

That has now happened twice:

* ``engagement-time-allocation`` totalled the firm's hours by adding a
  hundred and ninety-seven already-rounded rows. 817.27 that way, 817.23
  from the entries. The instruction named neither, the oracle picked one,
  and an agent with every row correct lost 3.5 of 19 points on a coin toss.
* ``work-product-review`` keyed documents on title alone, and two of them
  were called "Single Audit Playbook". The reference solver scored 0.976
  against its own grader — the *ceiling* was 0.976, which for a while I
  reported as a model's error rate.

Both are invisible to any check that reads the same database twice. Both
fall out immediately from computing the answer a second way. That is all
this is: a second derivation, from :mod:`workbench.analysis.world_facts`
(raw events, no projection code), compared field by field against the
committed oracle. Disagreement is not automatically the oracle's fault —
it means one of the two is wrong and neither may be trusted until someone
has looked.
"""

import argparse
import datetime
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from workbench.analysis.snapshot import status_on
from workbench.analysis.world_facts import WorldFacts, load_world

REPO = Path(__file__).resolve().parents[2]
TASKS = Path(__file__).resolve().parent / "tasks"
_SOURCE = REPO / "out" / "ashgrove" / "bundle" / "SOURCE"
# The world the current bundle was built from, when the build recorded it.
# A fixed fallback is what made this check compare a fresh oracle against a
# stale world once, so the recorded answer wins whenever there is one.
DEFAULT_LOG = (
    Path(_SOURCE.read_text().strip())
    if _SOURCE.is_file()
    else REPO / "out" / "ashgrove" / "epoch" / "world.jsonl"
)
# Tight on purpose. Both sides round once, at the end, from the same
# integer seconds and cents, so they should agree to the last place; this
# only absorbs IEEE noise from accumulating `seconds * rate / 3600` in
# floats. A looser tolerance is worse than none: the defect this check
# exists to catch — totalling rounded rows instead of the entries — shows
# up as a drift of exactly one or two hundredths on a small world, and an
# epsilon of 0.011 swallows it silently while still looking like a gate.
EPSILON = 1e-6
# The world's own start, carried in every projected database's `meta` and in
# the run.started event. Restated rather than read from the bundle so this
# stays a check on the log and not on the materialization.
EPOCH = "2026-01-05T00:00:00-08:00"

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
_WORD_DAYS = {"a": 1, "two": 2, "three": 3, "five": 5, "ten": 10}
# The task's specification, quoted verbatim in its instruction.
COMMITMENT_PATTERNS = (
    ("weekday", r"\bby (?:this |next |)(monday|tuesday|wednesday|thursday|friday)\b"),
    ("week", r"\bby the end of (?:the |this |next |)week\b"),
    ("month", r"\bby the end of (?:the |this |next |)month\b"),
    ("date", rf"\bby ({'|'.join(_MONTHS)}) (\d{{1,2}})\b"),
    ("day", r"\b(?:eod|cob|end of day|close of business)\b"),
    ("within", r"\bwithin (\d+|a|two|three|five|ten) (?:business )?days?\b"),
    ("tomorrow", r"\bby tomorrow\b"),
)


def _commitment_due(kind: str, match, sent: datetime.date) -> datetime.date:
    """Written from the instruction's table, not from the solver."""

    if kind == "weekday":
        ahead = (_WEEKDAYS.index(match.group(1).lower()) - sent.weekday()) % 7
        return sent + datetime.timedelta(days=7 if ahead == 0 else ahead)
    if kind == "week":
        return sent + datetime.timedelta(days=(4 - sent.weekday()) % 7)
    if kind == "month":
        # The last day of this month, found by walking back from the first
        # of the next one.
        following = (sent.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        return following - datetime.timedelta(days=1)
    if kind == "date":
        month = _MONTHS.index(match.group(1).lower()) + 1
        return datetime.date(sent.year, month, int(match.group(2)))
    if kind == "day":
        return sent
    if kind == "within":
        count = match.group(1).lower()
        days = int(count) if count.isdigit() else _WORD_DAYS[count]
        return sent + datetime.timedelta(days=days)
    return sent + datetime.timedelta(days=1)


def _cmp(where: str, mine, theirs, out: list[str]) -> None:
    if isinstance(mine, (int, float)) and isinstance(theirs, (int, float)):
        if abs(float(mine) - float(theirs)) > EPSILON:
            out.append(
                f"{where}: log says {mine}, oracle says {theirs}"
            )
        return
    if isinstance(mine, str) and isinstance(theirs, str):
        # Case-folded, because that is how the answer is actually graded:
        # every criterion compares `.strip().casefold()`. Clio serves a
        # status title-cased (`In-progress`) while the log holds what the
        # persona wrote (`in-progress`), and an agent is right either way.
        # Reporting that as a disagreement is noise, and noise in a gate is
        # how a gate stops being read.
        if mine.strip().casefold() != theirs.strip().casefold():
            out.append(f"{where}: log says {mine!r}, oracle says {theirs!r}")
        return
    if mine != theirs:
        out.append(f"{where}: log says {mine!r}, oracle says {theirs!r}")


def _rows(
    where: str, mine: list[dict], theirs: list[dict], key, out: list[str]
) -> None:
    """Compare two row lists on a caller-chosen key, then field by field."""

    left = {key(row): row for row in mine}
    right = {key(row): row for row in theirs}
    if len(left) != len(mine):
        out.append(
            f"{where}: my own derivation collapses {len(mine)} rows to {len(left)}"
        )
    if len(right) != len(theirs):
        out.append(
            f"{where}: the oracle's key collapses {len(theirs)} rows to {len(right)} "
            "— the grader cannot tell those rows apart"
        )
    for missing in sorted(right.keys() - left.keys())[:5]:
        out.append(f"{where}: oracle has {missing}, the log does not")
    for extra in sorted(left.keys() - right.keys())[:5]:
        out.append(f"{where}: the log has {extra}, the oracle does not")
    for shared in sorted(left.keys() & right.keys()):
        for field, theirs_value in right[shared].items():
            if field in left[shared]:
                _cmp(
                    f"{where}[{shared}].{field}",
                    left[shared][field],
                    theirs_value,
                    out,
                )


# --------------------------------------------------------------------------
# One derivation per task. Each restates the rule from the *instruction*, not
# from the solver, so a solver that reads its own instruction wrongly shows up
# here as a disagreement rather than as truth.
# --------------------------------------------------------------------------


def check_time_allocation(facts: WorldFacts, oracle: dict) -> list[str]:
    out: list[str] = []
    totals: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"entries": 0, "seconds": 0, "billable_seconds": 0, "cents": 0.0}
    )
    for activity in facts.activities:
        row = totals[(activity.person_id, activity.ticket_id)]
        seconds = activity.minutes * 60
        row["entries"] += 1
        row["seconds"] += seconds
        if activity.billable:
            row["billable_seconds"] += seconds
            # An entry without a rate contributes hours but no fees. There is
            # one billable entry with no rate, and it is the whole reason this
            # is spelled out rather than assumed.
            row["cents"] += seconds * (activity.rate_cents or 0) / 3600

    rows = [
        {
            "person": facts.name(person),
            "engagement": facts.display_number(ticket),
            "entries": int(row["entries"]),
            "hours": round(row["seconds"] / 3600, 2),
            "billable_hours": round(row["billable_seconds"] / 3600, 2),
            "fees_dollars": round(row["cents"] / 100, 2),
        }
        for (person, ticket), row in totals.items()
        if ticket in facts.tickets
    ]
    _cmp("entries_total", sum(r["entries"] for r in rows), oracle["entries_total"], out)
    _cmp("pairs", len(rows), oracle["pairs"], out)
    # Off the entries, deliberately: this is the exact quantity the two
    # methods disagree about, so deriving it the same way twice would prove
    # nothing.
    _cmp(
        "total_hours",
        round(sum(r["seconds"] for r in totals.values()) / 3600, 2),
        oracle["total_hours"],
        out,
    )
    _cmp(
        "total_billable_hours",
        round(sum(r["billable_seconds"] for r in totals.values()) / 3600, 2),
        oracle["total_billable_hours"],
        out,
    )
    _cmp(
        "total_fees_dollars",
        round(sum(r["cents"] for r in totals.values()) / 100, 2),
        oracle["total_fees_dollars"],
        out,
    )
    # The instruction's rule, not the solver's: most hours, then the earlier
    # person and engagement alphabetically. Restating it from the solver
    # would have copied the bug across and proved the two agree about it.
    busiest = min(rows, key=lambda r: (-r["hours"], r["person"], r["engagement"]))
    _cmp("busiest_person", busiest["person"], oracle["busiest_person"], out)
    _cmp("busiest_engagement", busiest["engagement"], oracle["busiest_engagement"], out)
    _rows(
        "allocations",
        rows,
        oracle["allocations"],
        lambda r: (r["person"], r["engagement"]),
        out,
    )
    return out


def check_work_product_review(facts: WorldFacts, oracle: dict) -> list[str]:
    out: list[str] = []
    attached = facts.attached_documents()
    internal = facts.internal
    reached: set[str] = set()
    for document_id, message_ids in attached.items():
        for message_id in message_ids:
            if facts.emails[message_id].recipients - internal:
                reached.add(document_id)
                break

    rows = []
    for document in facts.documents.values():
        chain = sorted(document.chain)
        first_author = chain[0][1] if chain else ""
        rows.append(
            {
                "document": document.title,
                "workspace": document.workspace,
                "author": facts.name(first_author) if first_author else "",
                "versions": max((v for v, _ in chain), default=0),
                "reviewed": any(author != first_author for _v, author in chain[1:]),
                "reached_client": document.document_id in reached,
            }
        )
    _cmp("documents_total", len(rows), oracle["documents_total"], out)
    _cmp(
        "reviewed_count",
        sum(r["reviewed"] for r in rows),
        oracle["reviewed_count"],
        out,
    )
    _cmp(
        "unreviewed_count",
        sum(not r["reviewed"] for r in rows),
        oracle["unreviewed_count"],
        out,
    )
    _cmp(
        "reached_client_count",
        len(reached & set(facts.documents)),
        oracle["reached_client_count"],
        out,
    )
    _cmp(
        "never_attached_count",
        sum(1 for d in facts.documents if d not in attached),
        oracle["never_attached_count"],
        out,
    )
    # Compared as a multiset of what each row claims, not on the key.
    # iManage's document number is minted by the projection and served
    # verbatim, so an agent copies it and it cannot be a wrong *answer* --
    # only the facts hanging off it can be. Restating how the number is
    # assigned would copy the projection, which is the one thing this file
    # exists not to do.
    def claim(row: dict) -> tuple:
        return (
            row["document"],
            row["workspace"],
            row["author"],
            row["versions"],
            bool(row["reviewed"]),
            bool(row["reached_client"]),
        )

    ours: dict[tuple, int] = defaultdict(int)
    theirs: dict[tuple, int] = defaultdict(int)
    for row in rows:
        ours[claim(row)] += 1
    for row in oracle["documents"]:
        theirs[claim(row)] += 1
    for key in sorted(set(ours) | set(theirs)):
        if ours[key] != theirs[key]:
            out.append(
                f"documents{list(key)}: log counts {ours[key]}, "
                f"oracle counts {theirs[key]}"
            )
    if len({r["document_number"] for r in oracle["documents"]}) != len(
        oracle["documents"]
    ):
        out.append(
            "documents: the oracle's document numbers are not unique — the "
            "grader cannot tell those rows apart"
        )
    return out


def check_client_responsiveness(facts: WorldFacts, oracle: dict) -> list[str]:
    out: list[str] = []
    external = {
        p.person_id for p in facts.people.values() if p.affiliation == "external"
    }
    clients = {
        p.person_id
        for p in facts.people.values()
        if p.affiliation == "external" and p.department == "Client"
    }
    threads = facts.threads()

    rows, every_wait = [], []
    for thread_id, messages in sorted(threads.items()):
        inbound = [m for m in messages if m.sender in clients]
        if not inbound:
            continue
        unanswered, waits = 0, []
        for index, message in enumerate(messages):
            if message.sender not in clients:
                continue
            # Only the firm closes a client message, and one reply closes
            # every client message before it at once.
            reply = next(
                (m for m in messages[index + 1 :] if m.sender not in external), None
            )
            if reply is None:
                unanswered += 1
            else:
                waits.append((reply.time - message.time) / 3600)
        every_wait.extend(waits)
        rows.append(
            {
                "thread_id": thread_id,
                "client": facts.name(inbound[0].sender),
                "messages": len(messages),
                "inbound": len(inbound),
                "unanswered": unanswered,
                "first_reply_hours": round(waits[0], 2) if waits else 0.0,
                "longest_reply_hours": round(max(waits), 2) if waits else 0.0,
            }
        )
    _cmp("threads_reviewed", len(threads), oracle["threads_reviewed"], out)
    _cmp(
        "threads_with_client_inbound",
        len(rows),
        oracle["threads_with_client_inbound"],
        out,
    )
    _cmp("inbound_total", sum(r["inbound"] for r in rows), oracle["inbound_total"], out)
    _cmp(
        "unanswered_total",
        sum(r["unanswered"] for r in rows),
        oracle["unanswered_total"],
        out,
    )
    _cmp(
        "firm_median_reply_hours",
        round(statistics.median(every_wait), 2) if every_wait else 0.0,
        oracle["firm_median_reply_hours"],
        out,
    )
    if rows:
        _cmp(
            "slowest_thread",
            max(rows, key=lambda r: (r["longest_reply_hours"], r["thread_id"]))[
                "thread_id"
            ],
            oracle["slowest_thread"],
            out,
        )
    _rows("threads", rows, oracle["threads"], lambda r: r["thread_id"], out)
    return out


def check_status_integrity(facts: WorldFacts, oracle: dict) -> list[str]:
    """Engagements whose status went backwards, and the time logged since.

    The only task here whose evidence was, for a while, unreachable: clio
    served no matter history at all, so Opus 5 scored 0.067 on an answer the
    tools could not produce. That was an environment defect, not a model
    failure, and this derivation is deliberately blind to whether the fix
    landed -- it reads the world, and the rollout reads the tools.
    """

    out: list[str] = []
    # A hold has no rank, so a move into or out of `waiting-client` is a
    # change without being a step backwards.
    rank = {"open": 1, "in-progress": 2, "review": 3, "closed": 4}

    changes: dict[str, int] = defaultdict(int)
    backward: dict[str, int] = defaultdict(int)
    reopened: set[str] = set()
    first_backward: dict[str, int] = {}
    for ticket_id, ticket in facts.tickets.items():
        for when, _actor, name, old, new in sorted(ticket.changes):
            if name != "status":
                continue
            changes[ticket_id] += 1
            if old.strip().casefold() == "closed":
                reopened.add(ticket_id)
            before = rank.get(old.strip().casefold())
            after = rank.get(new.strip().casefold())
            if before is not None and after is not None and after < before:
                backward[ticket_id] += 1
                first_backward.setdefault(ticket_id, when)

    flagged = []
    for ticket_id in facts.tickets:
        if not backward.get(ticket_id):
            continue
        # Whole days: clio dates a change and an entry, and stamps an hour
        # on neither.
        since = first_backward[ticket_id] // 86_400
        seconds = sum(
            a.minutes * 60
            for a in facts.activities
            if a.ticket_id == ticket_id and a.at // 86_400 >= since
        )
        flagged.append(
            {
                "engagement": facts.display_number(ticket_id),
                "status": facts.current_status(ticket_id),
                "status_changes": changes.get(ticket_id, 0),
                "backward_moves": backward[ticket_id],
                "reopened": ticket_id in reopened,
                "hours_from_backward_day": round(seconds / 3600, 2),
            }
        )

    _cmp(
        "engagements_reviewed",
        len(facts.tickets),
        oracle["engagements_reviewed"],
        out,
    )
    _cmp(
        "reopened_count",
        len(reopened & set(facts.tickets)),
        oracle["reopened_count"],
        out,
    )
    _cmp(
        "backward_move_count",
        sum(backward.values()),
        oracle["backward_move_count"],
        out,
    )
    _cmp(
        "never_moved_count",
        sum(1 for t in facts.tickets if not changes.get(t)),
        oracle["never_moved_count"],
        out,
    )
    _rows("flagged", flagged, oracle["flagged"], lambda r: r["engagement"], out)
    return out


def check_commitment_register(facts: WorldFacts, oracle: dict) -> list[str]:
    """Every promised deadline, re-read from the log's own message bodies.

    The seven patterns are the task's specification, so restating them here
    proves nothing about them — they are quoted in the instruction and an
    agent is graded on applying exactly those. What this does test is
    everything around them: that the world's epoch resolves to the same
    calendar the tools serve, that the counterparty join from mail domain to
    organisation name holds, and that a message promising one date twice
    still makes one row.
    """

    out: list[str] = []
    epoch = datetime.datetime.fromisoformat(EPOCH)
    organisations = {
        "".join(c for c in name.lower() if c.isalnum()): name
        for name in facts.orgs.values()
    }

    rows: dict[tuple[str, str], dict] = {}

    def collect(ref: str, sender: str, when: int, body: str, made_to: str) -> None:
        sent = (epoch + datetime.timedelta(seconds=when)).date()
        for kind, pattern in COMMITMENT_PATTERNS:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                due = _commitment_due(kind, match, sent)
                rows[(ref, due.isoformat())] = {
                    "ref": ref,
                    "due_date": due.isoformat(),
                    "author": facts.name(sender),
                    "sent_date": sent.isoformat(),
                    "made_to": made_to,
                }

    for email in facts.emails.values():
        outside = sorted(
            {
                organisations.get(domain.split(".")[0], domain)
                for domain in (
                    facts.people[p].email_address.split("@")[-1]
                    for p in (email.sender, *email.to, *email.cc)
                    if p in facts.people
                    and facts.people[p].affiliation == "external"
                )
            }
        )
        collect(
            email.message_id,
            email.sender,
            email.time,
            email.body,
            outside[0] if outside else "the firm",
        )
    # Chat is checked on its facts rather than on its key, deliberately.
    #
    # Slack names a message by a timestamp whose fractional part is a
    # within-second counter the projection mints (`1767661500.000003`).
    # Restating that here would copy the projection's algorithm, which is
    # the one thing this file exists not to do -- and it would buy nothing,
    # because the timestamp is served verbatim and the agent copies it. A
    # `ts` cannot be a *wrong answer*; only the facts attached to it can.
    # So: the mail rows are matched row by row on their stable ids, and the
    # chat rows are compared as a multiset of what they claim.
    chat_rows: dict[tuple[str, str, str, str], int] = defaultdict(int)
    chat_messages = 0
    for chat in facts.chats:
        sent = (epoch + datetime.timedelta(seconds=chat.time)).date()
        made_to = facts.channels.get(chat.conversation_id, chat.conversation_id)
        due_dates = set()
        for kind, pattern in COMMITMENT_PATTERNS:
            for match in re.finditer(pattern, chat.body, re.IGNORECASE):
                due_dates.add(_commitment_due(kind, match, sent).isoformat())
        chat_messages += bool(due_dates)
        for due in due_dates:
            key = (facts.name(chat.sender), sent.isoformat(), due, made_to)
            chat_rows[key] += 1

    mail_only = [rows[key] for key in sorted(rows)]
    theirs_chat: dict[tuple[str, str, str, str], int] = defaultdict(int)
    theirs_mail = []
    for row in oracle["commitments"]:
        if row["ref"].startswith("msg-"):
            theirs_mail.append(row)
        else:
            theirs_chat[
                (row["author"], row["sent_date"], row["due_date"], row["made_to"])
            ] += 1
    for key in sorted(set(chat_rows) | set(theirs_chat)):
        if chat_rows[key] != theirs_chat[key]:
            out.append(
                f"chat{list(key)}: log counts {chat_rows[key]}, "
                f"oracle counts {theirs_chat[key]}"
            )

    register = mail_only + [
        {"ref": "chat"} for _ in range(sum(chat_rows.values()))
    ]
    _cmp(
        "messages_read",
        len(facts.emails) + len(facts.chats),
        oracle["messages_read"],
        out,
    )
    _cmp("commitments_total", len(register), oracle["commitments_total"], out)
    _cmp(
        "messages_with_commitment",
        len({r["ref"] for r in mail_only}) + chat_messages,
        oracle["messages_with_commitment"],
        out,
    )
    for field, index, name in (
        ("due_date", 2, "busiest_due_date"),
        ("made_to", 3, "top_made_to"),
    ):
        counts: dict[str, int] = defaultdict(int)
        for row in mail_only:
            counts[row[field]] += 1
        for key, many in chat_rows.items():
            counts[key[index]] += many
        # Most, then earliest -- `max` would break the tie the other way.
        _cmp(name, min(counts, key=lambda k: (-counts[k], k)), oracle[name], out)
    _rows(
        "commitments",
        mail_only,
        theirs_mail,
        lambda r: (r["ref"], r["due_date"]),
        out,
    )
    return out


def check_open_items_triage(facts: WorldFacts, oracle: dict) -> list[str]:
    """Client threads whose last word is a question the firm has not answered.

    The one task already shown to discriminate: 1.000 for Opus 5 and 0.630
    for glm-5.2, which is what a working instrument looks like even though
    it is far too thin to grade partly right.
    """

    out: list[str] = []
    markers = (
        "please send", "please provide", "please confirm", "could you",
        "can you", "would you", "we need", "i need", "when will",
        "let me know", "waiting on", "waiting for",
    )

    def asks(body: str) -> bool:
        lowered = body.lower()
        return "?" in body or any(marker in lowered for marker in markers)

    external = {
        p.person_id for p in facts.people.values() if p.affiliation == "external"
    }
    threads = facts.threads()
    awaiting = []
    courtesy = 0
    for thread_id, messages in threads.items():
        last = messages[-1]
        if last.sender not in external:
            continue
        if asks(last.body):
            awaiting.append(
                {
                    "thread_id": thread_id,
                    "message_id": last.message_id,
                    "client": facts.name(last.sender),
                    "subject": re.sub(r"^(Re|RE|Fwd):\s*", "", last.subject).strip(),
                    "messages_in_thread": len(messages),
                }
            )
        else:
            courtesy += 1

    _cmp("threads_reviewed", len(threads), oracle["threads_reviewed"], out)
    _cmp("awaiting_firm_count", len(awaiting), oracle["awaiting_firm_count"], out)
    _cmp(
        "closed_by_client_courtesy",
        courtesy,
        oracle["closed_by_client_courtesy"],
        out,
    )
    _rows(
        "awaiting_firm",
        awaiting,
        oracle["awaiting_firm"],
        lambda r: r["thread_id"],
        out,
    )
    return out


def check_closeout_readiness(facts: WorldFacts, oracle: dict) -> list[str]:
    """Client engagements, and which of them are waiting on the firm.

    Clio's `responsible_person` is a ticket's assignee and its
    `originating_person` is the requester -- the client contact who opened
    it. The distinction carries the whole task: an engagement is waiting
    when *that* contact's last word in any thread is still unanswered.
    """

    out: list[str] = []
    external = {
        p.person_id for p in facts.people.values() if p.affiliation == "external"
    }
    threads = facts.threads()
    # Each outside person's oldest unanswered last word.
    waiting_since: dict[str, int] = {}
    for messages in threads.values():
        last = messages[-1]
        if last.sender in external:
            waiting_since[last.sender] = min(
                waiting_since.get(last.sender, last.time), last.time
            )
    horizon = max(
        (m.time for messages in threads.values() for m in messages), default=0
    )

    hours: dict[str, int] = defaultdict(int)
    staff: dict[str, set[str]] = defaultdict(set)
    wip_cents: dict[str, int] = defaultdict(int)
    for activity in facts.activities:
        seconds = activity.minutes * 60
        hours[activity.ticket_id] += seconds
        staff[activity.ticket_id].add(activity.person_id)
        if activity.billable and activity.rate_cents:
            wip_cents[activity.ticket_id] += seconds * activity.rate_cents // 3600

    rows = []
    for ticket_id in sorted(facts.tickets):
        ticket = facts.tickets[ticket_id]
        # An engagement is client work when it has a client. Who opened it
        # is not the test -- the peer review was opened by the outside
        # reviewer and is still the firm's own.
        if ticket.client_ref is None:
            continue
        originator = ticket.requester
        waiting = originator in waiting_since
        rows.append(
            {
                "engagement": facts.display_number(ticket_id),
                "client_contact": facts.name(originator) if originator else "",
                "responsible": facts.name(ticket.assignee) if ticket.assignee else "",
                "total_hours": round(hours.get(ticket_id, 0) / 3600, 2),
                "staff_count": len(staff.get(ticket_id, ())),
                "status": "awaiting_firm_reply" if waiting else "clear",
                "client_waiting_hours": round(
                    (horizon - waiting_since[originator]) / 3600, 1
                )
                if waiting
                else 0.0,
                "wip_dollars": round(wip_cents.get(ticket_id, 0) / 100, 2),
            }
        )

    _cmp("client_engagements", len(rows), oracle["client_engagements"], out)
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["status"]] += 1
    _cmp("status_counts", dict(sorted(counts.items())), oracle["status_counts"], out)
    awaiting = [r for r in rows if r["status"] == "awaiting_firm_reply"]
    _cmp(
        "wip_at_risk_dollars",
        round(sum(r["wip_dollars"] for r in awaiting), 2),
        oracle["wip_at_risk_dollars"],
        out,
    )
    for name, value in (
        ("awaiting_firm_reply", sorted(r["engagement"] for r in awaiting)),
        (
            "at_risk_over_10k",
            sorted(r["engagement"] for r in awaiting if r["wip_dollars"] > 10000),
        ),
    ):
        if value != oracle[name]:
            out.append(f"{name}: log says {value}, oracle says {oracle[name]}")
    _rows(
        "engagements", rows, oracle["engagements"], lambda r: r["engagement"], out
    )
    return out


#  Every internal title, and the delivery tier it belongs to. Support is a
#  tier of the firm but not of an engagement: an admin coordinator's hours
#  are real and are neither delivery nor review.
_TIERS = {
    "Managing Partner": "partner",
    "Partner, Client Accounting & Advisory": "partner",
    "Principal, Assurance": "partner",
    "Audit Manager": "manager",
    "Tax Manager": "manager",
    "Client Accounting Lead": "manager",
    "Senior Accountant, Assurance": "senior",
    "Senior Accountant, Tax": "senior",
    "Staff Accountant": "staff",
    "Payroll Specialist": "staff",
    "Office & Billing Manager": "support",
    "Admin Coordinator": "support",
    "IT Administrator": "support",
}


def check_staffing_leverage(facts: WorldFacts, oracle: dict) -> list[str]:
    """How much of each engagement sits with seniors rather than partners."""

    out: list[str] = []
    tier_of = {
        p.person_id: _TIERS[p.title]
        for p in facts.people.values()
        if p.affiliation == "internal" and p.title in _TIERS
    }
    hours: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for activity in facts.activities:
        ticket = facts.tickets.get(activity.ticket_id)
        # The firm's own projects have no client and are not engagements.
        if ticket is None or ticket.client_ref is None:
            continue
        tier = tier_of.get(activity.person_id)
        if tier is None:
            continue
        hours[activity.ticket_id][tier] += activity.minutes * 60

    rows = []
    for ticket_id in sorted(hours, key=facts.display_number):
        tiers = hours[ticket_id]
        delivery = tiers.get("senior", 0) + tiers.get("staff", 0)
        review = tiers.get("partner", 0) + tiers.get("manager", 0)
        total = sum(v for k, v in tiers.items() if k != "support")
        rows.append(
            {
                "engagement": facts.display_number(ticket_id),
                "partner_hours": round(tiers.get("partner", 0) / 3600, 2),
                "manager_hours": round(tiers.get("manager", 0) / 3600, 2),
                "senior_hours": round(tiers.get("senior", 0) / 3600, 2),
                "staff_hours": round(tiers.get("staff", 0) / 3600, 2),
                "support_hours": round(tiers.get("support", 0) / 3600, 2),
                "leverage_ratio": round(delivery / review, 2) if review else None,
                "review_share_pct": round(100 * review / total, 1) if total else 0.0,
            }
        )
    _cmp("engagements_reviewed", len(rows), oracle["engagements_reviewed"], out)
    firm_delivery = sum(h.get("senior", 0) + h.get("staff", 0) for h in hours.values())
    firm_review = sum(h.get("partner", 0) + h.get("manager", 0) for h in hours.values())
    _cmp(
        "firm_leverage_ratio",
        round(firm_delivery / firm_review, 2) if firm_review else None,
        oracle["firm_leverage_ratio"],
        out,
    )
    over = sorted(r["engagement"] for r in rows if r["review_share_pct"] > 40.0)
    if over != oracle["over_supervised"]:
        out.append(
            f"over_supervised: log says {over}, oracle says {oracle['over_supervised']}"
        )
    _rows(
        "engagements", rows, oracle["engagements"], lambda r: r["engagement"], out
    )
    return out


def check_wip_utilization(facts: WorldFacts, oracle: dict) -> list[str]:
    """Work in progress by engagement, and utilization by person.

    Three rules move many numbers at once, so each is restated rather than
    assumed: the firm's own projects carry no client and no WIP; an entry
    with no rate carries no value however many hours it has; and
    non-billable time counts toward a person's day but never toward WIP.
    """

    out: list[str] = []
    per_engagement: dict[str, dict] = defaultdict(
        lambda: {"billable_seconds": 0, "value_cents": 0, "staff": set()}
    )
    per_person: dict[str, dict] = defaultdict(
        lambda: {"logged_seconds": 0, "billable_seconds": 0, "value_cents": 0}
    )
    for activity in facts.activities:
        seconds = activity.minutes * 60
        value = seconds * (activity.rate_cents or 0) // 3600 if activity.billable else 0
        person = per_person[activity.person_id]
        person["logged_seconds"] += seconds
        if activity.billable:
            person["billable_seconds"] += seconds
            person["value_cents"] += value
        ticket = facts.tickets.get(activity.ticket_id)
        if ticket is None or ticket.client_ref is None:
            continue
        row = per_engagement[activity.ticket_id]
        row["staff"].add(activity.person_id)
        if activity.billable:
            row["billable_seconds"] += seconds
            row["value_cents"] += value

    client = [t for t, k in facts.tickets.items() if k.client_ref is not None]
    internal = len(facts.tickets) - len(client)
    # Every client engagement appears, quiet ones included: leaving them out
    # would make the count depend on whether anyone happened to log to it.
    empty = {"billable_seconds": 0, "value_cents": 0, "staff": ()}
    engagements = [
        {
            "engagement": facts.display_number(t),
            "billable_hours": round(
                per_engagement.get(t, empty)["billable_seconds"] / 3600, 2
            ),
            "wip_dollars": round(per_engagement.get(t, empty)["value_cents"] / 100, 2),
            "staff_count": len(per_engagement.get(t, empty)["staff"]),
        }
        for t in sorted(client, key=facts.display_number)
    ]
    people = [
        {
            "name": facts.name(person),
            "logged_hours": round(row["logged_seconds"] / 3600, 2),
            "billable_hours": round(row["billable_seconds"] / 3600, 2),
            "utilization_pct": round(
                100 * row["billable_seconds"] / row["logged_seconds"], 1
            )
            if row["logged_seconds"]
            else 0.0,
        }
        for person, row in sorted(
            per_person.items(), key=lambda kv: facts.name(kv[0])
        )
    ]
    total_value = sum(r["value_cents"] for r in per_engagement.values())
    total_billable = sum(r["billable_seconds"] for r in per_engagement.values())

    _cmp("client_engagements", len(client), oracle["client_engagements"], out)
    _cmp("internal_engagements", internal, oracle["internal_engagements"], out)
    _cmp(
        "total_client_wip_dollars",
        round(total_value / 100, 2),
        oracle["total_client_wip_dollars"],
        out,
    )
    _cmp(
        "blended_rate_dollars_per_hour",
        round(total_value / 100 / (total_billable / 3600), 2)
        if total_billable
        else 0.0,
        oracle["blended_rate_dollars_per_hour"],
        out,
    )
    _rows(
        "engagements",
        engagements,
        oracle["engagements"],
        lambda r: r["engagement"],
        out,
    )
    _rows("people", people, oracle["people"], lambda r: r["name"], out)
    return out


def _verdict(on_sheet: bool, actual: float, tracker: float) -> str:
    if not on_sheet:
        return "absent_from_tracker"
    return "unchanged" if abs(actual - tracker) < 0.005 else "understated"


def check_tracker_reconciliation(facts: WorldFacts, oracle: dict) -> list[str]:
    """The week-one sheet against the record, re-derived from the log.

    The generator and the solver sit on opposite sides of the same
    snapshot: one writes the tracker from the world at the cutoff, the
    other reads it back and compares with clio. If they ever disagreed
    about what day four looked like, every row would be wrong together and
    nothing else here would notice.
    """

    out: list[str] = []
    cutoff = 4 * 86_400
    spoken = {
        "not started": {"open"},
        "in progress": {"in-progress", "waiting-client"},
        "in review": {"review"},
        "complete": {"closed"},
    }
    said = {v: k for k, values in spoken.items() for v in values}

    engagements = []
    for ticket_id in sorted(facts.tickets):
        ticket = facts.tickets[ticket_id]
        if ticket.client_ref is None:
            continue
        then = status_on(facts, ticket_id, cutoff).strip().casefold()
        now = facts.current_status(ticket_id).strip().casefold()
        word = said.get(then, then)
        engagements.append(
            {
                "engagement": facts.display_number(ticket_id),
                "moved": now not in spoken.get(word, {then}),
            }
        )

    then_minutes: dict[tuple[str, str], int] = defaultdict(int)
    now_minutes: dict[tuple[str, str], int] = defaultdict(int)
    for activity in facts.activities:
        ticket = facts.tickets.get(activity.ticket_id)
        if ticket is None or ticket.client_ref is None:
            continue
        key = (facts.display_number(activity.ticket_id), facts.name(activity.person_id))
        now_minutes[key] += activity.minutes
        if activity.at <= cutoff:
            then_minutes[key] += activity.minutes

    effort = []
    for key in sorted(set(now_minutes) | set(then_minutes)):
        tracker_hours = round(then_minutes.get(key, 0) / 60, 2)
        actual = round(now_minutes.get(key, 0) / 60, 2)
        effort.append(
            {
                "engagement": key[0],
                "person": key[1],
                "tracker_hours": tracker_hours,
                "actual_hours": actual,
                "verdict": _verdict(key in then_minutes, actual, tracker_hours),
            }
        )

    _cmp(
        "engagements_on_tracker",
        len(engagements),
        oracle["engagements_on_tracker"],
        out,
    )
    _cmp(
        "engagements_moved",
        sum(1 for r in engagements if r["moved"]),
        oracle["engagements_moved"],
        out,
    )
    _cmp("effort_lines", len(effort), oracle["effort_lines"], out)
    counts: dict[str, int] = defaultdict(int)
    for row in effort:
        counts[row["verdict"]] += 1
    _cmp("verdict_counts", dict(sorted(counts.items())), oracle["verdict_counts"], out)
    _cmp(
        "hours_understated_total",
        round(sum(r["actual_hours"] - r["tracker_hours"] for r in effort), 2),
        oracle["hours_understated_total"],
        out,
    )
    _rows(
        "effort",
        effort,
        oracle["effort"],
        lambda r: (r["engagement"], r["person"]),
        out,
    )
    _rows(
        "engagements",
        engagements,
        [{"engagement": r["engagement"], "moved": r["moved"]} for r in
         oracle["engagements"]],
        lambda r: r["engagement"],
        out,
    )
    return out


CHECKS = {
    "commitment-register": check_commitment_register,
    "engagement-closeout-readiness": check_closeout_readiness,
    "tracker-reconciliation": check_tracker_reconciliation,
    "staffing-leverage-review": check_staffing_leverage,
    "wip-utilization-review": check_wip_utilization,
    "open-items-triage": check_open_items_triage,
    "engagement-time-allocation": check_time_allocation,
    "work-product-review": check_work_product_review,
    "client-responsiveness-sla": check_client_responsiveness,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args(argv)

    facts = load_world(args.log)
    print(
        f"{args.log}: {len(facts.people)} people, {len(facts.tickets)} tickets, "
        f"{len(facts.activities)} entries, {len(facts.documents)} documents, "
        f"{len(facts.emails)} messages"
    )
    failures = 0
    unchecked = []
    for task in sorted(args.tasks or [p.name for p in TASKS.iterdir() if p.is_dir()]):
        check = CHECKS.get(task)
        if check is None:
            unchecked.append(task)
            continue
        oracle_path = TASKS / task / "tests" / "oracle.json"
        if not oracle_path.is_file():
            print(f"{task}: NO ORACLE")
            failures += 1
            continue
        problems = check(load_world(args.log), json.loads(oracle_path.read_text()))
        if problems:
            failures += 1
            print(f"\n{task}: {len(problems)} DISAGREEMENTS")
            for problem in problems[:20]:
                print(f"  {problem}")
            if len(problems) > 20:
                print(f"  ... and {len(problems) - 20} more")
        else:
            print(f"{task}: agrees")
    if unchecked:
        # Named rather than silently skipped: a verifier that quietly covers
        # three of eight tasks reads exactly like one that covers all eight.
        print(f"\nno independent derivation yet: {', '.join(unchecked)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
