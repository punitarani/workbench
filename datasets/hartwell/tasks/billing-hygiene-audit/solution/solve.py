"""Reference solution for the corroborated silent-day billing audit.

The module reads the offstage tool projections and emits the public document
to stdout. Harbor's restricted oracle runs it as the environment user; the
shell wrapper remains the only component that writes into the workspace.
"""

import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

type DatabaseValue = str | int | float | bytes | None
type DatabaseRow = tuple[DatabaseValue, ...]
type Activity = tuple[int, str, str, int, int, int | None, int]
type Note = tuple[int, str, str, int]
type EventKey = tuple[str, str, date]

EPOCH = date(2026, 3, 2)


def rows(
    state: Path, database: str, sql: str, *params: DatabaseValue
) -> list[DatabaseRow]:
    path = state / database
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(timestamp: int) -> date:
    return EPOCH + timedelta(days=timestamp // 86_400)


def billed_cents(seconds: int, rate_cents: int | None, billable: int) -> int:
    if rate_cents is None or not billable:
        return 0
    public_total = round(rate_cents / 100 * seconds / 3_600, 2)
    return round(public_total * 100)


def build_hygiene(state: Path) -> dict[str, object]:
    activities: list[Activity] = [
        (
            int(activity_id),
            str(ticket_id),
            str(person),
            int(seconds),
            int(timestamp),
            None if rate_cents is None else int(rate_cents),
            int(billable),
        )
        for (
            activity_id,
            ticket_id,
            person,
            seconds,
            timestamp,
            rate_cents,
            billable,
        ) in rows(
            state,
            "clio.db",
            "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, person, "
            "quantity_seconds, time, rate_cents, billable FROM activities",
        )
    ]
    notes: list[Note] = [
        (int(note_id), str(ticket_id), str(author), int(timestamp))
        for note_id, ticket_id, author, timestamp in rows(
            state,
            "clio.db",
            "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, author, "
            "time FROM notes",
        )
    ]
    names: dict[str, str] = {
        str(person_id): str(name)
        for person_id, name in rows(
            state, "clio.db", "SELECT person_id, name FROM people"
        )
    }
    matter_numbers: dict[str, str] = {
        str(ticket_id): str(display_number)
        for ticket_id, display_number in rows(
            state, "clio.db", "SELECT ticket_id, display_number FROM matters"
        )
    }

    sent_gmail: dict[tuple[str, date], list[str]] = {}
    for message_id, sender, timestamp in rows(
        state,
        "gmail.db",
        "SELECT message_id, sender, time FROM messages ORDER BY time, message_id",
    ):
        sent_gmail.setdefault((str(sender), day_of(int(timestamp))), []).append(
            str(message_id)
        )
    sent_slack: dict[tuple[str, date], list[str]] = {}
    for ts, sender, timestamp in rows(
        state,
        "slack.db",
        "SELECT ts, sender, time FROM messages ORDER BY time, ts",
    ):
        sent_slack.setdefault((str(sender), day_of(int(timestamp))), []).append(str(ts))
    sent = set(sent_gmail) | set(sent_slack)

    events: set[EventKey] = {
        (ticket_id, person, day_of(timestamp))
        for _, ticket_id, person, _, timestamp, _, _ in activities
    }
    events.update(
        (ticket_id, author, day_of(timestamp))
        for _, ticket_id, author, timestamp in notes
    )
    participants: dict[tuple[str, date], set[str]] = {}
    for ticket_id, person, event_day in events:
        participants.setdefault((ticket_id, event_day), set()).add(person)

    billable = [activity for activity in activities if activity[6]]
    anomalous = [
        activity
        for activity in billable
        if (activity[2], day_of(activity[4])) not in sent
        and participants[(activity[1], day_of(activity[4]))] - {activity[2]}
    ]

    grouped: dict[tuple[date, str], list[Activity]] = {}
    for activity in anomalous:
        grouped.setdefault((day_of(activity[4]), activity[2]), []).append(activity)

    billable_by_day: dict[tuple[date, str], list[Activity]] = {}
    for activity in billable:
        billable_by_day.setdefault((day_of(activity[4]), activity[2]), []).append(
            activity
        )

    daily_review: list[dict[str, object]] = []
    for (activity_day, person), entries in sorted(
        billable_by_day.items(), key=lambda item: (item[0][0], names[item[0][1]])
    ):
        corroborated = [
            entry
            for entry in entries
            if participants[(entry[1], activity_day)] - {person}
        ]
        gmail_ids = sent_gmail.get((person, activity_day), [])
        slack_ts = sent_slack.get((person, activity_day), [])
        if gmail_ids or slack_ts:
            disposition = "cleared_by_communication"
        elif corroborated:
            disposition = "anomalous"
        else:
            disposition = "cleared_no_corroboration"
        daily_review.append(
            {
                "date": activity_day.isoformat(),
                "timekeeper": names[person],
                "billable_entry_ids": [entry[0] for entry in entries],
                "sent_gmail_ids": gmail_ids,
                "sent_slack_ts": slack_ts,
                "corroborated_entry_ids": [entry[0] for entry in corroborated],
                "corroborated_matter_numbers": list(
                    dict.fromkeys(matter_numbers[entry[1]] for entry in corroborated)
                ),
                "disposition": disposition,
            }
        )

    anomalous_days: list[dict[str, object]] = []
    for (activity_day, person), entries in sorted(grouped.items()):
        numbers = list(dict.fromkeys(matter_numbers[entry[1]] for entry in entries))
        anomalous_days.append(
            {
                "date": activity_day.isoformat(),
                "timekeeper": names[person],
                "entry_ids": [entry[0] for entry in entries],
                "matter_numbers": numbers,
                "minutes": sum(entry[3] for entry in entries) // 60,
                "billed_cents": sum(
                    billed_cents(entry[3], entry[5], entry[6]) for entry in entries
                ),
            }
        )

    phantom_notes = sorted(
        note_id
        for note_id, ticket_id, author, timestamp in notes
        if (author, day_of(timestamp)) not in sent
        and participants[(ticket_id, day_of(timestamp))] - {author}
    )

    if len(activities) != 4_306 or len(billable) != 4_233:
        raise RuntimeError(
            "expected 4,306 total and 4,233 billable activities, found "
            f"{len(activities):,} and {len(billable):,}"
        )
    if len({activity[2] for activity in billable}) != 8:
        raise RuntimeError("expected eight distinct billable timekeepers")
    dispositions = Counter(str(record["disposition"]) for record in daily_review)
    if len(daily_review) != 655 or dispositions != {
        "cleared_by_communication": 637,
        "cleared_no_corroboration": 15,
        "anomalous": 3,
    }:
        raise RuntimeError(
            "expected 655 person-days split 637 communication-cleared, "
            f"15 uncorroborated, and 3 anomalous; found {dispositions}"
        )
    if len(anomalous_days) != 3 or len(anomalous) != 18:
        raise RuntimeError(
            "expected 18 affected entries across three timekeeper-days, found "
            f"{len(anomalous)} across {len(anomalous_days)}"
        )
    if phantom_notes != [176]:
        raise RuntimeError(
            f"expected corroborated phantom note 176, found {phantom_notes}"
        )

    return {
        "entries_reviewed": len(billable),
        "timekeepers_reviewed": len({activity[2] for activity in billable}),
        "person_days_reviewed": len(daily_review),
        "cleared_by_communication": dispositions["cleared_by_communication"],
        "cleared_no_corroboration": dispositions["cleared_no_corroboration"],
        "anomalous_timekeeper_days": anomalous_days,
        "anomalous_timekeeper_day_count": dispositions["anomalous"],
        "anomalous_entry_count": len(anomalous),
        "anomalous_minutes_total": sum(entry[3] for entry in anomalous) // 60,
        "anomalous_billed_cents_total": sum(
            billed_cents(entry[3], entry[5], entry[6]) for entry in anomalous
        ),
        "phantom_note_ids": phantom_notes,
        "daily_review": daily_review,
    }


def main() -> int:
    state = Path(os.environ.get("WORKBENCH_STATE", "../state"))
    json.dump(build_hygiene(state), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
