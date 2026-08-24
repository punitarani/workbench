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
| `checks/verify.py` | the rule again, derived a *second* way |

## The two things that are not boilerplate

**`checks/verify.py` must not share the solver's expression of the rule.**
Transcribe it from `instruction.md` — the prose the agent is graded
against — never from `solve.py`. Copying the solver reproduces its bug
and then certifies that the two agree. This has produced two published
scores that were the answer key rather than a measurement.

**`KEY` must distinguish every real row, on both sides.** A key that
collapses two rows caps the achievable score below 1.0 for reasons no
agent can fix — and it does *not* show in row F1, because both sides
dedupe identically and F1 still reads 1.000. It shows in the per-row
check. Assert the row count before and after keying.

## Scope every conjunct to the same unit

A rule with more than one part is safe only when its parts are properties of
the same thing. This is the defect that has cost this dataset the most, and
it has now bitten the same task twice.

`live-commitment-register` first graded "a commitment, on a matter, by a
day" over a **turn**. Who is speaking and what day they named are properties
of a turn; *which piece of work a promise is about* is a property of a
clause. Over 71-word turns those came apart in both directions — 65% of the
firm's real promises discarded for not naming a matter in the same breath,
and a third of the kept rows pairing a promise with a matter mentioned more
than 120 characters away.

The matter column was removed. Then the *same defect* was found one conjunct
over: owner and deadline were still paired at turn scope, where both are
present but not necessarily *together*. Eight of twenty-five rows were a
docket manager reciting somebody else's deadline beside an undated promise,
or a date used as a condition. Two frontier models independently declined
all eight, and the sentence-scoped count matched one of them exactly.

**Both parts being properties of a turn does not make their pairing one.**

Before filling a rule with two or more conjuncts:

1. Name the unit each conjunct lives in — token, clause, sentence, turn,
   message, thread, day.
2. If they differ, the rule is not gradeable as written. Drop the conjunct
   that lives in the smaller unit, or scope the whole rule down to it.
3. Measure it: count how many units satisfy each conjunct alone, and — in
   the units that satisfy all of them — the character distance between the
   conjuncts. A median in the tens is a rule; a median in the hundreds is
   co-occurrence wearing a rule's clothes.

## Before the first rollout

Run `datasets/merrick/build_tasks.py --task <name>`. It refuses a build
whose file room is wrong, whose world lost timekeeping, or whose task set
is empty, and it verifies the reference solution against the committed
oracle byte for byte.
