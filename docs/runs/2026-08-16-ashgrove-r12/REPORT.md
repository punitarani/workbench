# Ashgrove r12 — a world that validates, and one task that discriminates

**What this was for.** An RL environment whose Harbor tasks land 0.2–0.8 for
a frontier model, where every sub-1.0 criterion is a genuine *model* failure
and never an environment, data, tool, or task defect.

**What it produced.** A clean 11-workday world, nine tasks whose oracles each
survive an independent re-derivation, one task at **0.783 (k=3, 0.770–0.808)**
with all 42 misses verified as model failures — and a measured account of why
the other four sit at 1.000 that is more useful than the 0.783.

---

## The world

`epoch-r12`, recorded on upgraded tiers (fast `claude-haiku-4.5`, deep
`claude-sonnet-5`, both Bedrock-pinned).

```
11 workdays · 5,984 steps · 6,150 events · 2.3h wall
4,945 LM calls · 16.1M prompt / 1.4M completion tokens · 74 rejections
validates=True · 8/8 audit gates · 0 contradictions · 0 dangling refs
```

What the model upgrade bought, against the previous world:

| | before | after |
|---|---|---|
| time booked against a client its own note contradicts | 20.7% | **0.1%** |
| documents filed under raw internal ids (`tkt-000004/…`) | 67% | **0 / 52** |
| documents ever revised | 16/34 | 27/52 |
| revised by a second author | 0/16 | 15/27 |
| meeting transcripts | 1 | 36 |
| `reviewed` column | false in all 34 | 15 true / 37 false |

The first two are the ones that mattered. Mis-booked time made three
engagement-level tasks ungradeable — the honest answer and the graded answer
were different answers. The `tkt-` paths were the one metric no code fix
moved (68% → 67% across an engine rewrite), which is what identified it as a
model limitation rather than a bug, and it went to zero on the better model
plus an explicit prompt rule.

## The suite

Opus 5 through codex, on r12.

| task | rows | Opus 5 | glm-5.2 |
|---|---|---|---|
| **commitment-register** | 388 | **0.783** (k=3) | running |
| engagement-time-allocation | 188 | 1.000 | **0.540** |
| work-product-review | 52 | 1.000 | **0.778** |
| tracker-reconciliation | 139 + 10 | 1.000 | **0.832** |
| client-responsiveness-sla | 43 | 1.000 | 1.000 |
| wip / closeout / staffing | 10 | not re-run (thin) | — |
| open-items-triage | 4 | not re-run (thin) | — |

**Three of the four discriminate, and all three put the weaker model in
band.** Every miss on both models is classified in `LEDGER.md`; all are M.
The widest gap is one clean mistake — glm dropped `00013-Mendes` entire, an
engagement `list_matters` returns on the first call, and every firm total is
then wrong by exactly its 41 entries.

`engagement-status-integrity` was **retired**: its answer on r12 is empty —
nothing moved backwards anywhere — and a task with no rows grades nothing.

## Why one task moved and four did not

Three difficulty hypotheses were tested and two were refuted, both with
measurements rather than argument.

**Width does not work — for a frontier model.** `engagement-time-allocation`
costs 1,260 time entries across 27 pages and returns 188 rows. Opus 5 scores
1.000, and did so on the previous world too, at 197 rows over 1,304 entries.

It *does* separate tiers: glm-5.2 scores **0.540** on r12. But not through
volume — through one clean mistake, and the cross-tier section below has it.

**Coverage does not work.** Widening the commitment register from mail only
to mail plus chat took it from 189 rows over 328 messages to 507 over 1,547
— and the score went *up*, 0.901 → 0.908.

The reason is arithmetic and was visible all along: independent errors
average out. A model right 99.5% of the time per row is right 99.5% of the
time however many rows there are. And the reading is never brute-forced —
the agent paginates each surface once, writes the results to disk, and
queries its own index.

**Correlated error does not work either.** `tracker-reconciliation` was built
precisely for it: a week-one tracker in the shared drive, three bridging
decisions (`tkt-000004` against `00004-KestrelManufacturing`, "In progress"
against "In-progress", "as at" against "to date"), each moving all 139 rows
together. Opus 5 solved it perfectly in 26 shell commands.

**What does work: rule-literalism under semantic temptation.** The
commitment register's recall is *perfect* — all 388 rows found. It loses on
precision: 42 invented rows, 34 of which come from prose containing none of
the seven stated forms.

```
"Harbor Light and Ashfield wrap end of week"    EOW is not one of the seven
"Fairmount queues early next week"              not a listed form
"Wednesday 14:30 works for the GL sync"         a meeting, not "by Wednesday"
```

The instruction excludes these in as many words. The model overrode it
because it *knows* those are commitments — its competence at reading intent
is what hurt it.

The axis needs a rule **much narrower than the thing it names**. That is not
a general property of written rules, and the limit was measured:
`open-items-triage` has the same whitelist shape and cannot be made to work,
because 81 of 86 client messages ask for something and there is nothing to
be tempted by.

## The honest structural finding

A task is deterministically gradeable exactly when it is programmatically
solvable. The oracle *is* a program; its existence proves one suffices, and
the agent has a shell. The two constraints this project imposes — state
every rule, so a miss is not a task defect; serve every fact, so a miss is
not an environment defect — together guarantee the task is a program the
agent can write.

Rule-literalism is the exception that fits: the program is writable, but
writing the *right* one means resisting what the prose plainly means.

## What made the 0.783 trustworthy

Four gates, each of which caught something real before any rollout was spent:

- **Oracle independence** — every answer re-derived from the world log, no
  projection code shared. Caught a tie-break where the solver contradicted
  its own instruction, and would have caught the 817.27-vs-817.23 rounding
  defect and the duplicate-title ceiling.
- **Coherence scan** — reproduced exactly the four `stale_field_change`
  events that made a whole 15-day recording unusable, and separates
  contradictions (which block) from ambiguities (which are task material).
- **Reachability** — found to be reading one page of one surface, and
  *writing* 2,280 phantom access rows into the bundle it measures.
- **Degeneracy** — was skipping the emptiest answer of all; that is how the
  empty task was found.

And `test.sh` now preserves the agent's answer beside its score, because a
trial that keeps the number and throws away the answer makes "why did it
miss that row" a guess — which is the one thing that may not decide whether
a miss is a model failure.

## End-to-end, in one command

`pipeline.py` chains audit → build → verify, each stage able to refuse the
next, and it runs clean on r12 **without** `--refresh-truth` — so every
solver reproduced its committed oracle byte for byte from a fresh
materialization rather than rewriting it:

```
1. audit    validates=True, 8/8 realism gates
2. build    coherence clean, 9 oracles verified, all reachable through the tools
3. verify   9 of 9 re-derived from the world log, all agree
```

The only output is the degeneracy report on the four thin tasks, which is
the check doing its job rather than a failure.

## Known gaps

- Four tasks at ceiling. The options are in `DIFFICULTY.md`; the one that
  works is applying the literalism axis where the ratio supports it.
- Four thin tasks (4–10 rows) are structurally near-binary — the firm has
  14 engagements and that caps any per-engagement grain.
- Only `commitment-register` has k=3. The rest are single trials.
- The Calder acceptance cassette has been missing since the persona prompts
  changed and still needs re-recording; verified pre-existing by stashing.
- `commitment-register` under glm-5.2 is the last cross-tier cell; it timed
  out at 50 minutes on the wider previous world and is running on r12.
