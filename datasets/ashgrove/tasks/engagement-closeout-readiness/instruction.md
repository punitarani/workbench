# Engagement status review

You are the engagement-support lead at **Ashgrove Reid LLP**. The
partners meet tomorrow and want one page: for every client engagement,
who owns it, how much work has gone in, and whether the client is
sitting waiting on us.

Systems available through tools: **clio** (engagements, time, people),
**gmail** (firm-wide mail), **slack**, **calendar**, **imanage**.

## What to produce

One file: **`closeout.json`**, with exactly these fields:

- `client_engagements` — client engagements reviewed.
- `status_counts` — a map of status → count.
- `awaiting_firm_reply` — sorted engagements in that status.
- `longest_waiting_engagement` — the engagement whose client has been
  waiting longest (`null` if none).
- `wip_at_risk_dollars` — unbilled work-in-progress sitting behind the
  firm's own silence: the WIP of every `awaiting_firm_reply` engagement,
  2 dp.
- `at_risk_over_10k` — sorted engagements whose status is
  `awaiting_firm_reply` and whose WIP exceeds $10,000.
- `engagements` — one entry per client engagement, sorted by
  `engagement`: `engagement` (the engagement's display number, as clio
  shows it — for example `00005-CardinalRidgeBuilders`), `client_contact` (full name),
  `responsible` (full name), `total_hours` (2 dp), `staff_count`
  (distinct people who logged any time), `status`,
  `client_waiting_hours` (1 dp; `0.0` when not waiting),
  `wip_dollars` (2 dp).

## Naming an engagement

Wherever this report names an engagement — in any field — use the
engagement's **display number**, exactly as clio shows it (for example
`00005-CardinalRidgeBuilders`). Identifiers in any other form that appear
elsewhere in the firm's systems are internal and are not what this report
asks for.

## How the firm values work in progress

WIP is **billable** time valued at the rate recorded on the entry.
Non-billable time is real work and belongs in `total_hours`, but carries
no value. Some people carry no rate at all: their time is hours without
dollars.

## How the firm decides status

An engagement is **client work** when it has a client. The firm's own
engagements — peer review, methodology, internal administration — carry
no client and are excluded, however they are titled and whoever opened
them. The engagement's client contact is the person who opened it.

A client engagement is:

- **`awaiting_firm_reply`** when that client's last message in *any*
  mail thread has no firm message after it; or
- **`clear`** otherwise.

`client_waiting_hours` is measured from that client's **oldest**
still-unanswered last message to the latest message anywhere in the
record. A client waiting on one thread makes **every** engagement they
opened `awaiting_firm_reply`, however much work it has had.

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
