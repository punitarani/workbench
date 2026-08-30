# Samir Bhatt | Corporate deal status | 2026-05-14 | 13

`certify.py` refused `delegation/standing-commitment-register` on this row:
every trial declined it, and three of eight answered `14` where the key
says `13`.

Unanimous disagreement in one direction has been the answer key five times
out of six on this tree, so it was adjudicated rather than waived on sight.

## The chain

Samir Bhatt commits in **16 meetings** of this series. Resolving each
statement against the meeting it was said in and stepping through
consecutive dates:

| | |
|---|---|
| steps where the date moved **later** | **13** |
| steps where it moved **earlier** | 1 — 2026-04-23 → 2026-04-22 |
| steps where it was restated unchanged | 1 |
| total transitions | 15 |

## Verdict: the key is right

The brief defines the field in as many words:

> `slips` — how many times this person moved this commitment **later**. …
> A date pulled **earlier** is not a slip and is not counted. A date
> restated unchanged is not a slip.

The `14` answers count the 2026-04-23 → 2026-04-22 step, which is a date
pulled earlier — the opposite of a slip, and excluded by the sentence
above. A judge panel shown the brief and the raw chain, and never the code,
returned **admit** and quoted that sentence back.

**A genuine model failure, waived.**

Reproduce:

    uv run python scripts/certify.py --dataset delegation \
        --task standing-commitment-register \
        --tag opus-sc1-k3 --tag glm-sc1-k3 --tag kimi-sc2-k3 \
        --waive 'Samir Bhatt | Corporate deal status | 2026-05-14 | 13'

## A note on how nearly this went the other way

The first recount here gave **14**, matching the models, and read as the
key being wrong. It counted *any* change across *every admitted turn*.
The rule counts *later* moves across *one commitment per meeting* — two
differences, each stated in the brief, and either alone flips the answer.

Re-deriving a disputed value is only evidence if the derivation is the
one the task states. Mine was not, and it agreed with the models, which
would have made it feel like confirmation.
