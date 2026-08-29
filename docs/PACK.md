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

| world | days | meetings | turns | words | people |
|---|---|---|---|---|---|
| `merrick` | 182 | 567 | 2,872 | 216,500 | 31 |
| `delegation` | 135 | 411 | 2,126 | 166,888 | 31 |

Both are the same fictional law firm. `delegation` was recorded a second
time with one change to the workplace spec — partners hand work to named
colleagues out loud instead of taking it on themselves — because the
assignment family needed a world with enough assignments in it: **122
against merrick's 16**. It is the only world here commissioned *for* a
family rather than a family found in a world.

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

## What it does not measure

Stated plainly because a benchmark that oversells itself is worse than a
small one.

- **Not legal judgement.** Every rule is a stated phrase list plus clause
  tests, written into the brief. This measures exhaustive application of a
  specification across a corpus no script can flatten.
- **Not a realistic workload.** A practitioner would prepare a partner
  meeting from last week's notes, not six months of transcripts. The wide
  window is arithmetic: blockers occur in 58 turns of 2,872, and at the
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

The reward is row F1 against the truth set plus per-row fields. Coverage
counts are reported, never scored. Floors are measured on every build: what
an empty answer scores, what dumping every candidate scores, what doing
nothing scores.

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

## Reading order

- `docs/CERTIFIED.md` — what is certified, with every trial score
- `docs/LAWS.md` — 42 measured laws, each with its number and its cost
- `docs/REALISM-REVIEW.md` — a practitioner's critique, answered with data
- `docs/adjudications/` — every disputed row, with the passage behind it
- `docs/RUNNING-SWEEPS.md` — the concurrency limit and how it lies to you
