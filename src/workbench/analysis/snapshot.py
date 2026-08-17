"""A tracker somebody typed up on day five, in a world that ran to day fifteen.

Every attempt to make these tasks hard by giving the agent *more* has
failed, and the measurements are not close: 197 rows over 27 pages came
back at the ceiling, and widening a prose task from 189 rows to 507 —
from 328 messages to 1,547 — moved a frontier model from 0.901 to 0.908,
which is to say it got slightly better. Independent errors average out. A
model right 99.5% of the time per row is right 99.5% of the time however
many rows there are.

What does not average out is a decision that carries every row with it.
So: a spreadsheet, generated from the world as it stood partway through,
sitting in the workspace exactly as a real one would — the status
somebody wrote down before the systems moved on.

It contradicts the record on purpose, and three separate ways at once:

* **stale** — statuses frozen at the snapshot day, which the record has
  since moved past;
* **another vocabulary** — `In progress` for clio's `In-progress`,
  `Complete` for its `Closed`, because people type what they say;
* **another set of names** — engagements as ``tkt-000004``, the id staff
  see, where clio serves ``00004-KestrelManufacturing``.

An agent that treats all three as divergences reports every row and is
wrong. One that maps too freely reports none and is equally wrong. That is
one judgement moving forty rows together, which is the only shape that has
ever moved one of these scores.

Generated rather than hand-written so it cannot drift from the world it
describes: the same seed produces the same sheet, and the sheet is always
a true statement about the day it claims.

Lives in ``analysis`` rather than ``environment`` because it reads a
finished world and computes over it, which is what this package is for.
It was written into ``environment`` first, next to the materializer that
places its output, and the layering test caught that immediately: nothing
may depend on ``analysis``, and an environment module importing it is a
dependency in the wrong direction.
"""

from __future__ import annotations

from dataclasses import dataclass

from workbench.analysis.world_facts import WorldFacts

# What the tracker calls each state clio serves. Deliberately not a
# bijection: two clio states collapse to "In progress" here, which is how
# an ordinary spreadsheet gets written and which the reconciliation has to
# survive.
SPOKEN = {
    "open": "Not started",
    "in-progress": "In progress",
    "waiting-client": "In progress",
    "review": "In review",
    "closed": "Complete",
}


@dataclass(frozen=True)
class TrackerRow:
    engagement_id: str
    client: str
    status: str
    owner: str
    hours_to_date: float


def status_on(facts: WorldFacts, ticket_id: str, cutoff: int) -> str:
    """The status the record held at ``cutoff``, ignoring everything later.

    The point of the whole exercise: this is a true statement about that
    moment, and a false one about now.
    """

    ticket = facts.tickets[ticket_id]
    status = ticket.status
    for when, _actor, field, _old, new in sorted(ticket.changes):
        if field == "status" and when <= cutoff:
            status = new
    return status


def tracker_rows(facts: WorldFacts, cutoff: int) -> list[TrackerRow]:
    """Every client engagement, as it stood on the snapshot day."""

    hours: dict[str, int] = {}
    for activity in facts.activities:
        if activity.at <= cutoff:
            hours[activity.ticket_id] = (
                hours.get(activity.ticket_id, 0) + activity.minutes
            )

    rows = []
    for ticket_id in sorted(facts.tickets):
        ticket = facts.tickets[ticket_id]
        if ticket.client_ref is None:
            continue
        held = status_on(facts, ticket_id, cutoff)
        rows.append(
            TrackerRow(
                # The id staff actually see, which clio never serves.
                engagement_id=ticket_id,
                client=facts.orgs.get(ticket.client_ref, ticket.client_ref),
                status=SPOKEN.get(held.strip().casefold(), held),
                owner=facts.name(ticket.assignee) if ticket.assignee else "",
                hours_to_date=round(hours.get(ticket_id, 0) / 60, 2),
            )
        )
    return rows


@dataclass(frozen=True)
class EffortRow:
    engagement_id: str
    person: str
    hours_to_date: float


def effort_rows(facts: WorldFacts, cutoff: int) -> list[EffortRow]:
    """Hours per person per engagement, as at the snapshot.

    The wide half of the tracker. On a fifteen-day world a day-four cutoff
    yields about a hundred and thirty lines, of which nearly all have moved
    since and a dozen more pairs have appeared that the sheet never knew
    about — so the reconciliation has both a drift finding and an absence
    finding in it, on the same page.
    """

    minutes: dict[tuple[str, str], int] = {}
    for activity in facts.activities:
        ticket = facts.tickets.get(activity.ticket_id)
        if ticket is None or ticket.client_ref is None or activity.at > cutoff:
            continue
        key = (activity.ticket_id, activity.person_id)
        minutes[key] = minutes.get(key, 0) + activity.minutes
    return [
        EffortRow(
            engagement_id=ticket_id,
            person=facts.name(person),
            hours_to_date=round(total / 60, 2),
        )
        for (ticket_id, person), total in sorted(
            minutes.items(), key=lambda kv: (kv[0][0], facts.name(kv[0][1]))
        )
    ]


def render_markdown(rows: list[TrackerRow], as_of: str) -> str:
    """The tracker as a document, the way one is actually circulated."""

    lines = [
        f"# Engagement tracker — as of {as_of}",
        "",
        "Prepared for the weekly partner review. Status is what the "
        "engagement team reported at the time of writing; the practice "
        "systems are the record of account.",
        "",
        "| Engagement | Client | Status | Owner | Hours to date |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r.engagement_id} | {r.client} | {r.status} | {r.owner} | "
        f"{r.hours_to_date:.2f} |"
        for r in rows
    ]
    lines.append("")
    return "\n".join(lines)


def render_effort_markdown(rows: list[EffortRow], as_of: str) -> str:
    lines = [
        f"# Time on engagements — as at {as_of}",
        "",
        "Hours each person had booked to each engagement when this was "
        "taken. Figures are from the practice system at the time and are "
        "not updated after circulation.",
        "",
        "| Engagement | Person | Hours to date |",
        "|---|---|---|",
    ]
    lines += [
        f"| {r.engagement_id} | {r.person} | {r.hours_to_date:.2f} |" for r in rows
    ]
    lines.append("")
    return "\n".join(lines)


def write_tracker(facts: WorldFacts, cutoff: int, as_of: str) -> str:
    """One document, both halves, as it would actually be circulated."""

    return (
        render_markdown(tracker_rows(facts, cutoff), as_of)
        + "\n"
        + render_effort_markdown(effort_rows(facts, cutoff), as_of)
    )
