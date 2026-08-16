# Where the firm's time went

You are the practice administrator at **Ashgrove Reid LLP**, an audit and
assurance practice. Before the partners set next quarter's staffing they
want the period's time laid out properly: every person, every engagement
they touched, the hours, and what those hours are worth.

The firm's systems are available through tools: **clio** (engagements,
users, and time activities), **gmail**, **imanage**, **slack**, and
**calendar**.

## What to produce

One file in your workspace: **`time_allocation.json`**, with exactly
these fields:

- `entries_total` — how many time entries you accounted for.
- `pairs` — how many person-and-engagement combinations logged any time.
- `total_hours` — every logged hour, 2 dp.
- `total_billable_hours` — the billable ones, 2 dp.
- `total_fees_dollars` — the fees those billable hours carry, 2 dp.
- `busiest_person` / `busiest_engagement` — the person and the engagement
  of the single row with the most `hours`. Break a tie by taking the
  earlier `person`, then the earlier `engagement`, alphabetically.
- `allocations` — **one entry per person-and-engagement combination that
  has any logged time**, sorted by `person` then `engagement`, each with:
  - `person` — the person's full name
  - `engagement` — the engagement's display number, as clio shows it
  - `entries` — how many time entries they logged to it
  - `hours` — their total logged hours on it, 2 dp
  - `billable_hours` — how many of those were billable, 2 dp
  - `fees_dollars` — what the billable hours come to, 2 dp

## How the arithmetic works

**Fees are per entry, not per person.** Each time entry carries its own
rate. Charge every billable entry at the rate on that entry and add the
results; do not total somebody's hours and multiply once by a rate you
found elsewhere. People work at different rates on different engagements,
and the two methods give different answers.

**Not every entry has a rate.** Some carry none at all. An entry without
a rate contributes its hours — and, if it is billable, its billable hours
— but contributes no fees, because there is no rate to charge it at.
This is true even for the occasional billable entry with no rate on it.

**Non-billable time still counts as time.** It belongs in `hours` and in
`entries`, and stays out of `billable_hours` and `fees_dollars`.

**Round once, at the end.** The four firm totals — `total_hours`,
`total_billable_hours`, `total_fees_dollars` — are computed from the time
entries themselves and rounded when they are written, **not** by adding up
the rounded figures in `allocations`. Adding two hundred numbers that have
each been cut to two decimals drifts away from the real total: the firm's
hours come to `817.23` from the entries and `817.27` from the rounded
rows, and only the first is the answer.

## A warning about completeness

The firm's time runs to well over a thousand entries and the tools hand
them back a page at a time. Every figure in this report depends on having
read all of them; a page left unread is not a small error, it is a wrong
row and possibly a missing one.
