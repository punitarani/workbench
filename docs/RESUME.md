# Resume point — 2026-08-27

Nothing is running. `main` is green and pushed at `d822eef`. In-progress
work is parked on `wip/band-superseded-key`, which is pushed and has one
known-failing test with its fix written out in the commit message.

## Where the work stands

Two tasks are certified — three tiers each inside 0.2–0.8, on one version
of the task, with the heaviest criterion off ceiling for every tier.

| task | opus-5 | glm-5.2 | kimi-k3 | state |
|---|---|---|---|---|
| `commitment-revision-register` | 0.706 | 0.495 | 0.492 | **CERTIFIED** |
| `standing-commitment-register` | 0.755 | 0.376 | 0.470 | **CERTIFIED** |
| `live-commitment-register` | 0.795 | 0.545 | 0.463 | in band, not certified |

Reproduce any row:

    uv run python scripts/certify.py --dataset merrick --task <task> \
        --tag <opus-tag> --tag <glm-tag> --tag <kimi-tag>

See the whole set at once (needs the branch below for the third row):

    uv run python scripts/band.py --dataset merrick --any-tag

## Pick up here

**1. Land the branch.** `wip/band-superseded-key` fixes a real defect:
without it, `band.py` prefers a stale sweep over the current one whenever
the harness did not record the brief in its trajectory, which is every glm
trial in this tree. It is what moves `live-commitment-register` from
hidden to visible. One test in it fails on its own fixture ordering; the
two-line fix is in the commit message.

**2. Certify `live-commitment-register`.** It needs, exactly:

    uv run python scripts/rollout.py --dataset merrick \
        --task live-commitment-register --model glm-5.2 --k 3 --tag glm-w147b-k3
    uv run python scripts/rollout.py --dataset merrick \
        --task live-commitment-register --model kimi-k3 --k 3 --tag kimi-w147b-k3

Both currently have 2 graded trials of 3 — glm lost one to a provider
serving gibberish, kimi to a trial that wrote nothing. The scores are in
band; only the trial count is short. Consider `--k 5`, since both tiers
have shown a DNF rate on this task.

Then adjudicate the one row `certify` refuses:

    every trial declined
      'Samir Bhatt | Corporate deal status | 2026-05-13 | 2026-01-08 | 2'
    and 2 of them answered '3' for the same key

Unanimous disagreement in one direction is the signature of an oracle
defect, and four of the last five were. Use `scripts/disputed.py` to build
the adjudication pack from the key's own citation — do **not** re-run the
rule that produced the row over the source, which cannot disagree with
itself.

**3. Then the next family.** `out/delegation-135` finished recording (day
134.8 of 135, 53,865 events). It is the corpus for third-person
assignments — a genuinely different rule, not a fourth window of this one.
`datasets/merrick/assignment_rule.py` and its checker agree on 10,211
items across six corpora, but the family has no brief yet, and the open
question is the one measured and left undecided: whether a first-person
clause standing *before* a colleague severs the assignment.

## What is local-only and must not be committed

- `jobs/` — every sweep. Gitignored; contains plaintext API keys in logs.
- `out/` — bundles, world logs, the delegation recording. Gitignored.
- `.env` — `OPENROUTER_API_KEY`. Gitignored.

Scores live in `jobs/`, so a fresh clone can reproduce the *tasks* but not
the *measurements*. Re-running a sweep is the only way to recover those.

One caveat for a fresh clone: `band.py`'s superseded-key check compares
mtimes, and a clone rewrites them all, so it goes quiet. It is a guard for
the machine doing the work, which is where stale sweeps accumulate.

## What is settled, so it is not re-derived

- **More rows is not more difficulty when the rows are independent.** Row
  F1 is per-row: a reader accurate to `a` per extraction scores `a` on 26
  rows or on 117. A month-end snapshot design was measured at 117 rows and
  discarded before it was built.
- **Difficulty comes from joint dependency.** A row needing `k` facts is
  right with probability `a**k`. Both certified tasks key on something a
  reader who finds one end of a chain cannot produce.
- **A hard fact in the KEY collapses row F1; the same fact in a FIELD only
  degrades it by one part in N.** Measured on `due`: 1.000 against 0.179.
- **A short window has no chain to reconstruct.** At 42 days the median
  person revises once and opus scores 1.000; at 147 days the median is
  3.5. Chain depth against window length is measured in the
  `live-commitment-register` commit.
- **Correcting an oracle raises the strongest model.** opus went
  0.704 → 0.788 → 0.817 across three corrections with the model untouched.
  Fix the key first, then re-earn the band with real difficulty.
- **Two independent derivations agreeing proves consistency, not
  correctness.** Both were written from the same brief and
  under-implemented the same clause of it for weeks. The models were the
  only independent reader.
- **A zero is not a score.** Six causes now distinguished in `band.py`,
  the newest being a provider that returns text which is not language.
