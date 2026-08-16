# Engagements that went backwards

You are the practice manager at **Ashgrove Reid LLP**, an audit and
assurance practice. Engagements are supposed to move forward: opened,
worked, reviewed, closed. Work that goes back a stage — or comes back
after it was closed — is where budgets are lost, and the partners want it
named before the monthly review.

The firm's systems are available through tools: **clio** (engagements,
their status history, and time activities), **gmail**, **imanage**,
**slack**, and **calendar**.

## What to produce

One file in your workspace: **`status_integrity.json`**, with exactly
these fields:

- `engagements_reviewed` — how many engagements exist.
- `reopened_count` — how many were reopened, by the rule below.
- `backward_move_count` — how many backward moves happened across the
  whole firm, counting every one, not one per engagement.
- `never_moved_count` — how many engagements have never had a status
  change at all.
- `flagged` — one entry per engagement that moved backwards at least
  once, sorted by `engagement`, each with:
  - `engagement` — the engagement's display number, as clio shows it
  - `status` — its status now
  - `status_changes` — how many status changes it has had in total
  - `backward_moves` — how many of those went backwards
  - `reopened` — `true` if any change took it out of `closed`
  - `hours_from_backward_day` — hours logged to it on or after the **date**
    of its first backward move, 2 decimals. Clio dates changes and time
    entries and stamps no hour on either, so count whole days: an entry
    dated the same day as the backward move counts.

## The stages

An engagement's status is one of these, and they run in this order:

1. `open`
2. `in-progress`
3. `review`
4. `closed`

A **backward move** is a status change whose new stage is earlier in that
list than the old one. `review` back to `in-progress` is backward;
`in-progress` on to `review` is not.

`waiting-client` is a hold rather than a stage: it has no position in the
order. A change into or out of `waiting-client` is never a backward move,
and never counts in `backward_moves`, though it does count in
`status_changes`.

**Reopened** means any change whose old status was `closed`, whatever it
became. An engagement can be reopened more than once and still counts
once in `reopened_count`.

Compare statuses without regard to capitalisation: the record does not
spell them consistently, and that is not the thing being tested.
