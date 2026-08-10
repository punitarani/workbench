"""Measure each hartwell task's reference tool-path floor.

    uv run python datasets/hartwell/measure_floors.py [task-name ...]

The floor is the call count of the honest MINIMAL tool sequence — the
discovery path an informed professional who knows the tools (but not the
answers) would take through the real MCP servers — scripted here against
each task's built environment bundle and counted mechanically, one tool
call per step, no parallelism credit. Every sequence must retrieve enough of the
record to reproduce the task's graded ground truth, and each run asserts
that it did. The printed cap is 3x the floor (DECISIONS.md entry 17);
task.toml's ``[harness] max_tool_calls`` carries it. The floor includes
the write_file and finish builtins (one deliverable file per task), which
the harness counts against the same budget.
"""

import asyncio
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from workbench.adapters.harness.mcp_workspace import McpWorkspace, open_workspace

TASKS = Path(__file__).parent / "tasks"
EPOCH = date(2026, 3, 2)
WRITE_AND_FINISH = 2

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
    return (date.fromisoformat(iso) - EPOCH).days * 86_400


def _ts_day(ts: str) -> str:
    return (EPOCH + timedelta(seconds=int(float(ts)))).isoformat()


def _ts_prefix(ts: str) -> str:
    return ts.split(".")[0]


def _next_working_day(day: date) -> date:
    moment = day + timedelta(days=1)
    while moment.weekday() >= 5:
        moment += timedelta(days=1)
    return moment


def _working_days(start: date, end: date) -> int:
    count, moment = 0, start
    while moment < end:
        moment += timedelta(days=1)
        if moment.weekday() < 5:
            count += 1
    return count


def _mail_seconds(iso_datetime: str) -> int:
    moment = datetime.fromisoformat(iso_datetime)
    midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return (moment.date() - EPOCH).days * 86_400 + int(
        (moment - midnight).total_seconds()
    )


def _imanage_day(edit_date: str) -> str:
    """iManage serves true-UTC instants; the record's calendar runs on the
    epoch's own -08:00 offset, so shift back before taking the date."""
    moment = datetime.fromisoformat(edit_date.replace("Z", "+00:00"))
    return (moment - timedelta(hours=8)).date().isoformat()


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


async def fee_dispute_reconstruction(client: CountingClient) -> None:
    truth = _truth("fee-dispute-reconstruction")
    matters = await client.call("clio__list_matters")
    matter = next(m for m in matters["data"] if "Meridian" in (m["description"] or ""))

    activities: list[dict] = []
    offset = 0
    while True:
        page = await client.call(
            "clio__list_activities", matter_id=matter["id"], limit=50, offset=offset
        )
        activities += page["data"]
        next_offset = page["meta"]["paging"].get("next_offset")
        if next_offset is None:
            break
        offset = next_offset

    notes = await client.call("clio__list_notes", matter_id=matter["id"])
    assert any(len(n["detail"]) > 400 for n in notes["data"]), "resolution note"

    cutoff_hits = await client.call("slack__slack_search_public", query="cutoff")
    cutoff_texts = [m["text"] for m in cutoff_hits["messages"]["matches"]]
    assert any("April 3" in t and "Meridian" in t for t in cutoff_texts), "cutoff"

    challenge = await _gmail_all_pages(client, "April invoice")
    assert any(m["date"][:10] == truth["challenge_date"] for m in challenge)

    coverage: set[str] = set()
    for marker in S2_MARKERS:
        query = f"{marker} after:2026/04/04 before:2026/05/01"
        for message in await _gmail_all_pages(client, query):
            if marker in f"{message['subject']} {message['plaintextBody']}".lower():
                coverage.add(message["date"][:10])
    for marker in S2_MARKERS:
        query = f"{marker} after:2026-04-03 before:2026-05-01"
        for message in await _slack_all_pages(client, query):
            if marker in message["text"].lower():
                coverage.add(_ts_day(message["ts"]))

    oldest, latest = _day_seconds("2026-04-04"), _day_seconds("2026-05-01")
    for dm in await _dm_channels(client):
        for message in await _read_window(client, dm["id"], oldest, latest):
            lowered = message["text"].lower()
            if any(marker in lowered for marker in S2_MARKERS):
                coverage.add(_ts_day(message["ts"]))

    window = [a for a in activities if "2026-04-03" < a["date"] <= "2026-04-30"]
    orphans = sorted(a["id"] for a in window if a["date"] not in coverage)
    assert orphans == sorted(truth["unsupported_entry_ids"]), orphans
    disputed = [
        a
        for a in window
        if ("diligence" in a["note"].lower() or "data room" in a["note"].lower())
    ]
    assert sum(a["quantity"] for a in disputed) // 60 == truth["total_minutes"]


async def standard_drift(client: CountingClient) -> None:
    truth = _truth("standard-drift")
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

    silent: list[str] = []
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
        covered_days = {m["date"][:10] for m in mail if vendor in _mail_text(m)}
        contents.sort()
        for (_, previous, _), (version, current, day) in zip(
            contents, contents[1:], strict=False
        ):
            if previous == current:
                continue
            if _strip_notices(previous) == _strip_notices(current):
                continue
            if day not in covered_days:
                silent.append(f"LEGAL!{number}.{version}")
    assert sorted(silent) == sorted(truth["silent_versions"]), silent


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
        mail_days = {
            m["date"][:10]
            for m in mail
            if any(marker in _mail_text(m) for marker in markers)
        }
        chat = await _slack_all_pages(client, f'"{markers[0]}"')
        chat_days = {
            _ts_day(m["ts"])
            for m in chat
            if any(marker in m["text"].lower() for marker in markers)
        }
        contents.sort()
        for version, _, day in contents[1:]:
            if day not in mail_days and day not in chat_days:
                unreviewed.append(f"LEGAL!{number}.{version}")
        if _dropped_block_exists([content for _, content, _ in contents]):
            drop_path = document["path"]
        else:
            clean.append(number)
    assert sorted(unreviewed) == sorted(truth["unreviewed_revisions"]), unreviewed
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

    public = await _slack_all_pages(client, "Arroyo")

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


async def _all_activities(client: CountingClient) -> list[dict]:
    """Every time entry in the record, walked at Clio's 50-per-page cap."""
    activities: list[dict] = []
    offset = 0
    while True:
        page = await client.call("clio__list_activities", limit=50, offset=offset)
        activities += page["data"]
        next_offset = page["meta"]["paging"].get("next_offset")
        if next_offset is None:
            return activities
        offset = next_offset


async def _conversation_listing(client: CountingClient) -> list[dict]:
    listing = await client.call("slack__slack_search_channels", query="", limit=100)
    return listing["channels"]


async def _read_all(
    client: CountingClient, conversations: list[dict]
) -> dict[str, list[dict]]:
    """Each conversation read end to end. Chat search never returns direct
    messages, so the lanes have to be opened one by one and the long ones
    paged."""
    oldest, latest = _day_seconds("2026-03-02"), _day_seconds("2026-07-31")
    return {
        conversation["id"]: await _read_window(
            client, conversation["id"], oldest, latest
        )
        for conversation in conversations
    }


async def billing_hygiene_audit(client: CountingClient) -> None:
    truth = _truth("billing-hygiene-audit")
    users = await client.call("clio__list_users")
    activities = await _all_activities(client)
    notes = await client.call("clio__list_notes")
    billable = [activity for activity in activities if not activity["non_billable"]]
    assert len(activities) == 4_306, len(activities)
    assert len(billable) == truth["entries_reviewed"], len(billable)
    assert (
        len({activity["user"]["name"] for activity in billable})
        == truth["timekeepers_reviewed"]
    )

    # The footprint index: every surface a person can write on, per day.
    footprint: set[tuple[str, str]] = set()
    for message in await _gmail_all_pages(client, ""):
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


async def _one_to_one_request_audit(client: CountingClient, request: str) -> list[dict]:
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

    mailed: set[tuple[str, str, str]] = set()
    for message in await _gmail_all_pages(client, ""):
        for recipient in message["toRecipients"] + message["ccRecipients"]:
            mailed.add(
                (
                    _sender_email(message),
                    recipient.split("<")[-1].rstrip(">"),
                    message["date"][:10],
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
            window = {asked_on.isoformat(), _next_working_day(asked_on).isoformat()}
            reply_days = {
                _ts_day(later["ts"])
                for later in messages[position + 1 :]
                if later["user"] == asked_of
            }
            by_mail = any(
                (emails[asked_of], emails[message["user"]], day) in mailed
                for day in window
            )
            requests.append(
                {
                    "ts": message["ts"],
                    "date": asked_on.isoformat(),
                    "asked_by": names[message["user"]],
                    "lanes": len(lanes),
                    "same_day": asked_on.isoformat() in reply_days,
                    "in_window": bool(reply_days & window) or by_mail,
                }
            )
    return requests


async def second_read_audit(client: CountingClient) -> None:
    truth = _truth("second-read-audit")
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


async def visitor_log_audit(client: CountingClient) -> None:
    truth = _truth("visitor-log-audit")
    requests = await _one_to_one_request_audit(client, SHEET_REQUEST)
    assert len(requests) == truth["requests_reviewed"], len(requests)
    assert requests[0]["lanes"] == truth["conversations_reviewed"]
    still_open = sorted(_ts_prefix(r["ts"]) for r in requests if not r["in_window"])
    assert still_open == truth["open_handover_ts_prefixes"], still_open
    next_day = sorted(
        _ts_prefix(r["ts"]) for r in requests if r["in_window"] and not r["same_day"]
    )
    assert next_day == truth["closed_next_day_prefixes"], next_day
    assert sum(1 for r in requests if r["same_day"]) == truth["closed_same_day"]


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


async def measure(task: str) -> tuple[int, int]:
    async with open_workspace(TASKS / task / "bundle") as workspace:
        client = CountingClient(workspace)
        await FLOORS[task](client)
    floor = client.calls + WRITE_AND_FINISH
    return floor, 3 * floor


async def main(argv: list[str]) -> int:
    tasks = argv or sorted(FLOORS)
    for task in tasks:
        floor, cap = await measure(task)
        print(f"{task}: floor={floor} cap={cap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
