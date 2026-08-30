# Measured laws

Every entry here was paid for. Each states a rule, the measurement behind
it, and what not knowing it cost — because a law with no measurement is an
opinion, and a law with no cost attached gets ignored the first time it is
inconvenient.

**How to use this.** Read it before designing a task, changing a grader, or
believing a score. When a new law is learned, add it here with its number,
its measurement, and its cost. When a law is *disproved*, do not delete it
— strike it and record what replaced it, because the reasoning that made it
plausible will recur.

**How to add one.** A candidate becomes a law when it has (a) a number
somebody could reproduce, and (b) a decision it would have changed. Without
both it is a note, and belongs in the relevant skill instead.

---

## Part I — What creates difficulty

### L1. A rule a model can turn into a program scores 1.000, whatever the corpus size

Coverage is not difficulty. A task whose rule is mechanical is solved by
writing the mechanism once and running it over everything.

**Measured:** three registers on this world sit at 1.000 for opus-5 with
grading fully sound — `unanswered-question-register`,
`no-op-revision-register`, `off-sense-register`. Bounding the corpus does
not move them.

**Cost:** three tasks built, measured, and dead. They still ship as
evidence, not as tasks.

### L2. Difficulty comes from a grouping key the agent must COMPUTE

A key that is a column is read. A key that is a computation is derived, and
deriving it is where models separate.

**Measured:** four tasks at 1.000 and one at 0.766; the separator was
whether the grouping key was a column or a computation.

### L3. More rows is not more difficulty when each row turns on one extraction

Row F1 is per-row. A reader accurate to `a` per extraction scores `a` on 26
rows and `a` on 117.

**Measured:** a month-end snapshot design was costed on paper at 117 rows
against 26, with 67% of the added rows new-or-changed. Estimated effect on
opus's row F1: none, because each snapshot row still hinges on a single
statement. Discarded before it was built.

**Cost:** none — this is the law working. Had it not been checked, a full
task build would have produced the same score with 4.5× the rows.

### L4. Difficulty is JOINT DEPENDENCY: a row needing `k` facts is right with `a**k`

To move a frontier model, make one row require several facts that are not
derivable from each other.

**Measured:** opus at `a ≈ 0.95` per extraction. Adding `first_due` (the
chain's other end) to a key already holding `due` and `superseded` moved
opus 0.817 → 0.706. Adding `slips` — which needs *every* link, not the ends
— moved a sibling task 0.852 → 0.755.

**Corollary:** pick facts that fail independently. Both ends of a chain and
its length are three reads of the same chain; a reader who finds one end
has none of the others.

### L5. A hard fact in the KEY collapses row F1; the same fact in a FIELD degrades it by 1/N

**Measured, on the same task and window:** keyed `(owner, meeting)` with
the date as a field → row_f1 **1.000**. Keyed `(owner, meeting, due)` →
row_f1 **0.179**. A wrong key means the row is not matched at all: every
field on it misses AND the invented row draws the extra-row penalty.

**Use it deliberately.** Key placement is the strongest difficulty dial
available and it is free. Field placement is the gentler one.

### L6. A short window has no chain to reconstruct

Supersession tasks need enough history for a date to actually move.

**Measured:** at a 42-day window the median person revises **once** and
opus scores 1.000; at 147 days the median is **3.5**. The same task, the
same rule, the same grader.

**Cost:** a task was declared at ceiling and nearly redesigned when the
window was the whole problem. Moving it also dropped the
dump-everything floor from 0.372 to 0.000.

### L7. A key component the model cannot derive is one the ORACLE cannot derive either

**Measured three times, each abandoned:** attributed deadlines, matter-keys,
assignment-rate. On matter-keys specifically: of 178 turns carrying a
commitment and a deadline, only 63 named a matter, and in those the matter
sat a median 96 characters from the commitment.

**Corollary — a conjunctive rule is safe only when its conjuncts share a
unit.** Who is speaking and what day they named are properties of a *turn*;
which matter a promise concerns is a property of a *clause*. Over long
turns those are different rules, and an agent reading correctly is graded
wrong.

---

## Part II — What corrupts a measurement

### L8. Correcting an oracle raises the strongest model

Every correction removes a judgement call, which is exactly what the
strongest reader was already getting right and being marked wrong for.

**Measured:** opus 0.704 → 0.788 → 0.817 across three corrections with the
model untouched. Across an earlier pass, 0.766 → 0.890.

**Therefore:** fix the key first and re-earn the band with real difficulty
afterwards. A task whose difficulty comes from its own defects is not
measuring anything. Never tune a score by leaving a known defect in.

### L9. Unanimous disagreement in one direction is the answer key, not the models

Genuine model error is stochastic; two runs drop overlapping but different
rows. When every trial of every tier declines the same row, or answers it
the same wrong way, the oracle is what they have in common.

**Measured:** four of the last five unanimous disagreements in this tree
were oracle defects. One task shipped with 11 of 20 rows wrong and three
model families declining all eleven.

**Corollary — the circularity trap.** Never verify a disputed row by
re-running the pattern that produced it. That check cannot fail. Adjudicate
against the source text, with a net deliberately WIDER than the rule.

### L10. Two independent derivations agreeing proves consistency, not correctness

If both were written from the same brief, they share its assumptions and
under-implement the same clause.

**Measured:** a rule and its independent checker agreed across **10,211
items in six corpora** while both were wrong in four separate ways. The
only reader that did not share the assumption was the model.

**Therefore:** independence must be at the level of ASSUMPTIONS, not code.
Route one derivation through characters and regex, the other through word
walking; select by `max`/`min` in one and by sorting in the other. And
treat model disagreement as a defect detector rather than as noise.

### L11. A DNF is not a zero, and averaging it drags an ABOVE-band task INTO range

How well a model answers and how often it manages to answer are different
facts. Folding one into the other puts any task in any band you like — and
the error runs the dangerous way: the more often a tier fails to answer,
the more certifiable its task looks.

**Measured:** a task certified with a tier reading `[0.0, 0.346, 0.383]`
for a mean of 0.243, where the 0.0 wrote no deliverable. Honest mean 0.365
on two trials — below the three required. The verdict had been reversed by
the bug.

**At least six causes produce a zero** and only one is about capability:
wrong answer, harness incompatibility, rate limiting, clock, abandoned
delegation, and a provider returning text that is not language. Read the
trial log before recording the number.

### L12. A stale sweep is worse than a missing one

It is a real number, from a real run, against a question nobody is asking,
and nothing about it looks wrong.

**Measured:** a table reported opus 1.000 on a task from a 42-day sweep
after the window had moved to 147 days, and glm 0.631 from a superseded key
while the current sweep said 0.545 — hiding a third in-band task entirely.

**Three checks, because there are three ways to go stale:** a changed KEY
(look for each graded field in the brief that trial was given); a changed
WINDOW (which changes no field at all — compare the brief's own generated
literals); and a changed ORACLE (compare the reward file's timestamp
against the oracle's, which needs nothing from the trajectory and is the
only check that works when the harness never records the prompt).

### L13. Measure one version of the task

Editing an instruction mid-sweep means tiers were measured on different
tasks, and nothing errors when it happens.

**Cost:** a rebuild mid-flight graded a trial against a key requiring a
field its instruction never mentioned. It scored 0.200 with a strong
answer on disk.

**Corollary:** when only the KEY moved and the brief did not, re-score the
saved deliverables instead of re-running. The work is already on disk, and
re-running measures a fresh sample of the model — a different, noisier
question that hides whether the correction moved the score or the dice did.

---

## Part III — What makes a gate worthless

### L14. A check that cannot fail is not a check

**Six species observed**, each with the tell that found it: a condition
whose branches are identical; an assertion of the form `x > y or True`; a
comparison of a value against itself; a gate reading a constant that has
drifted from the source it was meant to track; a verifier that re-runs the
rule it verifies; and a measurement whose inputs make only one outcome
reachable.

**Only mutation finds these.** Break the thing deliberately and require the
test to fail. A test suite that has never been mutated is a suite of
unknown value.

### L15. A gate that documents a check it does not perform is worse than no gate

The prose is load-bearing — it is what stops anybody looking again.

**Measured, three instances in one day:** `certify.py` promised in its own
docstring to exclude DNFs and averaged them as zeros; `checks/verify.py`
pinned the brief's phrase *"a question is not one"* and never tested for
it; a fidelity band was asserted and never run by any build.

**Therefore:** when a docstring states a rule, a test must assert the code
obeys it. Prose is a claim, not an implementation.

### L16. A gate that fails everything is indistinguishable from a gate nobody reads

**Measured:** 39 realism bands, **0 passing** — and the build printed the
failures and proceeded. Most had been written for a different institution
type, and at least one computed a number it could not compute (splitting on
`@` in a schema that stores `per-firstname-lastname`, never an address).

**Therefore:** a gate must be able to pass. Calibrate it for the world it
guards, delete the bands measuring fields the schema lacks, and make the
survivors block rather than print.

### L17. Capability without a caller is the most common serious defect

Correct code that nothing invokes. The subtlest form RUNS and can only
compute a constant.

**Measured:** a 90-minute wake grid made every persona's phase 0; a set of
realism bands whose only caller was pointed at a different firm's world and
marked xfail.

### L18. A derived figure graded as an exact scalar can only ever be 0

**Measured:** `superseded_count` against a true 132, with tiers reporting
118, 123, 124, 134, 98, 95 — within 6–11% and scored 0.000 every time.

**But read the direction before deleting it.** Answers that STRADDLE the
key mean the key is right and the models are imprecise: a hard criterion.
Answers that CLUSTER away from the key mean a convention mismatch: a
defect. The same symptom, opposite responses — and a gate that cannot tell
them apart nearly deleted the one criterion doing the discriminating.

**Better than either:** turn the scalar into rows. Partial credit becomes
possible and the reader can see *which* items were wrong.

### L32. A condition can be correct by luck on the corpus it was written against

Every solver here decided a standing series by counting MEETINGS while the
brief said a title must "appear on three or more days". On the world they
were written against those never diverged -- 8 series either way -- so
nothing could reveal it.

**Measured:** on a second world, one title is 4 meetings on 2 days: a
working session held twice, which the brief excludes, promoted to a
standing series worth two rows.

**Therefore:** a condition validated on one corpus is untested, not
correct. Run every rule against a second world before believing it, and
prefer the brief's own words over the convenient column.

### L33. A gate that can refuse its own invocation will

**Measured:** the guard against rebuilding under a running sweep scans
`ps` for `rollout.py` and `--task <name>`. One compound shell command that
stopped a sweep and then rebuilt appears as a SINGLE ps line carrying both,
so the guard reported four sweeps that were not running and refused every
build issued that way.

**Therefore:** a check that reads the machine's own state must exclude the
process asking. Match the interpreter, not the mention.

### L34. A key component chosen by watching a floor beats one chosen by argument

**Measured twice in one day.** A slippage register keyed on
`(owner, meeting, due, slips)` paid a no-comprehension dump **0.426** --
inside the band, with half the target range above a strategy that never
read a transcript, because `slips` is 0 for half the rows and guessing zero
is worth half the column. Adding `first_due` took the floor to **0.000**: a
dump can see the statements in front of it, but it cannot know where a
chain STARTED.

**Therefore:** measure `reported_every_candidate` before believing a key,
and treat a floor inside the band as a design defect rather than a note.

### L35. Two derivations can share a bug by sharing a bound

`_OWNER_REACH = 5` let the token route read "I'll get KLARA'S DATE pinned
down by end of day" as Klara owning the deadline; the regex route allowed
at most two words and read it correctly.

**Measured:** four tokens is the line. "assumes THANDIWE'S SIGN-OFF by
Wednesday" still matches at four, because a hyphenated deliverable is ONE
word to a regex and TWO to a tokeniser -- so the same bound means different
things to the two routes, and the number has to be set per route rather
than copied across.

**The rule underneath:** three words between a possessive and its
preposition means a verb phrase has intervened, and the day belongs to the
verb.

### L36. A shadowed name produces a plausible number, not an error

**Measured:** a verifier reported `meetings_read: 10` against a true 395,
because a loop variable named `room` shadowed the dict of meetings also
named `room`, and `len()` of a meeting id is 10.

**Therefore:** the dangerous bug is the one whose output looks like a
measurement. Assert magnitudes, not just types.

### L37. An oracle's mtime is part of the measurement record

A sweep is dated against the key that graded it — a reward file older than
its oracle came from a key that no longer exists. That is the only
staleness check that works when a harness never records the prompt, and one
whole tier in this tree is like that.

Which means rewriting a byte-identical oracle destroys measurements.

**Measured:** a rule correction propagated to seven solvers left three
oracles byte-for-byte identical — hashes compared before and after, which
is why it was believed safe. The rebuild moved their mtimes anyway, and the
band table went from **3 tasks in band to 0**, reporting two CERTIFIED
tasks as "graded against a superseded key" and discarding nine valid
graded trials.

**Therefore:** a build that produces the same bytes must not touch the
file. And more generally — a gate reading the filesystem's own bookkeeping
inherits every side effect of every tool that touches it. *"The contents
did not change"* is not the same as *"nothing changed"*.

### L38. A criterion with nothing to check returns 1.000

**Measured:** a register whose key held all five graded facts shipped with
an empty `FIELDS` mapping, so the per-row check had nothing to disagree
with. An empty answer scored **0.500** and an answer containing no work at
all scored **0.300** — three of ten points for a check whose outcome was
fixed by construction.

**The floors caught it, and only the floors could have.** No test fails, no
gate complains, and the score looks like a score.

**Therefore:** when a key absorbs every graded fact, the per-row dimension
must either be dropped or given genuine evidence to check — not padding,
but the fields that show the work was actually read.

### L39. Window variants cannot add tasks to a world already using its whole window

A shorter window is a real difficulty dial — but it only points one way,
and every register here already reads its world end to end. So a variant
can only be EASIER than a task that is already the easy end of the family.

**Measured:** a 90-day cut of a 182-day register gave 18 rows with a median
of **one** superseded commitment per row — most chains being two statements
long — and a dump floor of **0.364**. That is the same shape that scored
1.000 for the strongest tier at 42 days.

**Therefore:** to add tasks, add rules or worlds, not windows. A window
variant earns its place only where the parent does NOT already use the full
recording, or where the world is long enough that the shorter cut still has
chains in it.

The tooling is still worth keeping (`scripts/window_variant.py`), because
the next world may be longer — and because cutting a window by hand is how
a brief comes to state one window while its solver reads another.

### L40. The phenomenon's density sets a floor under the window, and realism cannot go below it

A practitioner will tell you the real work uses recent cycles, not six
months. Measure before agreeing.

**Measured:** blockers occur in 75 turns of 2,872 (58 before the rule was
corrected on 2026-08-29; the shape of the finding did not move). At the last 8
occurrences of each standing series the register has **2 rows**; at the last
12, four. A register that thin cannot score partially — every rollout comes
back 0 or 1.

**Therefore:** when a reviewer says the window is unrealistically wide, the
answer is a row count, not an argument. If the realistic slice is
ungradeable, say so plainly: the task measures a capability nobody would be
asked to exercise at that scale. That is true of most agent benchmarks and
is better said than dressed up.

### L41. The more faithful row definition is often the less measurable one

**Measured, on the same corpus.** A reviewer correctly observed that a
blocker register keyed on person × series conflates distinct waits. The
faithful fix — split a chain wherever it goes quiet for 60 days — gives 28
rows where 18 are a single raise, and hands the task to a strategy with no
chain reconstruction in it at all:

    every-complaint-is-its-own-episode, against the split register   f1 0.434
    the same strategy against the unsplit register                   f1 0.000

Forty-three per cent of the row set for never grouping anything.

**Therefore:** test a proposed row definition against the laziest strategy
that satisfies it before adopting it. A definition that reads more like the
real artifact can measure strictly less, and the tell is a floor rather than
an argument.

### L42. Do not tell the agent which surface holds the answer

A brief that lists six systems and then says "the answer is in the
transcripts, and only there" removes the tool-selection problem the six
surfaces exist to pose. No real brief does this.

**Measured side effect of the related fix:** the coverage counts that a
brief asks for back — how many meetings and turns were read — are audit
fields no reader wants, and they were paying two of ten points that every
tier earns. Moving them to the diagnostic dimension dropped the
empty-answer floor from **0.200 to 0.000**. The bottom of the target band
was arriving before the task began.

---

## Part IV — What makes a world usable

### L19. Surfaces must cohere, and rank correlation is how you check

A firm's busiest matter is busy everywhere. If it is not, the surfaces were
generated independently and the world is a set of unrelated logs.

**Measured on merrick:** billing hours against mail volume per person,
Spearman **−0.526** — the people who bill the most send the fewest emails.
Mail against meeting turns, **−0.360**. The same world's billing against
Slack (+0.52) and against meetings (+0.69) are fine, so the defect is
specific and locatable.

**Therefore:** compute per-person and per-matter rank correlation across
every pair of surfaces before building a task that spans them. A task
resting on an incoherent pair measures the generator, not the model.

### L20. A task family needs a world built for it

**Measured:** the working family lives on one surface of one world. Two
sibling worlds write promises with no dates at all, so the same rule
produces nothing there.

**Corollary:** check the premise before writing the task. Count the rows
the rule would produce on the actual corpus, not on an imagined one.

### L21. Engine failures become world data, and personas write policy about them

**Measured:** a simulated firm spent six months writing policies about a
bug in its own simulator — 0.8% of events. The fix is not to clean the
data afterwards but to stop the failure being VISIBLE to the personas; the
next recording was clean.

### L22. The surface a shell cannot flatten is the one worth grading

**Measured:** on this world, 21,597 time entries return in about seventy
seconds at zero context cost and the arithmetic over them is three lines. A
transcript has no id to group by and no column to sum.

**Corollary — three difficulty levers measured dead on this world:** rule
difficulty (opus 1.000 and 0.976 on two tasks built to punish an editorial
reader), coverage difficulty (bimodal, luck rather than skill, gone once
bounded), and procedure difficulty (scriptable; fifteen measured
wrong-branch payoffs had a median of 0.90).

---

## Part V — Grading shapes that decide what a score means

### L23. Normalize per-row credit by the truth set, never by the submission

Iterating what the agent sent and skipping unmatched rows makes
under-reporting free: three perfect rows out of a hundred scores 1.000.

### L24. Cap the invented-row penalty

A wrong answer must not wipe out work that was right. A cliff to zero tells
the reader nothing about what the agent knew.

### L25. Split grading into a reward dimension and a diagnostic dimension

Ship only the reward as the score. Presentation and process checks belong
where they inform without silently moving the number.

### L26. Do not grade what the brief hands over, and do not grade a tally twice

**Measured:** a window boundary the instruction states in prose, asked for
back as a field, was **10% of the reward on every task in a dataset** —
obtainable by transcribing one sentence. And six scalars carried 43% of one
register's reward while five were tallies of rows the grader already
scored.

**Corollary:** measure the floors. What does an empty answer score? What
does dumping every candidate score? If either reaches the band, the band is
not measuring comprehension.

### L27. A criterion at ceiling for a tier is not measuring that tier

A task can sit inside the band on its mean while the criterion carrying
half the reward reads 1.000 for the strongest model. The headline is then
an average of something measured and something that is not.

---

### L43. A key is chosen against a corpus, and the corpus may be a bug

Two worlds carrying the same rule, brief and grader measured DIFFERENT
right answers for how many components their key should hold. That was
recorded here as a law about corpora. It was a law about a defect.

**What was measured**, re-scoring saved deliverables on the blocker rule:

|  key  | merrick | delegation |
|---|---|---|
| (owner, meeting) | 1.000 | 0.953 |
| + first_raised | 0.900 | 0.785 |
| + last_raised | 0.900 | 0.729 |
| + raised_count | **0.700** | 0.561 |

merrick looked shallower -- 9 of 20 chains had `first == last`, so both
ends cost nothing and four components left the strongest tier at 0.900.
The fifth component went into the key to pull it back into band, and the
divergence was written up as two corpora honestly disagreeing.

**Then the rule was fixed.** It had been reading "waiting on me" as the
speaker stuck, keeping a wait the speaker said was over, and refusing
every complaint whose subject was left out -- which is how this firm says
most of them. Re-measured on the corrected oracle:

|  key  | merrick | delegation |
|---|---|---|
| (owner, meeting) | 0.944 | -- |
| + first_raised | 0.832 | -- |
| + last_raised | **0.640** | **0.846** |
| + raised_count | 0.480 | 0.654 |

The shallowness was the defect. Chains now run to 11 meetings and 15, four
components are right on both worlds, and the fifth still collapses the
weakest tier (0.177 -- beneath the threshold at which a criterion counts
as touched at all).

**What survives** is the method: re-score the saved deliverables under
every candidate key, per world, because the answers are already on disk
and it costs no rollouts.

**What does not** is the conclusion. A key measured against a corpus is
only as good as the oracle that cut the corpus, and a difficulty that
appears only in one world is a reason to go looking for a defect before
writing it down as a property of the world. Two sibling tasks disagreeing
about their own key is a smell, and it was read here as a finding.

### L44. The trials' own deliverables localise an oracle defect

A unanimous refusal says *something* is wrong with a row. What is wrong is
usually written in what the trials reported INSTEAD, and reading it is
free -- the answers are already on disk.

**Measured**, on five rows that blocked one certification:

| the key | what the trials said | what it meant |
|---|---|---|
| first 2026-01-22, count 14 | first 2026-01-**16**, count 14 | one turn missing at the START |
| first 2026-05-18 | 2026-04-**01** .. 05-18, count 2 | one turn missing, chain begins earlier |
| last 2026-03-05 | last 2026-05-**18** | the chain does not stop where the key stops |

Same count with a different start is not noise. It says the reader found a
turn the key did not and dropped one the key kept, which points at a
sentence rather than at a capability. Three of these five located the
defect to the exact turn before any judge was spent.

**Therefore:** before adjudicating, diff the key's row against the rows the
trials returned for the same owner. Structure in the disagreement is the
finding.

### L45. Every conjunct of a guard needs its own measurement

A guard that reads as one idea is usually several, and the ones that were
never measured are where it is wrong in both directions.

**Measured**, separating a report from an argument about a hypothetical
wait -- *"waiting on Bennett before flagging Rosalie just compounds the
delay"*:

| guard | rejects | correct |
|---|---|---|
| a gerund adjunct | 2 | 1 |
| ...and no first person in the clause | 1 | 1 |

The gerund test alone also rejects *"still waiting on Harriet ... before
drafting starts"*, which is a true report. And admitting a comma-carried
subject on "the previous segment heads with a verb" admits 7 turns, 6 of
them *"the deposition summary, **unscheduled**, blocked on the Martinez
transcript"* -- the summary is blocked, not the speaker. Requiring
complements as well as a verb admits 1, and it is the right one.

**Therefore:** measure each conjunct alone before shipping the conjunction.
A guard whose parts were never separated is a guard nobody has read.

### L46. A shared tool can be uncallable for a whole family, silently

Not dead code -- code that runs, is documented, is pointed at from a gate's
own error message, and cannot be reached by half the tasks in the tree.

**Measured**, in one adjudication, two tools deep:

- `disputed.py` unpacks a row label as `owner | group | value` and this
  family's key holds four parts. It failed at the assignment.
- `adjudicate.py` finds the brief's rule sections through a `PINNED` table
  and the blocker verifiers pin with `_STATED`. It found none and refused
  to run.

Both had been written, reviewed, documented and cited by `certify.py`'s
refusal message for weeks. Neither had ever been called by a task in this
family, and nothing said so until somebody tried at the moment it was
needed.

**Therefore:** when a gate names a tool in its refusal, run that tool
against the family the gate guards, once, before believing the path
exists. A capability with no caller looks exactly like a capability.


### L47. Two derivations can be stale in the same direction

The strongest check in this tree is two independently written derivations
of a rule having to agree before an oracle ships. It cannot see them both
being out of date.

**Measured:** one task alone vendored its own copies of the rule and the
checker into `solution/` and `checks/` instead of importing the world's
modules. Both forks drifted. The build compared one stale module against
the other, found no disagreement, and printed *second derivation agrees*
on every build for as long as that lasted.

    the world's rule admits      57  of 1,399 mail messages
    the vendored fork admits     61

Six messages, inside an answer key, behind a gate designed to catch
exactly this. The agreement was real; both sides were simply old.

**Therefore:** independence is necessary and not sufficient. A derivation
must also be the CURRENT one, which means importing the shared module
rather than holding a copy. Where a copy is unavoidable, hash it against
its source in the build. `md5` over every vendored module in the tree took
one command and found both of these.

### L48. At ceiling and at floor are not the same finding

A criterion every tier gets right is not measuring them. A criterion every
tier gets wrong might be measuring them perfectly.

**Measured**, on one register's three certified tiers:

| criterion | opus | glm | kimi | verdict |
|---|---|---|---|---|
| `meetings_read` | 1.00 | 1.00 | 1.00 | free — a date-filtered query |
| `turns_read` | 1.00 | 0.33 | 1.00 | keeps |
| `superseded_count` | 0.00 | 0.00 | 0.00 | **keeps** |

The third reads like the first: no separation, no signal, take it out. It
is the opposite. The oracle holds 128, the trials report 121 to 129, and
three of them reported exactly 128 — it is scored exact, so counting
almost all of the supersessions earns nothing. That is a hard criterion,
not an unscoreable one.

**Therefore:** before retiring a criterion nobody scores, look at what
they answered. Clustering near the truth is difficulty; scattering, or a
value no reader could produce, is a defect. **The test is whether anybody
has ever scored it**, and the answers are already on disk.


### L49. Reading the evidence yourself is not adjudication

L28 says print the evidence and never let the rule judge itself. That is
necessary and it is not sufficient, because the person who wrote the rule
reads the evidence through it.

**Measured, and the cost was nearly a wrong waiver.** A gate refused a task
over one row every trial declined, where five of them answered an earlier
date for the same key. The evidence was printed. It was read carefully. The
verdict was *the key is right and the models missed a late turn*, and a
waiver was one command away.

The judge panel -- shown the brief and the raw passage, never the code --
returned the opposite:

    "the ... characterization question is partially narrowed but not
     closed - still waiting on written confirmation from Ulrich-Bergmann's
     side"

The clause splitter had severed "still waiting" from its subject, and the
rule handed it to the speaker. The question was waiting. Five trials of
three tiers had been right, and the author of the rule had not been.

The tell was there and was explained away: **five independent trials
agreeing on a different value is not five models making the same mistake**.
That is the same signal as identical failures across independent trials,
and it points at the key.

**Therefore:** run the panel on every disputed row, including -- especially
-- the ones where the answer seems obvious. It costs three prompts. The
alternative is that a rule's author certifies their own rule, which is the
failure L28 describes wearing a different hat.


### L50. Count the implementations before fixing the rule

A rule with a shared module is not a rule in one place. Ask how many
copies exist, and check the answer, before believing an edit reached the
oracle.

**Measured:** the promise rule in this tree exists in **sixteen**
implementations — `promise_rule.py` and `promise_rule_check.py` on each of
two worlds, plus a full private copy inside each of seven solvers and
seven verifiers. Four tasks import the shared modules. The seven
commitment registers do not: each solver defines its own `commitment_in`,
and that copy is what computes the oracle.

So the first fix, applied carefully to both shared modules and verified
against the corpus, **moved zero rows**. It ran, it passed its own
differential check, and the answer key did not change, because nothing
that builds an answer key imports the thing that was fixed.

The tell was cheap and was not looked for:

    grep -l "^def commitment_in" datasets/*/tasks/*/solution/solve.py

**What made it survivable** is that the sixteen were byte-identical in
behaviour — 0 disagreements across both corpora before the change. The
copies had never drifted. The danger is not that copies are wrong; it is
that a copy is right until the day somebody fixes the original.

**Therefore:**

- before editing a rule, enumerate every implementation of it and fix all
  of them in one change;
- afterwards, compare each copy against the shared module over the whole
  corpus, and require 0;
- the two-derivation gate will catch a partial fix — solver against
  verifier — but only for the tasks whose two copies disagree, and it
  reports the disagreement as a task defect rather than as what it is.

L47 says two derivations can be stale in the same direction. This is the
same failure at the level of the tree: sixteen derivations, all agreeing,
none of them the file that was edited.


## Part VI — Process

### L28. Print the evidence, then adjudicate; never let the rule judge itself

Build the adjudication pack from the key's OWN citation and from the rival
value the trials reported — both passages together. A judge shown only the
key's evidence can confirm that passage and leave the row wrong anyway,
because what makes it wrong is elsewhere.

**Cost:** a passage was hand-picked four times and the fourth was wrong —
the speaker had two turns in the cited meeting and the judges were handed
the first. They returned SPLIT on evidence that contained no promise at
all, and nothing about the verdict looked wrong.

### L29. Differential testing across generated corpora is the highest-yield check

Each generator's text habits expose different assumptions in a rule.

**Measured:** running one rule against six corpora found defects that
8,893 items of a single corpus did not.

### L30. "N edits applied" is not "the code does what I think"

**Measured:** a propagation script reported six successful edits and had
silently produced TWO definitions of the same function in two files. Python
takes the later one, so the copy that was carefully patched never ran.

**Therefore:** verify structurally — parse the file and count the
definitions — rather than trusting a replace count.

### L31. Run the tests, then READ the result, then commit

**Cost:** twice in one day a commit went out red because the suite and the
commit were issued in the same breath.
