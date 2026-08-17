# The tracker is out of date. Say exactly where.

You are the practice administrator at **Ashgrove Reid LLP**, an audit and
assurance practice. In week one somebody typed up an engagement tracker and
circulated it. It is still in the shared drive, still being read in
meetings, and the practice systems have kept moving since it was written.

Before the partners rely on it again, they want it checked against the
system of record, line by line.

The tracker is a file in your workspace: **`engagement-tracker-week1.md`**.
The systems are available through tools: **clio** (engagements, users, time
activities), plus **gmail**, **slack**, **imanage**, and **calendar**.

## Three things about the tracker

**It names engagements the way staff do, not the way clio does.** The sheet
says `tkt-000004`. Clio identifies the same engagement as
`00004-KestrelManufacturing` and never uses the other form. They share
their number, and that is the join.

**It words statuses the way people speak, not the way clio stores them.**
Translate before comparing, using exactly this table:

| the tracker says | clio's state(s) |
|---|---|
| `Not started` | `Open` |
| `In progress` | `In-progress` **or** `Waiting-client` |
| `In review` | `Review` |
| `Complete` | `Closed` |

An engagement has **moved** only when clio's current state is *not* one the
tracker's word covers. `In progress` against `Waiting-client` has not
moved — the sheet is not wrong, it is simply not that specific.

**Its hours are "as at", not "now".** Every figure was the total booked up
to the tracker's own date. The comparison that matters is against the total
booked *to date*, which is what clio holds now.

## What to produce

One file in your workspace: **`tracker_reconciliation.json`**, with exactly
these fields:

- `as_of` — the date the tracker states for itself, `YYYY-MM-DD`.
- `engagements_on_tracker` — how many engagements it lists.
- `engagements_moved` — how many have moved, by the rule above.
- `effort_lines` — how many rows are in `effort`.
- `verdict_counts` — an object counting each `verdict` value.
- `hours_understated_total` — the sum over `effort` of
  `actual_hours - tracker_hours`, 2 dp.
- `engagements` — one entry per engagement on the tracker, sorted by
  `engagement`:
  - `engagement` — clio's display number
  - `tracker_status` — what the sheet says, unchanged
  - `current_status` — what clio says now, unchanged
  - `moved` — true or false
- `effort` — one entry per person-and-engagement, sorted by `engagement`
  then `person`:
  - `engagement` — clio's display number
  - `person` — the person's full name
  - `tracker_hours` — what the sheet credits them, 2 dp, or `0.0` if the
    sheet does not list them
  - `actual_hours` — what clio holds now, 2 dp
  - `verdict` — one of:
    - `unchanged` — the two agree
    - `understated` — the sheet lists them and clio now holds more
    - `absent_from_tracker` — clio has time the sheet never listed

## Scope

The tracker covers the **client book**. The firm's own internal projects
were never on it, so time booked to them is not something the sheet is
missing and does not belong in this report. Clio marks the difference: a
client engagement has a client, an internal one does not.

Every person-and-engagement pair with time on a client engagement belongs
in `effort` — the ones the sheet lists, and the ones that started work only
after it was written and appear nowhere on it. Finding that second group
means working from clio's side rather than the sheet's; there is no line to
read for a row that was never typed.

## How to round

**Every figure in hours or dollars is rounded once, at the end.** Add the
entries' own durations — the raw seconds clio holds — and round the total
only as you write it. Never add up figures that have already been cut to
two decimals.

The two orders do not agree here, and not rarely: on this record they give
different answers for **34% of person-and-engagement pairs, 79% of
engagements, 88% of people, and every firm-wide total**. `10.78` and
`10.79` are the same work counted two ways, and only the first is the
answer.
