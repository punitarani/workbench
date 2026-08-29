# Samir Bhatt | Corporate deal status | 2026-05-13 | 2026-01-08 | 2

`certify.py` refused `live-commitment-register` on this row: every trial
declined it, and two answered `3` where the key says `2`. Unanimous
disagreement in one direction has been an oracle defect four times out of
five on this tree, so it was adjudicated rather than waived on sight.

## What the key holds

Three qualifying turns in three meetings of the series, so two earlier
commitments were replaced:

| meeting | date | token |
|---|---|---|
| mtg-000134 | 2026-01-08 | `eod` |
| mtg-000136 | 2026-01-12 | `thursday` |
| mtg-000220 | 2026-05-08 | `wednesday` |

## What the models saw

A fourth meeting. Fifteen further turns by this speaker in this series
carry both a promise form and a day, and the rule refuses all of them.
Reading them, all but one are refused for reasons the brief states
outright:

- *"I'll defer the EOD escalation ownership to you"* — the brief's own
  example of a hand-off naming a task, not a deadline.
- *"I'll hold the closing binder as-is until Ingrid's written confirmation
  comes in"* — `until` ends a wait; it does not date a delivery.
- *"I'll update the tracker ... once Quentin and Mira have"* — a condition.
- *"I'll have the Officer's Certificate ready to circulate the moment those
  land"* — timing depends on an external event, so it names no day.

The remaining one is mtg-000132, 2026-01-06: *"I'll get on the phone with
lender's counsel **today** and report back before we're anywhere near
signature."*

## Verdict: the key is right

The brief settles this in as many words:

> **A day named only to rule it out is not a deadline.** *"I'll get an
> answer today, not tomorrow"* commits to today, and `today` is not one of
> the days this register admits — so it makes **no row**.

`today` is absent from the deadline table on purpose. The turn is a real
commitment that this register does not admit, which the brief says out
loud, and admitting it would also require deciding what "report back before
we're anywhere near signature" resolves to — which is nothing.

So the models over-admitted a day the brief excludes. **A genuine model
failure, waived.**

Reproduce:

    uv run python scripts/certify.py --dataset merrick \
        --task live-commitment-register --tag opus-w147-k3 \
        --tag glm-w147-k3 --tag kimi-w147-k3 \
        --waive "Samir Bhatt | Corporate deal status | 2026-05-13 | 2026-01-08 | 2"
