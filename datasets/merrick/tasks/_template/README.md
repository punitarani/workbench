# _template

Not a task. The shape a task takes here, so that authoring one is filling
in a rule rather than rediscovering a structure.

Copy the directory, rename it, and change five things:

| file | what changes |
|---|---|
| `task.toml` | name, description, the deliverable's filename |
| `instruction.md` | the brief — who you are, the rule, the deliverable |
| `solution/solve.py` | the rule, as the oracle computes it |
| `tests/criteria.py` | `ROWS`, `KEY`, `FIELDS`, and the aggregate list |
| `tests/verify.py` | the rule again, derived a *second* way |

## The two things that are not boilerplate

**`tests/verify.py` must not share the solver's expression of the rule.**
Transcribe it from `instruction.md` — the prose the agent is graded
against — never from `solve.py`. Copying the solver reproduces its bug
and then certifies that the two agree. This has produced two published
scores that were the answer key rather than a measurement.

**`KEY` must distinguish every real row, on both sides.** A key that
collapses two rows caps the achievable score below 1.0 for reasons no
agent can fix — and it does *not* show in row F1, because both sides
dedupe identically and F1 still reads 1.000. It shows in the per-row
check. Assert the row count before and after keying.

## Before the first rollout

Run `datasets/merrick/build_tasks.py --task <name>`. It refuses a build
whose file room is wrong, whose world lost timekeeping, or whose task set
is empty, and it verifies the reference solution against the committed
oracle byte for byte.
