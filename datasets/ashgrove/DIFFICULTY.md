# Difficulty, as measured on this world

Dataset-specific evidence. The rules these measurements produced are in
[`../../docs/METHOD.md`](../../docs/METHOD.md); this file is the numbers
behind them, kept so the rules can be checked against what actually
happened here.

**World:** `epoch-r12` — 11 workdays, 6,150 events, 27 people, 14
matters, 1,260 time entries, 1,585 messages (354 mail, 1,231 chat), 52
documents, 49 workspace files. Coherence clean at 0.1% mis-booked
against a 5% limit.

## The band, three models

Mean of gpt-5.6-sol, Opus 5 and glm-5.2, over gradeable trials only.

| task | gpt-5.6-sol | opus-5 | glm-5.2 | mean | |
|---|---|---|---|---|---|
| commitment-follow-through | 0.515 (4/9) | 1.000 | 0.213 (2/3) | **0.576** | in |
| opening-days-completion-claims | 0.687 (8/9) | 1.000 | 0.635 (3/3) | **0.774** | in |
| opening-week-follow-through | 0.686 (9/9) | 1.000 | 0.693 (8/9) | **0.793** | in |
| opening-days-commitment-register | 0.802 (8/9) | 1.000 | 0.628 (8/9) | 0.810 | out |
| work-product-review | 0.741 | 1.000 | 0.926 | 0.889 | out |
| tracker-reconciliation | 1.000 | 1.000 | 0.909 | 0.970 | out |
| open-items-triage · self-review-exposure · workpaper-open-items | 1.000 | 1.000 | 1.000 | 1.000 | out |

Every miss in the three in-band tasks is classified M, on the evidence
recorded in [`LEDGER.md`](LEDGER.md).

## Opus 5 scores 1.000 on every fair task here

Eight difficulty levers were built and measured against it here — width,
coverage, correlated error, lexical near-miss, semantic synonym, chained
derivation, office files, and constraint satisfaction — and all returned
ceiling. Two more, volume and depth, had already been measured on another
dataset a week earlier with the same result. The full table and the
reason they share a cause are in `METHOD.md` §2.

The consequence for this suite is arithmetic: with one tier pinned
at 1.000 the three-model mean has a floor of 0.333 and clears 0.8 only
when the other two average ≤ 0.7. Every in-band task here is bought by
how far the weakest tier falls, which is why two of the three sit within
0.03 of the upper edge and the one with real margin (0.576) is the one
where glm scores 0.213.

**A better-centred band needs a rule the frontier tier also misses, or a
fourth tier below glm-5.2.**

## What separates the tiers here

Measured on `completion-claims`: gpt-5.6-sol read **1,574 of 1,585
messages — 99.3% coverage** — and found 48 of 110 rows, catching 23 of
the 82 occurrences of a single common word. That is rule application,
not enumeration, and it is the only effect on this world that survives
bounding the corpus.

The three in-band tasks fail in three distinct ways, none of which is
coverage:

- **rule miss at a rate** — a two-word rule missed at ~70% by a model
  that had read the text
- **compositional miss** — one sentence carrying two forms that resolve
  to different dates; every trial found one, two of nine found both
- **date arithmetic and invention** — wrong due dates on real rows, plus
  rows asserted on messages carrying no time-shaped sentence at all

## Corpus sizes, for cutting bounded tasks

Both weaker tiers stop producing deliverables on the full 1,585-message
corpus — one times out, the other hands the work to sub-agents and ends
its turn. Bounded windows over the same corpus:

| window | messages | commitment rows | completion rows |
|---|---|---|---|
| 2 days | 213 | 71 | 25 |
| 3 days | 355 | 123 | 37 |
| full | 1,585 | 441 | 110 |

**355 is where abandonment begins** for gpt-5.6-sol on this world; 213
is reliably completed by both weak tiers. Task windows here are chosen
against that boundary, not against a row target.

## Grains available

| grain | rows |
|---|---|
| time entries | 1,260 |
| chat messages | 1,231 |
| person × engagement | 188 |
| mail messages | 354 |
| calendar invitations | 184 |
| documents / versions | 52 / 112 |
| workbook sheets carrying a status column | 96 (755 rows) |
| threads | 49 |
| engagements | 14 |

## Two structural limits of this world

**Density does not improve with length.** A world three times longer has
three times the documents and three times the attachments, so a boolean
true on 13% of rows stays true on 13%. Scale multiplies rows and leaves
proportions alone; the skew is a property of how a firm works — most
working papers are never sent, most recurring invitations are never
answered. Continuous and derived values (hours, dates, counts) grade well
here; sparse booleans do not.

**Constraint satisfaction is not buildable.** 17 of 27 staff have logged
time on nearly every engagement, so an independence-constrained reviewer
assignment has zero feasible solutions on 13 of 14 matters. Making it
feasible would mean inventing constraints the firm does not have.
