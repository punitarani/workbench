# The task pack

Agentic tasks over recorded fictional workplaces, graded programmatically
against an answer key that a second, independently written derivation
reproduces.

Everything here is measured. Where a number appears, a command beside it
reproduces it; where a task was retired, the manifest carries the
measurement that retired it.

---

## What is in it

Two recorded worlds and the tasks cut from them.

`days` is the span from the first recorded meeting to the last, inclusive.
It is not the configured window: merrick's window runs to day 182 and its
last meeting is on day 179, which is where the 182 this table used to
carry came from.

| world | days | meetings | turns | words | people |
|---|---|---|---|---|---|
| `merrick` | 180 | 567 | 2,872 | 216,500 | 31 |
| `delegation` | 135 | 411 | 2,126 | 166,888 | 31 |

Both are the same fictional law firm. `delegation` was recorded a second
time with one change to the workplace spec — partners hand work to named
colleagues out loud instead of taking it on themselves — because the
assignment family needed a world with enough assignments in it: **105
turns against merrick's 13**, re-measured 2026-08-29. It is the only world
here commissioned *for* a family rather than a family found in a world.

That pair used to read 122 against 16, and the drop is the rule being
tightened rather than the worlds changing: every guard added to it removes
matches, and the figure had been written down before the guards were. The
ratio — eight to one — is what the re-recording was for, and it held.

They share all 31 people, every meeting title and both rule modules, so a
family that works on one is a task on the other for the cost of
recomputing the four dates its brief states. **Twelve live tasks**, five
on `merrick` and seven on `delegation`; nine more were retired on
measurement and each manifest carries the number that retired it.

`docs/TASKS.md` lists every one, generated from the tasks themselves. It
also lists **27 legacy tasks on three earlier worlds** that are NOT part of
this pack and are not counted anywhere in it. They predate the current
grading architecture — their criteria name no deliverable, so the scorer
refuses them, because without one a trial that wrote nothing is
indistinguishable from one that answered badly. `ashgrove` is among them,
and it is the world whose tasks measured at **~1.000 for a frontier model**
however the difficulty was turned up. That measurement is why `merrick` was
recorded.

Six tool surfaces are served over MCP: `clio` (matters, people, time),
`gmail`, `slack`, `imanage`, `calendar`, and `meetings` (transcripts).

## What the tasks ask

Every live task is a **register**: read a window of standing-meeting
transcripts and report one row per person per meeting series, with facts
that only exist once the whole series has been read in order.

Three rules generate them:

- **the promise rule** — `I'll have it by Thursday`, first person
- **the assignment rule** — `Mira owes me the schedule by Friday`, third
  person, where **the owner of a row is never the speaker**
- **the blocker rule** — `I'm still waiting on Ulrich`, which carries **no
  date at all**, so every graded fact comes from the meetings

Each rule has two independent derivations that must agree before an oracle
ships: one over character spans and regex, one over word tokens. They
currently agree on **4,998 turns across both worlds, 0 disagreements**.

That check has a blind spot worth stating, because it was found the hard
way: it cannot see both derivations being stale in the same direction. One
task vendored its own copies of the rule and the checker rather than
importing the world's, both forks drifted, and the gate compared one stale
module against another and reported agreement. On that task's 1,399 mail
messages the fork admitted 61 where the world's rule admits 57. Nothing
vendors now.

## Why they are hard

A deadline said out loud is relative. `EOD` said in January and `EOD` said
in June are five months apart, so the register grades the **resolved date**,
not the word — which means a reader who never opens a transcript scores
nothing, and a reader who takes each person's first statement scores
almost nothing.

Measured, on one task keyed two ways:

    keyed (owner, meeting), date a field    row_f1 1.000
    keyed (owner, meeting, due)             row_f1 0.179

Difficulty comes from **joint dependency**: a row needing `k` facts that
fail independently is right with probability `a**k`. Both ends of a chain
and its length are three different reads of the same chain, and none is
derivable from the others.

## How much of the stated rule the corpus actually tests

A brief that names a form the corpus never contains is grading a promise it
cannot keep, and nothing errors when it happens. Measured with
`scripts/dead_conditions.py`, which deletes one alternative from a pattern,
re-runs the rule over every turn and every message, and asks whether the
verdict moved:

| rule | what the brief enumerates | exercised |
|---|---|---|
| the promise rule | 8 deadline forms | **8 of 8**, on both worlds |
| the blocker rule | 5 stuck phrases + 5 `can't` verbs | 8 of 10 — no turn says `can't proceed` or `can't finish` |

Beyond what the briefs enumerate, the rules carry breadth the corpora do
not reach: 65 of the blocker rule's pattern alternatives change no verdict
on either world, and more of the older two. That is mostly grammatical
completion the brief never promised — `stays` and `remains` beside `is` —
and it is the safe direction for a rule to be wrong in.

**The check must run against both worlds.** Every guard added to the
blocker rule on 2026-08-29 is alive on exactly one of them, and against a
single corpus each reports dead — a condition deciding nothing, ready to be
deleted as decoration. Each has one caller, and each caller is a sentence
that was putting a row in the key wrongly that morning.

## What it does not measure

Stated plainly because a benchmark that oversells itself is worse than a
small one.

- **Not legal judgement.** Every rule is a stated phrase list plus clause
  tests, written into the brief. This measures exhaustive application of a
  specification across a corpus no script can flatten.
- **Not a realistic workload.** A practitioner would prepare a partner
  meeting from last week's notes, not six months of transcripts. The wide
  window is arithmetic: blockers occur in 75 turns of 2,872, and at the
  last eight occurrences of each series the register has **two rows**.
- **Not a coherent firm across every surface.** Billing has a Gini of
  0.059 — every person logs 573 to 933 hours — and mail is inverted against
  the surfaces that agree with each other. The live tasks all read
  transcripts, which is the coherent surface. Anything spanning billing or
  mail would measure the generator.

`docs/REALISM-REVIEW.md` answers a practitioner's critique point by point,
including the three criticisms that are correct and ungradeable.

## Grading

Each task ships an `instruction.md`, an `environment/`, a reference
`solution/`, an independent `checks/verify.py`, and `tests/` carrying the
oracle and the criteria.

The reward is row F1 against the truth set plus per-row fields. Floors are
measured on every build: what an empty answer scores, what dumping every
candidate scores, what doing nothing scores.

Grading is split in two: a **reward** dimension that is the score, and a
**diagnostic** dimension that informs and never moves it. That separation
is checked rather than assumed — across 198 saved trials the recorded
reward equals the answer dimension's score exactly, 0 exceptions, so no
presentation or process check has ever moved a number in this pack.

Coverage counts are reported, not scored, and the line between the two is
drawn by measurement rather than by taste. A criterion at ceiling for every
tier is not measuring any of them, so `meetings_read` — 1.00 across all
three tiers, and a date-filtered query away — pays nothing. `turns_read`
reads 1.00, 0.33, 0.67 and still pays: counting turns means having opened
the transcripts. `superseded_count` reads 0.00 for nearly every tier and
pays anyway, because the oracle holds 128, the trials report 121 to 129,
and three of them reported exactly 128 — hard is not the same as
unmeasurable, and the test is whether anyone has ever scored it.

A task is **certified** only when three model tiers each score inside
0.2–0.8 on at least three trials that produced an answer, against one
version of the task, with no single criterion at ceiling *or* untouched for
any tier, and no row that every trial declined unless a reader has
adjudicated it in `docs/adjudications/`.

    uv run python scripts/certify.py --dataset <world> --task <task> \
        --tag <opus-tag> --tag <glm-tag> --tag <kimi-tag>

## Reproducing

    uv run python datasets/<world>/build_tasks.py --task <task>
    uv run python scripts/band.py --dataset <world> --any-tag
    uv run python scripts/coherence.py --state out/<world>/bundle/state

Scores live in `jobs/`, which is not distributed: it holds provider keys in
logs. A clone reproduces the tasks and the oracles, not the measurements.

`jobs/`, `out/` and `.env` are gitignored and none of them has a tracked
file. Verified 2026-08-29 across all 872 commits: **no commit in this
repository's history has ever added an `sk-or-v1-` or `sk-ant-` literal,
or a private key block.** The only matches for a credential pattern
anywhere in the tree are the variable NAME in usage examples --
`OPENROUTER_API_KEY=... uv run ...` -- in six files.

## Reading order

- `docs/TASKS.md` — every task, generated, with the legacy worlds separated
- `docs/CERTIFIED.md` — what is certified, with every trial score
- `docs/LAWS.md` — 50 measured laws, each with its number and its cost
- `docs/REALISM-REVIEW.md` — a practitioner's critique, answered with data
- `docs/adjudications/` — every disputed row, with the passage behind it
- `docs/RUNNING-SWEEPS.md` — the concurrency limit and how it lies to you
