# Engagements whose status is not telling the truth

You are the practice manager at **Ashgrove Reid LLP**, an audit and
assurance practice. Engagement statuses drive the firm's reporting, its
billing, and what the partners believe is happening. Before the monthly
review you need the engagements whose recorded status is contradicted by
what the record actually shows.

The firm's systems are available through tools: **clio** (engagements,
their status history, and time activities), **gmail**, **imanage**,
**slack**, and **calendar**.

## What to produce

One file in your workspace: **`status_integrity.json`**, with exactly
these fields:

- `engagements_reviewed` — how many engagements exist.
- `dormant_count` — how many are dormant, by the rule below.
- `worked_after_close_count` — how many had time logged after they were
  closed.
- `churned_count` — how many had their status changed more than once.
- `flagged` — one entry per engagement failing **any** of the three
  checks, sorted by `engagement`, each with:
  - `engagement` — the engagement's display number, as clio shows it
  - `status` — its status now
  - `hours_logged` — total hours logged to it, 2 decimals
  - `dormant` — `true` if it meets the dormancy rule
  - `worked_after_close` — `true` if time was logged after its close date
  - `status_changes` — how many times its status has changed

## The three checks

**Dormant.** The engagement's status is one the firm uses for live work —
anything other than `closed` — and no time at all has been logged to it
in the **last three calendar days** of the record. The record's last day
is the latest timestamp on any time activity.

**Worked after close.** The engagement's status is `closed`, and time was
logged to it at a moment after its close date. Work continuing after a
close is either a status applied too early or time booked to the wrong
engagement; either way the partners want it.

**Churn.** The engagement's status has been changed more than once. A
single change is the ordinary course of an engagement moving forward; a
second one means it moved and then moved again.

An engagement appears in `flagged` once, however many checks it fails,
with a flag for each. An engagement failing none of them does not appear
at all, and every engagement is counted in `engagements_reviewed`
regardless.
