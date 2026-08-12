"""Reference oracle for visitor-log-audit; emits the certified deliverable.

Nothing here is a table of answers. Every row's outcome is DERIVED from the
record: the request instants are read from the one-to-one DMs, the holder's
*return* of the sign-in sheet is located by parsing the reply prose (a message
counts as the return only when it says the sheet is physically back at the
front desk -- one of RETURN_MARKERS in chat, or a directed "Sign-in sheet
returned" email -- never a bare acknowledgement that the holder still has it),
each return is matched to the request instance it answers by timing across
surfaces, and the outcome (same_day / next_working_day / unresolved) falls out
of the Pacific calendar date of that first return against a holiday-aware
next-working-day custody deadline. Timestamps are stored as machine seconds;
the day boundaries are Pacific, so an evening return is still the same working
day even though its UTC date is already the next one.

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
PACIFIC = ZoneInfo("America/Los_Angeles")
REQUEST = "do you still have the sign-in sheet from yesterday?"
CUTOFF = (date(2026, 7, 1) - EPOCH).days * 86_400

# A holder message is the *return* only if it says the sheet is physically back
# at the front desk. In chat the return carries one of these verbatim markers;
# ordinary acknowledgements ("still have it up here, I'll run it down later")
# and chatter carry none and are not the return.
RETURN_MARKERS = (
    "back at reception",
    "back on the reception desk",
    "back on the front desk",
    "back in the reception binder",
    "back on the sign-in clipboard",
    "back downstairs at reception",
    "returned it to the front desk",
    "back on the desk out front",
)
# A directed email is a cross-surface return iff its subject carries this marker.
EMAIL_MARKER = "sign-in sheet returned"

# Federal holidays that fall on a weekday inside the March-June review window;
# the firm treats them as non-working days when computing the custody deadline.
HOLIDAYS = frozenset({date(2026, 5, 25), date(2026, 6, 19)})


def rows(
    state: Path, database: str, sql: str, *params: DatabaseValue
) -> list[DatabaseRow]:
    path = state / database
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(timestamp: int) -> date:
    return EPOCH + timedelta(days=timestamp // 86_400)


def is_workday(moment: date) -> bool:
    return moment.weekday() < 5 and moment not in HOLIDAYS


def next_working_day(moment: date) -> date:
    candidate = moment + timedelta(days=1)
    while not is_workday(candidate):
        candidate += timedelta(days=1)
    return candidate


def iso_datetime(timestamp: int) -> str:
    return (
        datetime(2026, 3, 2, tzinfo=PACIFIC) + timedelta(seconds=timestamp)
    ).isoformat()


def is_return(body: str) -> bool:
    lowered = body.lower()
    return any(marker in lowered for marker in RETURN_MARKERS)


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
        "WHERE time < ? ORDER BY time, ts",
        CUTOFF,
    ):
        lane = str(conversation_id)
        if lane in conversations:
            history.setdefault(lane, []).append(
                (str(sender), str(body), int(timestamp), str(ts))
            )

    # Directed mail: sender, recipients, time, message_id, and subject, so a
    # "Sign-in sheet returned" return can be recognized and matched to its asker.
    recipients: dict[str, set[str]] = {}
    for message_id, person_id in rows(
        state, "gmail.db", "SELECT message_id, person_id FROM recipients"
    ):
        recipients.setdefault(str(message_id), set()).add(str(person_id))
    directed_mail: list[tuple[str, set[str], int, str, str]] = [
        (
            str(sender),
            recipients.get(str(message_id), set()),
            int(timestamp),
            str(message_id),
            str(subject),
        )
        for message_id, sender, subject, timestamp in rows(
            state,
            "gmail.db",
            "SELECT message_id, sender, subject, time FROM messages WHERE time < ?",
            CUTOFF,
        )
    ]

    # Every sheet request, with its asker, holder, and instant.
    requests: list[dict[str, object]] = []
    for conversation_id, messages in history.items():
        lane_members = membership[conversation_id]
        if len(lane_members) != 2:
            continue
        for sender, body, request_time, ts in messages:
            if body.strip().lower() != REQUEST:
                continue
            (asked_of,) = lane_members - {sender}
            requests.append(
                {
                    "ts": ts,
                    "time": request_time,
                    "asked_by": sender,
                    "asked_of": asked_of,
                }
            )

    # Every holder return, as (time, surface, id, asker, holder). A chat return
    # is a marker-bearing DM; its asker is the other lane member. An email return
    # is a "Sign-in sheet returned" directed message; its asker is the recipient.
    returns: list[tuple[int, str, str, str, str]] = []
    for conversation_id, messages in history.items():
        lane_members = membership[conversation_id]
        if len(lane_members) != 2:
            continue
        for sender, body, timestamp, ts in messages:
            if is_return(body):
                (asker,) = lane_members - {sender}
                returns.append((timestamp, "slack", ts, asker, sender))
    for sender, to_people, timestamp, message_id, subject in directed_mail:
        if EMAIL_MARKER in subject.lower():
            for asker in to_people:
                returns.append((timestamp, "gmail", message_id, asker, sender))

    # Match each return to the request instance it answers: the latest request
    # from the same asker to the same holder that precedes it. A return whose
    # asker re-sent the request answers the re-sent instance, leaving the
    # original with only its acknowledgement.
    by_pair: dict[tuple[str, str], list[int]] = {}
    for index, request in enumerate(requests):
        by_pair.setdefault(
            (str(request["asked_by"]), str(request["asked_of"])), []
        ).append(index)
    for indices in by_pair.values():
        indices.sort(key=lambda index: int(requests[index]["time"]))
    for request in requests:
        request["return"] = None
    for timestamp, surface, identifier, asker, holder in sorted(returns):
        owner = None
        for index in by_pair.get((asker, holder), ()):
            if int(requests[index]["time"]) < timestamp:
                owner = index
        if owner is None:
            continue
        current = requests[owner]["return"]
        if current is None or timestamp < current[0]:
            requests[owner]["return"] = (timestamp, surface, identifier)

    # Classify each request against the holiday-aware custody deadline.
    records: list[dict[str, object]] = []
    for request in requests:
        request_day = day_of(int(request["time"]))
        deadline = next_working_day(request_day)
        returned = request["return"]
        if returned is None:
            surface, identifier, at, outcome = "none", "", "", "unresolved"
        else:
            when, surface, identifier = returned
            at = iso_datetime(when)
            return_day = day_of(when)
            if return_day == request_day:
                outcome = "same_day"
            elif return_day <= deadline:
                outcome = "next_working_day"
            else:
                outcome = "unresolved"
        records.append(
            {
                "request_ts": request["ts"],
                "request_date": request_day.isoformat(),
                "asked_by": names[str(request["asked_by"])],
                "asked_of": names[str(request["asked_of"])],
                "first_return_surface": surface,
                "first_return_id": identifier,
                "first_return_at": at,
                "outcome": outcome,
            }
        )

    records.sort(key=lambda record: float(str(record["request_ts"])))
    breach_audit = [record for record in records if record["outcome"] != "same_day"]
    breaches = [
        {
            "ts": record["request_ts"],
            "date": record["request_date"],
            "asked_by": record["asked_by"],
            "asked_of": record["asked_of"],
            "resolution": record["outcome"],
        }
        for record in breach_audit
    ]
    returned_next = [
        str(record["request_ts"])
        for record in breach_audit
        if record["outcome"] == "next_working_day"
    ]
    unresolved = [
        str(record["request_ts"])
        for record in breach_audit
        if record["outcome"] == "unresolved"
    ]

    if len(records) != 71 or len(history) != 12:
        raise RuntimeError(
            f"expected 71 requests in 12 DM lanes, found {len(records)} in "
            f"{len(history)}"
        )
    returned_same_day = len(records) - len(breach_audit)
    if (returned_same_day, len(returned_next), len(unresolved)) != (59, 10, 2):
        raise RuntimeError(
            "expected 59 same-day returns, 10 next-working-day returns, and "
            f"2 unresolved requests; found {returned_same_day}, "
            f"{len(returned_next)}, and {len(unresolved)}"
        )

    return {
        "requests_reviewed": len(records),
        "conversations_reviewed": len(history),
        "same_day_breach_ts": [str(record["ts"]) for record in breaches],
        "same_day_breaches": breaches,
        "returned_same_day": returned_same_day,
        "returned_next_working_day": len(returned_next),
        "unresolved_by_followup": len(unresolved),
        "returned_next_working_day_ts": returned_next,
        "unresolved_ts": unresolved,
        "custody_audit": records,
    }


def main() -> int:
    state = Path(os.environ.get("WORKBENCH_STATE", "../state"))
    json.dump(build_visitor_log(state), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
