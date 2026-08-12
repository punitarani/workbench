"""Measure each hartwell task's reference tool-path floor.

    uv run python datasets/hartwell/measure_floors.py [task-name ...]

The floor is the call count of the honest minimal tool sequence — the
discovery path an informed professional who knows the tools (but not the
answers) would take through the real MCP servers — scripted here against
each task's built environment bundle and counted mechanically, one tool
call per step, no parallelism credit. Every sequence must retrieve enough of the
record to reproduce the task's graded ground truth, and each run asserts
that it did. The floor is calibration metadata, not a hard runtime cap. It includes
the write_file and finish builtins (one deliverable file per task), which
the harness counts against the same budget.
"""

import asyncio
import json
import sys
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from workbench.adapters.harness.mcp_workspace import McpWorkspace, open_workspace

TASKS = Path(__file__).parent / "tasks"
EPOCH = date(2026, 3, 2)
PACIFIC = ZoneInfo("America/Los_Angeles")
WRITE_AND_FINISH = 2

# Every brief scopes its review to the firm's closed quarter: billing-hygiene
# names it outright ("March 2 through June 30, 2026, inclusive"), the two
# one-to-one audits sweep "March through June", and the fee reconstruction
# works the April window inside it. These sweeps went unbounded while the
# world happened to stop on June 30; the bound is stated here, from the
# briefs rather than from any solve.py, so the discovery paths keep asking
# the same question now that the record runs on past the quarter.
REVIEW_FIRST_DAY = "2026-03-02"
REVIEW_LAST_DAY = "2026-06-30"
REVIEW_END_EXCLUSIVE = date(2026, 7, 1)
# Gmail's ``before:`` is exclusive of the day it names.
REVIEW_MAIL_QUERY = f"before:{REVIEW_END_EXCLUSIVE:%Y/%m/%d}"

# The firm's standing phrasings for the one-to-one requests each audit
# certifies, stated verbatim in the corresponding brief.
SECOND_READ_REQUEST = "mind taking a quick look at my draft before it goes out?"
SHEET_REQUEST = "do you still have the sign-in sheet from yesterday?"

S2_MARKERS = ("meridian", "diagnostics", "00001")
ARROYO_TOKENS = ("arroyo", "dept. 511", "fruitvale")

# The vanished-clause mention rule, keyed by path basename (NDAs derive
# their vendor marker from the filename). Mirrors DOC_MENTION_MARKERS.
MENTION_MARKERS = {
    "board-resolution-review.md": ("board resolution review",),
    "cam-reconciliation-analysis.md": ("cam reconciliation",),
    "case-chronology.md": ("case chronology",),
    "closing-checklist.md": ("closing checklist",),
    "compliance-memorandum.md": ("compliance memorandum",),
    "disclosure-schedules.md": ("disclosure schedules",),
    "early-case-assessment.md": ("early case assessment",),
    "engagement-letter.md": ("engagement letter",),
    "holdback-administration-memo.md": ("holdback administration",),
    "lien-claim-summary.md": ("lien claim summary",),
    "matter-intake-checklist.md": ("intake checklist", "matter-intake-checklist"),
    "billing-guidelines.md": (
        "billing guidelines",
        "time entry guidelines",
        "billing-guidelines",
    ),
    "litigation-hold-notice.md": ("litigation hold", "litigation-hold"),
    "discovery-responses.md": (
        "discovery response playbook",
        "discovery playbook",
        "discovery-responses",
    ),
    "vendor-nda-playbook.md": ("nda playbook", "vendor-nda-playbook"),
    "license-and-support-agreement.md": (
        "license and support agreement",
        "license-and-support-agreement",
    ),
    "position-statement.md": ("position statement",),
    "renewal-option-notice.md": ("renewal option notice",),
    "scheduling-conference-report.md": ("scheduling conference report",),
    "stop-notice-service-list.md": ("stop notice service list",),
    "support-services-sow.md": ("statement of work", "support-services-sow"),
    "vendor-contract-comparison.md": ("vendor contract comparison",),
    "witness-interview-summaries.md": ("witness interview summaries",),
}


def _day_seconds(iso: str) -> int:
    return int(
        datetime.combine(date.fromisoformat(iso), time.min, tzinfo=PACIFIC).timestamp()
    )


def _ts_day(ts: str) -> str:
    return datetime.fromtimestamp(int(float(ts)), tz=PACIFIC).date().isoformat()


def _ts_prefix(ts: str) -> str:
    return ts.split(".")[0]


def _next_working_day(day: date) -> date:
    moment = day + timedelta(days=1)
    while moment.weekday() >= 5:
        moment += timedelta(days=1)
    return moment


def _custody_outcome(
    asked_on: date, asked_at: int, response_times: Iterable[int]
) -> tuple[bool, bool, bool]:
    first_response = min(
        (timestamp for timestamp in response_times if timestamp > asked_at),
        default=None,
    )
    if first_response is None:
        return False, False, False
    response_day = date.fromisoformat(_ts_day(str(first_response)))
    same_day = response_day == asked_on
    next_working_day = asked_on < response_day <= _next_working_day(asked_on)
    return same_day, next_working_day, same_day or next_working_day


def _working_days(start: date, end: date) -> int:
    count, moment = 0, start
    while moment < end:
        moment += timedelta(days=1)
        if moment.weekday() < 5:
            count += 1
    return count


def _mail_seconds(iso_datetime: str) -> int:
    return int(datetime.fromisoformat(iso_datetime).timestamp())


def _seconds_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=PACIFIC).isoformat()


def _imanage_day(edit_date: str) -> str:
    """iManage serves true-UTC instants; audit dates use the firm timezone."""
    moment = datetime.fromisoformat(edit_date.replace("Z", "+00:00"))
    return moment.astimezone(PACIFIC).date().isoformat()


def _mail_text(message: dict) -> str:
    names = " ".join(a["filename"] for a in message.get("attachments", []))
    return f"{message['subject']} {message['plaintextBody']} {names}".lower()


def _sender_email(message: dict) -> str:
    return message["sender"].split("<")[-1].rstrip(">")


def _document_number(display_id: str) -> int:
    return int(str(display_id).split("!")[1].split(".")[0])


def _strip_notices(content: str) -> str:
    sections = content.split("\n## ")
    return "\n## ".join(
        [sections[0]] + [s for s in sections[1:] if not s.startswith("Notices")]
    )


class CountingClient:
    """One tool call per step against the live workspace servers."""

    def __init__(self, workspace: McpWorkspace) -> None:
        self._workspace = workspace
        self.calls = 0

    async def call(self, name: str, **arguments: Any) -> Any:
        self.calls += 1
        text = await self._workspace.call(name, arguments)
        if text.startswith("ERROR:"):
            raise RuntimeError(f"{name} failed: {text[:200]}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # A list-returning tool arrives as one JSON document per
            # content block, concatenated; decode them in sequence.
            decoder = json.JSONDecoder()
            items: list[Any] = []
            position = 0
            while position < len(text):
                item, end = decoder.raw_decode(text, position)
                items.append(item)
                position = end
                while position < len(text) and text[position] in " \n\r\t":
                    position += 1
            return items


def _truth(task: str) -> dict:
    path = TASKS / task / "tests" / "ground_truth.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _oracle(task: str) -> dict:
    path = TASKS / task / "tests" / "oracle.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_records(values: Iterable[object]) -> list[str]:
    return sorted(
        json.dumps(item, sort_keys=True, separators=(",", ":")) for item in values
    )


async def _read_window(
    client: CountingClient, channel: str, oldest: int, latest: int
) -> list[dict]:
    """Windowed newest-first reads, paging backwards until exhausted."""
    messages: list[dict] = []
    upper = float(latest)
    while True:
        page = await client.call(
            "slack__slack_read_channel",
            channel_id=channel,
            limit=100,
            oldest=str(oldest),
            latest=str(upper),
        )
        messages += page["messages"]
        if not page["has_more"] or not page["messages"]:
            return messages
        upper = min(float(m["ts"]) for m in page["messages"]) - 1e-6


async def _gmail_all_pages(client: CountingClient, query: str) -> list[dict]:
    """Every message of every matched thread, annotated with its thread id."""
    messages: list[dict] = []
    token: str | None = None
    while True:
        page = await client.call(
            "gmail__search_threads", query=query, pageSize=50, pageToken=token
        )
        for thread in page["threads"]:
            messages += [{**m, "threadId": thread["id"]} for m in thread["messages"]]
        token = page["nextPageToken"]
        if token is None:
            return messages


async def _slack_all_pages(client: CountingClient, query: str) -> list[dict]:
    matches: list[dict] = []
    cursor: str | None = None
    while True:
        page = await client.call(
            "slack__slack_search_public", query=query, limit=20, cursor=cursor
        )
        matches += page["messages"]["matches"]
        if len(matches) >= page["messages"]["total"]:
            return matches
        cursor = str(len(matches))


async def _dm_channels(client: CountingClient) -> list[dict]:
    listing = await client.call("slack__slack_search_channels", query="", limit=100)
    return [c for c in listing["channels"] if c["is_im"]]


async def _review_mail(client: CountingClient) -> list[dict]:
    """The whole mailbox for the review period. ``before:`` selects the
    threads that spoke inside it; the date filter drops any later reply that
    would ride along on such a thread."""
    return [
        message
        for message in await _gmail_all_pages(client, REVIEW_MAIL_QUERY)
        if message["date"][:10] <= REVIEW_LAST_DAY
    ]


async def _review_activities(
    client: CountingClient, matter_id: int | None = None
) -> list[dict]:
    """Every time entry of the review period, walked at Clio's 50-per-page
    cap. Clio serves activities in date order, so the period's entries are a
    prefix of the history: page until an entry lands past it, then stop."""
    scope = {} if matter_id is None else {"matter_id": matter_id}
    activities: list[dict] = []
    offset = 0
    while True:
        page = await client.call(
            "clio__list_activities", limit=50, offset=offset, **scope
        )
        activities += [
            activity for activity in page["data"] if activity["date"] <= REVIEW_LAST_DAY
        ]
        next_offset = page["meta"]["paging"].get("next_offset")
        if next_offset is None or any(
            activity["date"] > REVIEW_LAST_DAY for activity in page["data"]
        ):
            return activities
        offset = next_offset


async def fee_dispute_reconstruction(client: CountingClient) -> None:
    truth = _oracle("fee-dispute-reconstruction")
    matters = await client.call("clio__list_matters")
    matter = next(
        m for m in matters["data"] if "Meridian" in f"{m['title']} {m['description']}"
    )

    activities = await _review_activities(client, matter_id=matter["id"])

    notes = await client.call("clio__list_notes", matter_id=matter["id"])
    assert any(len(n["detail"]) > 400 for n in notes["data"]), "resolution note"

    cutoff_hits = await client.call("slack__slack_search_public", query="cutoff")
    cutoff_texts = [m["text"] for m in cutoff_hits["messages"]["matches"]]
    assert any("April 3" in t and "Meridian" in t for t in cutoff_texts), "cutoff"

    challenge = await _gmail_all_pages(client, "April invoice")
    assert any(m["date"][:10] == truth["challenge_date"] for m in challenge)

    coverage: set[str] = set()
    gmail_support: dict[str, set[str]] = {}
    for marker in S2_MARKERS:
        query = f"{marker} after:2026/04/04 before:2026/05/01"
        for message in await _gmail_all_pages(client, query):
            if marker in f"{message['subject']} {message['plaintextBody']}".lower():
                message_day = message["date"][:10]
                coverage.add(message_day)
                gmail_support.setdefault(message_day, set()).add(message["id"])
    slack_support: dict[str, set[str]] = {}
    for marker in S2_MARKERS:
        query = f"{marker} after:2026-04-03 before:2026-05-01"
        for message in await _slack_all_pages(client, query):
            if marker in message["text"].lower():
                message_day = _ts_day(message["ts"])
                coverage.add(message_day)
                slack_support.setdefault(message_day, set()).add(message["ts"])

    oldest, latest = _day_seconds("2026-04-04"), _day_seconds("2026-05-01")
    for dm in await _dm_channels(client):
        for message in await _read_window(client, dm["id"], oldest, latest):
            lowered = message["text"].lower()
            if any(marker in lowered for marker in S2_MARKERS):
                message_day = _ts_day(message["ts"])
                coverage.add(message_day)
                slack_support.setdefault(message_day, set()).add(message["ts"])

    window = [a for a in activities if "2026-04-03" < a["date"] <= "2026-04-30"]
    orphans = sorted(a["id"] for a in window if a["date"] not in coverage)
    certified_orphans = sorted(
        entry_id
        for unsupported_day in truth["unsupported_days"]
        for entry_id in unsupported_day["entry_ids"]
    )
    assert orphans == certified_orphans, orphans
    by_day: dict[str, list[dict]] = {}
    for activity in window:
        by_day.setdefault(activity["date"], []).append(activity)
    support_audit = [
        {
            "date": day,
            "entry_ids": [activity["id"] for activity in entries],
            "entry_count": len(entries),
            "minutes": sum(activity["quantity"] for activity in entries) // 60,
            "billed_cents": sum(
                0 if activity["total"] is None else round(activity["total"] * 100)
                for activity in entries
            ),
            "gmail_message_ids": sorted(gmail_support.get(day, set())),
            "slack_message_ts": sorted(slack_support.get(day, set())),
            "supported": day in coverage,
        }
        for day, entries in sorted(by_day.items())
    ]
    assert support_audit == truth["support_audit"]
    disputed = [
        a
        for a in window
        if ("diligence" in a["note"].lower() or "data room" in a["note"].lower())
    ]
    assert sum(a["quantity"] for a in disputed) // 60 == truth["total_minutes"]


async def standard_drift(client: CountingClient) -> None:
    truth = _truth("standard-drift")
    oracle = _oracle("standard-drift")
    workspaces = await client.call("imanage__search_workspaces", criteria="")
    firm = next(w for w in workspaces if "firm" in w["name"].lower())
    children = await client.call(
        "imanage__get_container_children", container_id=firm["id"]
    )
    ndas = sorted(
        (d for d in children["data"] if "/vendor-ndas/" in d["path"]),
        key=lambda d: d["path"],
    )
    assert len(ndas) == 9
    playbook = next(d for d in children["data"] if "vendor-nda-playbook" in d["path"])
    playbook_head = await client.call(
        "imanage__download_document", document_id=playbook["id"]
    )
    assert "three (3) years" in playbook_head["content"]

    # Playbook rule 5 authority. Titles come from the chat directory --
    # Clio's user record only says Attorney or NonAttorney, which cannot
    # tell a partner from Of Counsel, so the reference path reads the one
    # surface that carries the title.
    users = await client.call("slack__slack_search_users", query="partner", limit=100)
    partners = [
        u for u in users["members"] if "partner" in u["profile"]["title"].lower()
    ]
    partner_names = {u["real_name"] for u in partners}
    partner_ids = {u["id"] for u in partners}
    assert partner_names, "no partner titles in the directory"

    silent: list[str] = []
    version_audit: list[dict[str, object]] = []
    for document in ndas:
        path = document["path"]
        vendor = path.rsplit("/", 1)[-1].removeprefix("mutual-nda-").removesuffix(".md")
        number = _document_number(document["id"])
        profiles = await client.call(
            "imanage__get_document_versions", document_id=f"LEGAL!{number}"
        )
        contents: list[tuple[int, str, str]] = []
        for profile in profiles["data"]:
            downloaded = await client.call(
                "imanage__download_document", document_id=profile["id"]
            )
            contents.append(
                (
                    profile["version"],
                    downloaded["content"],
                    _imanage_day(profile["edit_date"]),
                )
            )
        mail = await _gmail_all_pages(client, vendor)
        qualifying_mail = [m for m in mail if vendor in _mail_text(m)]
        # Some sign-offs never name the vendor, citing the redline only by
        # its iManage number, so the number is its own search key on both
        # written surfaces.
        by_number = await _gmail_all_pages(client, f"LEGAL!{number}")
        chat = await _slack_all_pages(client, vendor)
        chat_by_number = await _slack_all_pages(client, f"LEGAL!{number}")
        approvals = [
            (m["id"], m["date"][:10], _mail_text(m))
            for m in mail + by_number
            if any(name in m["sender"] for name in partner_names)
        ] + [
            (m["ts"], _ts_day(m["ts"]), m["text"].lower())
            for m in chat + chat_by_number
            if m["user"] in partner_ids
        ]
        approvals = [
            entry
            for entry in approvals
            if any(
                marker in entry[2]
                for marker in ("approved", "approval", "signed off", "go ahead")
            )
            and (vendor in entry[2] or f"legal!{number}" in entry[2])
        ]
        contents.sort()
        for (_, previous, _), (version, current, day) in zip(
            contents, contents[1:], strict=False
        ):
            if previous == current:
                change_class = "unchanged"
            elif _strip_notices(previous) == _strip_notices(current):
                change_class = "notices_only"
            else:
                change_class = "substantive"
            email_ids = sorted(
                m["id"] for m in qualifying_mail if m["date"][:10] == day
            )
            version_id = f"LEGAL!{number}.{version}"
            if change_class == "substantive":
                earlier = sorted(a for a in approvals if a[1] < day)
                later = sorted(a for a in approvals if a[1] >= day)
                if earlier:
                    sign_off, reference, signed = (
                        "present",
                        earlier[-1][0],
                        earlier[-1][1],
                    )
                elif later:
                    sign_off, reference, signed = (
                        "after_the_fact",
                        later[0][0],
                        later[0][1],
                    )
                else:
                    sign_off, reference, signed = "absent", "", ""
            else:
                sign_off, reference, signed = "not_required", "", ""
            version_audit.append(
                {
                    "version_id": version_id,
                    "document_path": path,
                    "date": day,
                    "change_class": change_class,
                    "email_ids": email_ids,
                    "sign_off": sign_off,
                    "sign_off_ref": reference,
                    "sign_off_date": signed,
                }
            )
            if change_class == "substantive" and not email_ids:
                silent.append(version_id)
    assert sorted(silent) == sorted(truth["silent_versions"]), silent
    assert _canonical_records(version_audit) == _canonical_records(
        oracle["version_audit"]
    ), version_audit
    assert len(version_audit) == oracle["versions_reviewed"]
    assert (
        sum(item["change_class"] == "substantive" for item in version_audit)
        == oracle["substantive_versions"]
    )
    assert (
        sum(item["change_class"] == "notices_only" for item in version_audit)
        == oracle["notices_only_versions"]
    )
    assert (
        sum(item["change_class"] == "unchanged" for item in version_audit)
        == oracle["unchanged_versions"]
    )
    assert (
        sum(
            item["change_class"] == "substantive" and bool(item["email_ids"])
            for item in version_audit
        )
        == oracle["covered_substantive_versions"]
    )
    assert len(silent) == oracle["silent_substantive_versions"]
    assert (
        sum(len(item["email_ids"]) for item in version_audit)
        == oracle["covering_email_count"]
    )


def _dropped_block_exists(contents: list[str]) -> bool:
    """A substantial block held across two consecutive versions, then
    vanished for good — the solve.sh drop rule."""
    blocks: set[str] = set()
    for content in contents:
        blocks.update(b.strip() for b in content.split("\n\n") if len(b.strip()) >= 120)
    for block in blocks:
        presence = [block in content for content in contents]
        absents = [
            i for i, present in enumerate(presence) if not present and any(presence[:i])
        ]
        if not absents:
            continue
        first_absent = absents[0]
        if first_absent < 2 or not presence[first_absent - 2]:
            continue
        if any(presence[first_absent:]):
            continue
        return True
    return False


async def vanished_clause(client: CountingClient) -> None:
    truth = _truth("vanished-clause")
    oracle = _oracle("vanished-clause")
    workspaces = await client.call("imanage__search_workspaces", criteria="")
    documents: list[dict] = []
    for workspace in workspaces:
        children = await client.call(
            "imanage__get_container_children", container_id=workspace["id"]
        )
        documents += children["data"]
    multi = [d for d in documents if int(str(d["id"]).rsplit(".", 1)[1]) >= 2]
    assert len(multi) == 32

    unreviewed: list[str] = []
    revision_audit: list[dict[str, object]] = []
    clean: list[int] = []
    drop_path: str | None = None
    for document in multi:
        number = _document_number(document["id"])
        basename = document["path"].rsplit("/", 1)[-1]
        if basename.startswith("mutual-nda-"):
            markers = (basename.removeprefix("mutual-nda-").removesuffix(".md"),)
        else:
            markers = MENTION_MARKERS[basename]
        profiles = await client.call(
            "imanage__get_document_versions", document_id=f"LEGAL!{number}"
        )
        contents: list[tuple[int, str, str]] = []
        for profile in profiles["data"]:
            downloaded = await client.call(
                "imanage__download_document", document_id=profile["id"]
            )
            contents.append(
                (
                    profile["version"],
                    downloaded["content"],
                    _imanage_day(profile["edit_date"]),
                )
            )
        mail = await _gmail_all_pages(client, markers[0])
        qualifying_mail = [
            m for m in mail if any(marker in _mail_text(m) for marker in markers)
        ]
        mail_days = {m["date"][:10] for m in qualifying_mail}
        chat = await _slack_all_pages(client, f'"{markers[0]}"')
        qualifying_chat = [
            m for m in chat if any(marker in m["text"].lower() for marker in markers)
        ]
        chat_days = {_ts_day(m["ts"]) for m in qualifying_chat}
        contents.sort()
        for version, _, day in contents[1:]:
            email_ids = sorted(
                m["id"] for m in qualifying_mail if m["date"][:10] == day
            )
            public_slack_ts = sorted(
                m["ts"] for m in qualifying_chat if _ts_day(m["ts"]) == day
            )
            version_id = f"LEGAL!{number}.{version}"
            status = "covered" if day in mail_days or day in chat_days else "unreviewed"
            revision_audit.append(
                {
                    "version_id": version_id,
                    "document_number": number,
                    "document_path": document["path"],
                    "date": day,
                    "coverage_status": status,
                    "email_ids": email_ids,
                    "public_slack_ts": public_slack_ts,
                }
            )
            if status == "unreviewed":
                unreviewed.append(version_id)
        if _dropped_block_exists([content for _, content, _ in contents]):
            drop_path = document["path"]
        else:
            clean.append(number)
    assert sorted(unreviewed) == sorted(truth["unreviewed_revisions"]), unreviewed

    assert _canonical_records(revision_audit) == _canonical_records(
        oracle["revision_audit"]
    ), revision_audit
    assert len(revision_audit) == oracle["revisions_reviewed"]
    assert (
        sum(item["coverage_status"] == "covered" for item in revision_audit)
        == oracle["covered_revisions"]
    )
    assert len(unreviewed) == oracle["unreviewed_revision_count"]
    assert (
        sum(
            len(item["email_ids"]) + len(item["public_slack_ts"])
            for item in revision_audit
        )
        == oracle["covering_communications"]
    )
    assert drop_path == truth["document_path"]
    assert sorted(clean) == sorted(truth["clean_documents"]), clean


async def client_departure_postmortem(client: CountingClient) -> None:
    truth = _truth("client-departure-postmortem")
    arc = await _slack_all_pages(client, "Cascadia")
    milestones = [m for m in arc if "Cascadia supplier dispute" not in m["text"]]
    happy = next(m for m in milestones if "happy" in m["text"])
    assert truth["happy_update_ts_prefix"].startswith(_ts_prefix(happy["ts"]))
    reactions = sum(r["count"] for r in happy.get("reactions", []))
    assert reactions == truth["happy_update_reactions"]

    matters = await client.call("clio__list_matters")
    # Clio gives the substantive prose to `description` and keeps the
    # one-line matter label — the part that names the client — in `title`.
    cascadia = next(
        m
        for m in matters["data"]
        if "Cascadia" in f"{m['title'] or ''} {m['description'] or ''}"
    )
    assert cascadia["close_date"] == truth["matter_closed_date"]

    users = await client.call("clio__list_users")
    firm_emails = {u["email"] for u in users["data"]}

    mail = await _gmail_all_pages(client, "Cascadia")
    by_thread: dict[str, list[dict]] = {}
    for message in mail:
        by_thread.setdefault(message["threadId"], []).append(message)
    unanswered: list[str] = []
    for messages in by_thread.values():
        messages.sort(key=lambda m: m["date"])
        for index, message in enumerate(messages):
            if _sender_email(message) in firm_emails:
                continue
            if "Cascadia" not in message["subject"]:
                continue
            answered = any(
                _sender_email(later) in firm_emails for later in messages[index + 1 :]
            )
            if not answered:
                unanswered.append(message["id"])
    assert sorted(unanswered) == sorted(truth["unanswered_client_emails"]), unanswered

    letter = await client.call("imanage__search", query="disengagement")
    assert any(
        str(hit.get("path", "")).endswith(truth["letter_path_suffix"])
        for hit in letter["results"]
    )


async def operative_deadline(client: CountingClient) -> None:
    truth = _truth("operative-deadline")
    mail = await _gmail_all_pages(client, "Arroyo")
    notices = sorted(
        (m for m in mail if "hearing setting" in m["subject"]),
        key=lambda m: m["date"],
    )
    assert len(notices) == 3

    matters = await client.call("clio__list_matters")
    arroyo = next(
        m
        for m in matters["data"]
        if "Arroyo" in f"{m['title'] or ''} {m['description'] or ''}"
    )
    assert arroyo["display_number"].startswith("00008")

    # Bounded like the DM sweep below: the docket review closes with the
    # quarter, so the public surfaces are read over the same span.
    public = await _slack_all_pages(client, f"Arroyo before:{REVIEW_END_EXCLUSIVE}")

    dms = await _dm_channels(client)
    users = await client.call("slack__slack_search_users", query="", limit=100)
    names = {u["id"]: u["real_name"] for u in users["members"]}
    docket_dm = None
    for dm in dms:
        members = await client.call(
            "slack__slack_list_channel_members", channel_id=dm["id"]
        )
        member_names = {names[m] for m in members["members"]}
        if member_names == {"Grace Adeyemi", "Samuel Marsh"}:
            docket_dm = dm["id"]
    assert docket_dm is not None

    correction_window = await _read_window(
        client, docket_dm, _day_seconds("2026-06-08"), _day_seconds("2026-06-17")
    )
    correction = next(m for m in correction_window if "moved again" in m["text"])
    assert _ts_prefix(correction["ts"]) == truth["correction_ts_prefix"]

    # Stale sweep: the public surfaces are fully in hand; every DM is
    # checked once over the post-first-supersession span.
    dm_texts: list[tuple[str, str, int]] = []
    for dm in dms:
        for message in await _read_window(
            client, dm["id"], _day_seconds("2026-04-18"), _day_seconds("2026-07-01")
        ):
            dm_texts.append((message["ts"], message["text"], int(float(message["ts"]))))

    supersession_seconds = {
        "2026-04-28": _mail_seconds(notices[1]["date"]),
        "2026-05-20": _mail_seconds(notices[2]["date"]),
        "2026-06-18": int(float(correction["ts"])),
    }
    forms = {
        "2026-04-28": ("april 28", "the 28th"),
        "2026-05-20": ("may 20", "the 20th"),
        "2026-06-18": ("june 18", "the 18th"),
    }
    surfaces: list[tuple[str, str, int]] = [
        (
            m["id"],
            f"{m['subject']} {m['plaintextBody']}".lower(),
            _mail_seconds(m["date"]),
        )
        for m in mail
    ]
    surfaces += [(m["ts"], m["text"].lower(), int(float(m["ts"]))) for m in public]
    surfaces += [(ts, text.lower(), when) for ts, text, when in dm_texts]
    stale: list[str] = []
    for identity, text, when in surfaces:
        if not any(token in text for token in ARROYO_TOKENS):
            continue
        for superseded, cutover in supersession_seconds.items():
            hits = [form for form in forms[superseded] if form in text]
            if not hits or when <= cutover:
                continue
            if any(f"not {form}" in text for form in hits):
                continue
            stale.append(identity)
    matchers = list(truth["stale_calendar_refs"])
    assert len(stale) == len(matchers), stale
    for identity in stale:
        matched = next(
            (
                m
                for m in matchers
                if identity == m.get("id")
                or identity.startswith(m.get("ts_prefix", "\0"))
            ),
            None,
        )
        assert matched is not None, identity
        matchers.remove(matched)


async def _conversation_listing(client: CountingClient) -> list[dict]:
    listing = await client.call("slack__slack_search_channels", query="", limit=100)
    return listing["channels"]


async def _read_all(
    client: CountingClient, conversations: list[dict]
) -> dict[str, list[dict]]:
    """Each conversation read end to end over the review period. Chat search
    never returns direct messages, so the lanes have to be opened one by one
    and the long ones paged."""
    oldest = _day_seconds(REVIEW_FIRST_DAY)
    latest = _day_seconds(REVIEW_END_EXCLUSIVE.isoformat())
    return {
        conversation["id"]: await _read_window(
            client, conversation["id"], oldest, latest
        )
        for conversation in conversations
    }


async def billing_hygiene_audit(client: CountingClient) -> None:
    truth = _truth("billing-hygiene-audit")
    oracle = _oracle("billing-hygiene-audit")
    users = await client.call("clio__list_users")
    activities = await _review_activities(client)
    # list_notes serves the whole file in one page; the period bound is the
    # caller's, exactly as it is for the entries the notes corroborate.
    notes = {
        "data": [
            note
            for note in (await client.call("clio__list_notes"))["data"]
            if note["date"] <= REVIEW_LAST_DAY
        ]
    }
    billable = [activity for activity in activities if not activity["non_billable"]]
    assert len(activities) == 4_306, len(activities)
    assert len(billable) == truth["entries_reviewed"], len(billable)
    assert (
        len({activity["user"]["name"] for activity in billable})
        == truth["timekeepers_reviewed"]
    )

    # The footprint index: every surface a person can write on, per day.
    footprint: set[tuple[str, str]] = set()
    mail_messages = await _review_mail(client)
    for message in mail_messages:
        footprint.add((_sender_email(message), message["date"][:10]))
    conversations = await _conversation_listing(client)
    history = await _read_all(client, conversations)
    chat_users = await client.call("slack__slack_search_users", query="", limit=100)
    emails = {user["id"]: user["profile"]["email"] for user in chat_users["members"]}
    for messages in history.values():
        for message in messages:
            footprint.add((emails[message["user"]], _ts_day(message["ts"])))
    assert len(conversations) >= 16, conversations

    by_name = {user["name"]: user["email"] for user in users["data"]}
    events = {
        (
            activity["matter"]["display_number"],
            activity["user"]["name"],
            activity["date"],
        )
        for activity in activities
    }
    events.update(
        (note["matter"]["display_number"], note["author"]["name"], note["date"])
        for note in notes["data"]
    )
    participants: dict[tuple[str, str], set[str]] = {}
    for matter, person, event_day in events:
        participants.setdefault((matter, event_day), set()).add(person)

    anomalous = [
        activity
        for activity in billable
        if (by_name[activity["user"]["name"]], activity["date"]) not in footprint
        and participants[(activity["matter"]["display_number"], activity["date"])]
        - {activity["user"]["name"]}
    ]
    grouped: dict[tuple[str, str], list[dict]] = {}
    for activity in anomalous:
        grouped.setdefault((activity["date"], activity["user"]["name"]), []).append(
            activity
        )
    days = [
        {
            "date": event_day,
            "timekeeper": person,
            "entry_ids": [activity["id"] for activity in entries],
            "matter_numbers": list(
                dict.fromkeys(
                    activity["matter"]["display_number"] for activity in entries
                )
            ),
            "minutes": sum(activity["quantity"] for activity in entries) // 60,
            "billed_cents": sum(
                0
                if activity["total"] is None
                else round(float(activity["total"]) * 100)
                for activity in entries
            ),
        }
        for (event_day, person), entries in sorted(grouped.items())
    ]
    assert days == truth["anomalous_timekeeper_days"], days
    assert len(anomalous) == truth["anomalous_entry_count"]
    assert (
        sum(activity["quantity"] for activity in anomalous) // 60
        == truth["anomalous_minutes_total"]
    )
    assert (
        sum(round(float(activity["total"]) * 100) for activity in anomalous)
        == truth["anomalous_billed_cents_total"]
    )
    phantom = [
        note["id"]
        for note in notes["data"]
        if (by_name[note["author"]["name"]], note["date"]) not in footprint
        and participants[(note["matter"]["display_number"], note["date"])]
        - {note["author"]["name"]}
    ]
    assert sorted(phantom) == truth["phantom_note_ids"], phantom

    sent_gmail: dict[tuple[str, str], list[str]] = {}
    for message in sorted(mail_messages, key=lambda item: _mail_seconds(item["date"])):
        key = (_sender_email(message), message["date"][:10])
        sent_gmail.setdefault(key, []).append(message["id"])
    sent_slack: dict[tuple[str, str], list[str]] = {}
    chat_messages = sorted(
        (message for messages in history.values() for message in messages),
        key=lambda item: float(item["ts"]),
    )
    for message in chat_messages:
        key = (emails[message["user"]], _ts_day(message["ts"]))
        sent_slack.setdefault(key, []).append(message["ts"])
    grouped_billable: dict[tuple[str, str], list[dict]] = {}
    for activity in billable:
        grouped_billable.setdefault(
            (activity["date"], activity["user"]["name"]), []
        ).append(activity)
    daily_review = []
    for (activity_day, person), entries in sorted(grouped_billable.items()):
        corroborated = [
            activity
            for activity in entries
            if participants[(activity["matter"]["display_number"], activity_day)]
            - {person}
        ]
        gmail_ids = sent_gmail.get((by_name[person], activity_day), [])
        slack_ts = sent_slack.get((by_name[person], activity_day), [])
        if gmail_ids or slack_ts:
            disposition = "cleared_by_communication"
        elif corroborated:
            disposition = "anomalous"
        else:
            disposition = "cleared_no_corroboration"
        daily_review.append(
            {
                "date": activity_day,
                "timekeeper": person,
                "billable_entry_ids": [activity["id"] for activity in entries],
                "sent_gmail_ids": gmail_ids,
                "sent_slack_ts": slack_ts,
                "corroborated_entry_ids": [activity["id"] for activity in corroborated],
                "corroborated_matter_numbers": list(
                    dict.fromkeys(
                        activity["matter"]["display_number"]
                        for activity in corroborated
                    )
                ),
                "disposition": disposition,
            }
        )
    assert len(daily_review) == truth["person_days_reviewed"]
    assert (
        sum(
            record["disposition"] == "cleared_by_communication"
            for record in daily_review
        )
        == truth["cleared_by_communication"]
    )
    assert (
        sum(
            record["disposition"] == "cleared_no_corroboration"
            for record in daily_review
        )
        == truth["cleared_no_corroboration"]
    )
    assert _canonical_records(daily_review) == _canonical_records(
        oracle["daily_review"]
    ), daily_review


async def _one_to_one_request_audit(
    client: CountingClient,
    request: str,
    *,
    custody_deadline: bool = False,
) -> list[dict]:
    """The shared discovery path for the one-to-one request audits: every
    lane opened and paged, its two members resolved, and the mailbox swept
    because coming back can be mail rather than chat."""
    chat_users = await client.call("slack__slack_search_users", query="", limit=100)
    names = {user["id"]: user["real_name"] for user in chat_users["members"]}
    emails = {user["id"]: user["profile"]["email"] for user in chat_users["members"]}

    lanes = [c for c in await _conversation_listing(client) if c["is_im"]]
    history = await _read_all(client, lanes)

    membership: dict[str, set[str]] = {}
    for lane in lanes:
        members = await client.call(
            "slack__slack_list_channel_members", channel_id=lane["id"]
        )
        membership[lane["id"]] = set(members["members"])

    mailed: list[tuple[str, str, int, str]] = []
    for message in await _review_mail(client):
        for recipient in message["toRecipients"] + message["ccRecipients"]:
            mailed.append(
                (
                    _sender_email(message),
                    recipient.split("<")[-1].rstrip(">"),
                    _mail_seconds(message["date"]),
                    message["id"],
                )
            )

    requests: list[dict] = []
    for lane in lanes:
        messages = sorted(history[lane["id"]], key=lambda m: float(m["ts"]))
        for position, message in enumerate(messages):
            if message["text"].strip().lower() != request:
                continue
            (asked_of,) = membership[lane["id"]] - {message["user"]}
            asked_on = date.fromisoformat(_ts_day(message["ts"]))
            asked_at = int(float(message["ts"]))
            next_day = _next_working_day(asked_on).isoformat()
            chat_candidates = {
                (int(float(later["ts"])), "slack", later["ts"])
                for later in messages[position + 1 :]
                if later["user"] == asked_of and int(float(later["ts"])) > asked_at
            }
            mail_candidates = {
                (timestamp, "gmail", message_id)
                for sender, recipient, timestamp, message_id in mailed
                if sender == emails[asked_of]
                and recipient == emails[message["user"]]
                and timestamp > asked_at
            }
            candidates = chat_candidates | mail_candidates
            first_response = min(candidates, default=None)
            if custody_deadline:
                same_day, next_working_day, in_window = _custody_outcome(
                    asked_on,
                    asked_at,
                    {timestamp for timestamp, _, _ in candidates},
                )
            else:
                first_day = (
                    date.fromisoformat(_ts_day(str(first_response[0])))
                    if first_response
                    else None
                )
                same_day = first_day == asked_on
                in_window = first_day is not None and first_day <= date.fromisoformat(
                    next_day
                )
                next_working_day = in_window and not same_day
            requests.append(
                {
                    "ts": message["ts"],
                    "date": asked_on.isoformat(),
                    "asked_by": names[message["user"]],
                    "asked_of": names[asked_of],
                    "lanes": len(lanes),
                    "same_day": same_day,
                    "next_working_day": next_working_day,
                    "in_window": in_window,
                    "first_response_surface": (
                        first_response[1] if first_response else "none"
                    ),
                    "first_response_id": first_response[2] if first_response else "",
                    "first_response_at": (
                        _seconds_iso(first_response[0]) if first_response else ""
                    ),
                }
            )
    return requests


async def second_read_audit(client: CountingClient) -> None:
    truth = _truth("second-read-audit")
    oracle = _oracle("second-read-audit")
    requests = await _one_to_one_request_audit(client, SECOND_READ_REQUEST)
    assert len(requests) == truth["requests_reviewed"], len(requests)
    assert requests[0]["lanes"] == truth["conversations_reviewed"]
    unanswered = sorted(_ts_prefix(r["ts"]) for r in requests if not r["in_window"])
    assert unanswered == truth["unanswered_request_ts_prefixes"], unanswered
    later_pickups = sorted(
        _ts_prefix(r["ts"]) for r in requests if r["in_window"] and not r["same_day"]
    )
    assert later_pickups == truth["came_back_later_prefixes"], later_pickups
    assert sum(1 for r in requests if r["same_day"]) == truth["answered_same_day"]
    assert (
        sum(1 for r in requests if r["next_working_day"])
        == oracle["answered_next_working_day"]
    )
    assert (
        sum(1 for r in requests if not r["in_window"])
        == oracle["unanswered_by_deadline"]
    )
    response_audit = [
        {
            "request_ts": request["ts"],
            "request_date": request["date"],
            "asked_by": request["asked_by"],
            "asked_of": request["asked_of"],
            "first_response_surface": request["first_response_surface"],
            "first_response_id": request["first_response_id"],
            "first_response_at": request["first_response_at"],
            "outcome": (
                "same_day"
                if request["same_day"]
                else "next_working_day"
                if request["next_working_day"]
                else "unanswered"
            ),
        }
        for request in sorted(requests, key=lambda item: float(item["ts"]))
    ]
    assert _canonical_records(response_audit) == _canonical_records(
        oracle["response_audit"]
    ), response_audit


async def visitor_log_audit(client: CountingClient) -> None:
    truth = _truth("visitor-log-audit")
    oracle = _oracle("visitor-log-audit")
    requests = await _one_to_one_request_audit(
        client, SHEET_REQUEST, custody_deadline=True
    )
    assert len(requests) == truth["requests_reviewed"], len(requests)
    assert requests[0]["lanes"] == truth["conversations_reviewed"]
    breaches = sorted(
        (
            {
                "ts": request["ts"],
                "date": request["date"],
                "asked_by": request["asked_by"],
                "asked_of": request["asked_of"],
                "resolution": (
                    "next_working_day" if request["next_working_day"] else "unresolved"
                ),
            }
            for request in requests
            if not request["same_day"]
        ),
        key=lambda record: float(record["ts"]),
    )
    assert breaches == truth["same_day_breaches"], breaches
    assert [record["ts"] for record in breaches] == truth["same_day_breach_ts"]
    next_day = [
        record["ts"]
        for record in breaches
        if record["resolution"] == "next_working_day"
    ]
    assert next_day == truth["returned_next_working_day_ts"], next_day
    unresolved = [
        record["ts"] for record in breaches if record["resolution"] == "unresolved"
    ]
    assert unresolved == truth["unresolved_ts"], unresolved
    assert (
        sum(1 for request in requests if request["same_day"])
        == truth["returned_same_day"]
    )
    assert len(next_day) == truth["returned_next_working_day"]
    assert len(unresolved) == truth["unresolved_by_followup"]
    custody_audit = [
        {
            "request_ts": request["ts"],
            "request_date": request["date"],
            "asked_by": request["asked_by"],
            "asked_of": request["asked_of"],
            "first_return_surface": request["first_response_surface"],
            "first_return_id": request["first_response_id"],
            "first_return_at": request["first_response_at"],
            "outcome": (
                "same_day"
                if request["same_day"]
                else "next_working_day"
                if request["next_working_day"]
                else "unresolved"
            ),
        }
        for request in sorted(requests, key=lambda item: float(item["ts"]))
    ]
    assert _canonical_records(custody_audit) == _canonical_records(
        oracle["custody_audit"]
    ), custody_audit


FLOORS = {
    "billing-hygiene-audit": billing_hygiene_audit,
    "visitor-log-audit": visitor_log_audit,
    "second-read-audit": second_read_audit,
    "fee-dispute-reconstruction": fee_dispute_reconstruction,
    "standard-drift": standard_drift,
    "vanished-clause": vanished_clause,
    "client-departure-postmortem": client_departure_postmortem,
    "operative-deadline": operative_deadline,
}


async def measure(task: str) -> int:
    async with open_workspace(TASKS / task / "bundle") as workspace:
        client = CountingClient(workspace)
        await FLOORS[task](client)
    floor = client.calls + WRITE_AND_FINISH
    return floor


async def main(argv: list[str]) -> int:
    tasks = argv or sorted(FLOORS)
    for task in tasks:
        floor = await measure(task)
        print(f"{task}: floor={floor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
