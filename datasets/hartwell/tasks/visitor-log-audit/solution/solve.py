"""Reference solution for the end-of-request-day visitor-log audit.

The module reads the offstage projections and emits the public document to
stdout. Harbor's restricted oracle runs it as the environment user; the shell
wrapper is the only component that writes into the agent workspace.
"""

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

type DatabaseValue = str | int | float | bytes | None
type DatabaseRow = tuple[DatabaseValue, ...]
type SlackMessage = tuple[str, str, int, str]

EPOCH = date(2026, 3, 2)
REQUEST = "do you still have the sign-in sheet from yesterday?"


def rows(
    state: Path, database: str, sql: str, *params: DatabaseValue
) -> list[DatabaseRow]:
    path = state / database
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(timestamp: int) -> date:
    return EPOCH + timedelta(days=timestamp // 86_400)


def next_working_day(moment: date) -> date:
    candidate = moment + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def iso_datetime(timestamp: int) -> str:
    pacific = ZoneInfo("America/Los_Angeles")
    return (
        datetime(2026, 3, 2, tzinfo=pacific) + timedelta(seconds=timestamp)
    ).isoformat()


def build_visitor_log(state: Path) -> dict[str, object]:
    names = {
        str(person_id): str(name)
        for person_id, name in rows(
            state, "slack.db", "SELECT person_id, name FROM people"
        )
    }
    conversations = {
        str(conversation_id)
        for (conversation_id,) in rows(
            state,
            "slack.db",
            "SELECT conversation_id FROM conversations WHERE kind = 'dm'",
        )
    }
    membership: dict[str, set[str]] = {}
    for conversation_id, person_id in rows(
        state, "slack.db", "SELECT conversation_id, person_id FROM members"
    ):
        membership.setdefault(str(conversation_id), set()).add(str(person_id))

    history: dict[str, list[SlackMessage]] = {}
    for conversation_id, sender, body, timestamp, ts in rows(
        state,
        "slack.db",
        "SELECT conversation_id, sender, body, time, ts FROM messages "
        "ORDER BY time, ts",
    ):
        lane = str(conversation_id)
        if lane in conversations:
            history.setdefault(lane, []).append(
                (str(sender), str(body), int(timestamp), str(ts))
            )

    recipients: dict[str, set[str]] = {}
    for message_id, person_id in rows(
        state, "gmail.db", "SELECT message_id, person_id FROM recipients"
    ):
        recipients.setdefault(str(message_id), set()).add(str(person_id))
    directed_mail: list[tuple[str, set[str], int, str]] = [
        (
            str(sender),
            recipients.get(str(message_id), set()),
            int(timestamp),
            str(message_id),
        )
        for message_id, sender, timestamp in rows(
            state, "gmail.db", "SELECT message_id, sender, time FROM messages"
        )
    ]

    requests: list[dict[str, object]] = []
    for conversation_id, messages in history.items():
        lane_members = membership[conversation_id]
        if len(lane_members) != 2:
            raise RuntimeError(
                f"expected two members in DM {conversation_id}, found "
                f"{len(lane_members)}"
            )
        for position, (asker, body, request_time, ts) in enumerate(messages):
            if body.strip().lower() != REQUEST:
                continue
            (asked_of,) = lane_members - {asker}
            candidates = [
                (timestamp, "slack", response_ts)
                for sender, _, timestamp, response_ts in messages[position + 1 :]
                if sender == asked_of and timestamp > request_time
            ]
            candidates.extend(
                (timestamp, "gmail", message_id)
                for sender, to_people, timestamp, message_id in directed_mail
                if sender == asked_of
                and asker in to_people
                and timestamp > request_time
            )
            first_response = min(candidates, default=None)
            request_day = day_of(request_time)
            response_day = None if first_response is None else day_of(first_response[0])
            if response_day == request_day:
                outcome = "same_day"
            elif response_day is not None and response_day <= next_working_day(
                request_day
            ):
                outcome = "next_working_day"
            else:
                outcome = "unresolved"
            requests.append(
                {
                    "request_ts": ts,
                    "request_date": request_day.isoformat(),
                    "asked_by": names[asker],
                    "asked_of": names[asked_of],
                    "first_return_surface": (
                        first_response[1] if first_response else "none"
                    ),
                    "first_return_id": first_response[2] if first_response else "",
                    "first_return_at": (
                        iso_datetime(first_response[0]) if first_response else ""
                    ),
                    "outcome": outcome,
                }
            )

    requests.sort(key=lambda request: float(str(request["request_ts"])))
    breach_audit = [request for request in requests if request["outcome"] != "same_day"]
    breaches = [
        {
            "ts": request["request_ts"],
            "date": request["request_date"],
            "asked_by": request["asked_by"],
            "asked_of": request["asked_of"],
            "resolution": request["outcome"],
        }
        for request in breach_audit
    ]
    returned_next = [
        str(request["request_ts"])
        for request in breach_audit
        if request["outcome"] == "next_working_day"
    ]
    unresolved = [
        str(request["request_ts"])
        for request in breach_audit
        if request["outcome"] == "unresolved"
    ]

    if len(requests) != 71 or len(history) != 12:
        raise RuntimeError(
            f"expected 71 requests in 12 DM lanes, found {len(requests)} in "
            f"{len(history)}"
        )
    returned_same_day = len(requests) - len(breach_audit)
    if (returned_same_day, len(returned_next), len(unresolved)) != (59, 10, 2):
        raise RuntimeError(
            "expected 59 same-day returns, 10 next-working-day returns, and "
            f"2 unresolved requests; found {returned_same_day}, "
            f"{len(returned_next)}, and {len(unresolved)}"
        )

    return {
        "requests_reviewed": len(requests),
        "conversations_reviewed": len(history),
        "same_day_breach_ts": [str(request["ts"]) for request in breaches],
        "same_day_breaches": breaches,
        "returned_same_day": returned_same_day,
        "returned_next_working_day": len(returned_next),
        "unresolved_by_followup": len(unresolved),
        "returned_next_working_day_ts": returned_next,
        "unresolved_ts": unresolved,
        "custody_audit": requests,
    }


def main() -> int:
    state = Path(os.environ.get("WORKBENCH_STATE", "../state"))
    json.dump(build_visitor_log(state), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
