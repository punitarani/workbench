# Method

How to build a simulated world, cut tasks from it, measure models against
them, and know that what you measured was the model.

[`WORKBENCH.md`](WORKBENCH.md) is what this system *is*.
[`runs/`](runs/) is what happened on particular days. This file is what
we learned that holds on the next dataset, in another domain, with a
different model — the rules, not the record.

## Why this file exists

A [frontier failure-mode study](runs/2026-08-09-four-month-history/FAILURE-MODES-FRONTIER.md)
established, with paid measurements, that task volume does not move a
frontier model (0.84 → 0.81 when contested rows doubled), that stacking
independent judgments per row moves it the *wrong way* (0.87), and that
the sub-0.5 target belonged to a sub-frontier tier. A week later, on a
different dataset, all three were re-derived from scratch at the cost of
eight built-and-discarded difficulty levers — along with the harness fix
that same document had already specified.

Nothing was lost or contradicted. The findings had simply been filed
under `runs/`, which this tree labels *history, not guidance*, so the
next build did not read them. **A finding that generalizes is not a run
record.** When a measurement tells you something true about building
environments rather than about one Tuesday, it belongs here.

---

## 1. The only acceptable failure

A task exists to measure a model. Every point it loses is therefore a
claim, and the claim is only honest if the loss came from the model.
Five things can take a point away:

| class | what it means | what it demands |
|---|---|---|
| **E — environment** | the fact is not reachable through the served surface, or the record contradicts itself with no stated rule | postmortem; the environment is wrong |
| **D — data** | the world's content is incoherent — a document whose body contradicts its registered name, time booked against the wrong matter | postmortem; the world is wrong |
| **H — harness** | the agent never got to answer: incompatible tool bridge, rate limit, setup timeout, abandoned delegation | not a score at all; fix or discard |
| **T — task** | the instruction is ambiguous, the oracle is wrong, the grader is wrong, a tolerance is unfair | fix and re-measure |
| **M — model** | reachable, unambiguous, oracle independently confirmed, and it got it wrong anyway | **the only one that may ship** |

The classes are not equally likely. On a mature environment, **T is by
far the most common and the easiest to mistake for M**, because a task
defect and a model failure both look like a number below 1.0.

### The decisive question

> **A defect blocks every trial. Difficulty just makes most of them miss.**

Before calling any miss M, ask whether *any* trial of *any* model found
that row. If one did, the row is findable and the rule is applicable —
whatever the others did is the model's. If none did across many trials,
suspect yourself first.

---

## 2. What a frontier model actually fails at

### The theorem

> Expert-solvable ⇒ a rule exists ⇒ a frontier model applies it.

This is not pessimism, it is the definition. "Expert-solvable" means a
competent professional could produce the answer from a stated rule. A
frontier model applies stated rules at roughly 93% per row and does not
degrade with row count. So the only ways below that ceiling are to
remove the rule — which destroys expert-solvability — or to grade
all-or-nothing, which converts the measurement into a coin flip on one
row.

**Plan for this rather than discovering it.** Difficulty targets should
name a capability tier, not a number in the abstract.

### Levers measured to do nothing

Each of these was built, measured against a frontier model, and came
back at ceiling. Do not spend a build on them again without a reason the
list does not cover.

| lever | how it was tested | result |
|---|---|---|
| volume | contested rows doubled at equal judgment depth | 0.84 → **0.81** |
| depth | four independent judgments per row, traps on 19 of 30 | 0.84 → **0.87** (wrong way) |
| width | 1,300 entries, 27 pages, ~200 rows | ceiling |
| coverage | rows 189 → 507, corpus 328 → 1,547 messages | score went **up** |
| correlated error | a task built for it | 1.000 in 26 shell commands |
| lexical near-miss | 171 near-miss temptations | 1.000 |
| semantic synonym | 70 synonyms excluded by rule | 1.000 |
| chained derivation | three dependent steps per row | **403 of 403** derivations correct |
| office files | 19 workbooks, 61 sheets, no index, nothing in SQL | 1.000 |
| constraint satisfaction | ruled out before building — see below | not fairly buildable |

What they share: **the agent computes each row locally and mechanically
from text it has already pulled onto disk.** Against a written script,
per-row rules are free however many links the chain has, and independent
errors average out instead of compounding.

### The distinction that does work

There are two kinds of difficulty and they behave oppositely under
bounding.

**Coverage difficulty** — did the agent enumerate the corpus? Bimodal:
1.000 or ~0.3, decided by whether it finished. It is *luck*, it produces
unstable means, and it **disappears** the moment the corpus is small
enough to finish.

**Rule difficulty** — did the agent apply the stated rule to text it has
already read? A **rate**. One model read 1,574 of 1,585 messages — 99.3%
coverage — and still found 48 of 110 rows, catching 23 of 82 occurrences
of a single common word. **A rate does not care how much text there is**,
so it survives bounding.

This is why "make the corpus smaller so every tier can finish" and "keep
it hard" are not in conflict, once you know which kind you have.

### Why the distinction stays hidden

A frontier model has neither problem. Coverage and rule application look
identical when a model does both perfectly. **Any difficulty conclusion
drawn from a single frontier model is drawn from a sample that could not
have shown otherwise.** Measure at least one tier that fails, or you are
measuring your own ceiling.

---

## 3. Building the world

The world must be *true* before anything cut from it can be *fair*.

- **Determinism is the product.** Every generator takes an explicit
  seed and produces identical bytes for identical input. No wall-clock,
  no unseeded randomness, no dependence on dict or filesystem ordering.
  Without this, no measurement is repeatable and no defect is
  reproducible.
- **Loud failure, always.** Cassette misses, budget exhaustion, integrity
  violations and transport errors raise. A world that degrades silently
  produces scores that mean nothing and cannot be traced.
- **The offstage boundary is structural, not conventional.** The agent
  reaches the world through materialized data and tool servers over
  projected databases — never through simulation internals, personas,
  hidden state, or reward logic. Enforce it in the type system so it
  cannot be forgotten.
- **Coherence gates before materialization.** Contradictions block;
  ambiguities are reported and are raw material for hard tasks. A record
  that says two things with no stated precedence rule cannot be graded:
  the answer would depend on which statement the agent happened to read.
- **Derived directories are rebuilt wholesale, never incrementally.** A
  materializer that writes files and never removes them will accumulate
  several worlds in one directory. This is invisible until the first
  task grades those files, because nothing reads a stale surface until
  something does.
- **Set thresholds between two measured worlds**, a known-bad and a
  known-good, rather than at a round number. A band picked by intuition
  either never fires or fires constantly, and in both cases stops being
  read.
- **Vendor parity constrains realism.** Adding *content* a real product
  would serve is a gain; adding *tools* it would not is a loss wearing a
  gain's clothes — an agent trained against an invented tool learns a
  call that fails in the real product. When a surface cannot host your
  content, put the content where the real product would.

---

## 4. Building a task

### The instruction is a brief

It is the only prose the agent gets, and it must read as a colleague's
handoff: who you are, what happened, the precise professional rule that
defines the answer set, and the deliverable's name and shape. Never name
the scaffolding — no databases, no servers, no grading, nothing that
reveals the work is scored. A rule that fixes an exact answer set is a
professional standard; phrase it the way the firm would.

### State the rule, then state which kind of rule it is

The single most expensive defect class in this repo, found **five times
on five tasks**: an instruction whose *prose* describes a concept and
whose *test* is string matching. The two disagree, a careful reader
trusts the concept, and the grader trusts the string — so the model that
read more carefully loses points.

Examples of the gap, each of which cost a measurement:

- a register of *promises* whose rule matches tokens anywhere in a body
- "that message *asks for something*" implemented as twelve phrases,
  where `we need` appears inside "what we need to deliver"
- "work reported *complete*" implemented as the word `complete`, which
  also matches "that gives you the complete picture"

**If the rule matches words in prose, the instruction must say the test
is textual and not editorial** — and say it in the instruction, not in
the solver's comments. There is a second, distinct version of this:
whether a form *inside a longer phrase* still counts (`within a day`
inside "within a day or two"). Saying "textual not editorial" does not
settle that one; say it separately.

### Check the rule against the corpus before shipping it

Count how the world actually writes the thing before fixing the rule's
vocabulary. One rule required an article the corpus used **once** while
the firm wrote the bare form 34 times, so it admitted 1 of 35 real
instances and scored the rest as hallucinations. The author's intuition
about how people write is not evidence; a frequency count over the
corpus is, and it costs one query.

The same check governs transplanting a rule to a new grain: measure the
near-miss ratio there first. A literalism task is only hard where the
near-misses are dense.

### Build only on joins the world records explicitly

If a relation has to be *inferred* — which engagement a document belongs
to, which contact counts as the client — the oracle built on it is not
deterministic, and the disagreement surfaces as a model failure. Either
the world records the relation as a field, or the task does not grade it.

### Structural floors

| floor | why |
|---|---|
| ≥ 12 rows | fewer cannot express partial credit; the task reads 1.000 or near zero with nothing between |
| no constant-valued graded field | a column with one value grades nothing — an agent that never looks scores full marks |
| every graded value reachable through the served surface | a rule the agent cannot evaluate through the tools is not a task rule |
| exact-match aggregates alongside row F1 | one wrong row should move several criteria; this is what converts a small real error into a mid-band score |
| the reference answer scores 1.000 against its own grader | otherwise the ceiling is not 1.0 and every score below it is misread |

### Bound the work, not only the answer

If a task reports a figure computed over the whole corpus — "how many
records you examined" — the agent will examine the whole corpus, even
when the answer set is a small window of it. On large corpora that
alone can take a model from a good score to *no deliverable at all*.
Bound what must be read, not just what must be reported.

---

## 5. Gates, and how to earn the right to trust one

Every gate below exists because its absence cost a wrong verdict. Each
must be **falsified before it is trusted**: break the thing deliberately
and confirm the gate fails. A gate that has never failed is a gate you
are guessing about.

| gate | catches |
|---|---|
| **Oracle independence** — derive every answer a second time from raw events, never from the projection the solver reads | wrong solver rules that would otherwise silently become the answer key |
| **Reachability** — crawl the real servers, require every graded identifier to appear in what they serve | oracles keyed on internal ids no tool emits |
| **Coherence** — sweep served surfaces for one fact carrying two values | contradictions with no stated precedence |
| **Degeneracy** — report constant columns, empty lists, thin row counts | criteria that grade nothing |
| **Rule-accepts-its-own-phrasings** — assert the pattern matches the examples the instruction itself gives | a regex narrower than the prose it implements |
| **Textual-test declared** — any task matching forms in prose must say so | the prose-versus-literal class above |
| **Rounding convention declared** — any task summing quantities must say which order it rounds in | a coin toss between sum-then-round and round-then-sum |
| **Grading guards** — the reference answer scores 1.000; every criterion resolves, binds and formats | graders that silently score every boolean zero |

### Size tolerances against the defect, not for comfort

A numeric tolerance must be strictly smaller than the smallest defect the
gate exists to catch. One epsilon set generously "for safety" was larger
than the rounding drift it was written to detect, so the gate passed
while the defect it was built for sat underneath it. **A tolerance chosen
for safety is decoration.**

### The independence check has a blind spot — know it

An independence check that re-derives the answer from a second source
**cannot catch a rule that disagrees with its own prose**, because the
rule is the specification both derivations share. That is what makes the
rule-accepts-its-own-phrasings gate a different check and not a
duplicate.

---

## 6. Measuring a rollout

### A zero is not a score

At least five distinct causes produce 0.000, and only one is a claim
about capability:

| cause | signature |
|---|---|
| wrong answer | a deliverable exists and grades badly |
| harness incompatibility | tool bridge rejects the model's payload; no tool calls land |
| rate limiting | tool calls succeed, then a limit error, trials die in seconds |
| clock | many tool calls, real work in progress, no deliverable, timeout raised |
| abandoned delegation | few steps of a large budget, work handed to sub-agents, turn ends with them uncollected |

**Read the trial log before recording the number.** A model scoring
0.000 where another scores 1.000 has usually not been measured at all.

A timeout is a DNF only when **nothing was written**. If the deliverable
exists and the grader scored it, the trial answered and the score stands
however the run ended.

Before attributing any failure to a model, verify that model directly
against the provider with a minimal two-turn tool round-trip. Harness
incompatibility and model incapacity are indistinguishable downstream,
and the round-trip separates them in one call.

### Never average a non-answer as a zero

A DNF averaged in as zero drags any task into any band you like:
`1.000 + 0.600 + nothing` reads as 0.533 and looks well calibrated. Score
the trials that produced an answer; require at least two so the estimate
is never a single sample; and report the completion rate *beside* the
score rather than folded into it. **How well a model answers and how
often it manages to answer are different facts.**

### Sample enough to see through the harness

Abandonment is a *rate*, not a capability. One task measured 1-of-3
answered at k=3 and 8-of-9 at k=9; the sample was the artefact, and a
whole account of the model's behaviour had been built on it. Three
samples of a binary outcome cannot distinguish 1-in-3 from 1-in-9. **Use
k=9 where completion is unreliable, and never describe a completion rate
estimated from three attempts as a property of the model.**

### Measure one version of the task

An instruction edited mid-sweep means tiers were measured on different
tasks. Timestamp the job against the instruction and re-run any tier that
read a superseded version. Nothing errors when this happens; only a
timestamp comparison catches it.

---

## 7. Classifying a miss without fooling yourself

### The circularity trap

The most expensive error available: verifying a disputed row by
re-running *the pattern that produced it* over the source. That check
cannot fail. It agrees with the oracle by construction — and it agrees
just as confidently about rows the pattern never produced.

> **A check that cannot fail is not a check.**

Two published scores were certified as model failures this way. Both
were the answer key. Every miss in them was the author's.

### Three checks that can disagree with you

1. **Identical failures across independent trials.** Genuine model error
   is stochastic; two runs drop overlapping but different rows. When
   independent trials drop the *same* set, the oracle is what they have
   in common. This is the only mechanical test for a task defect that
   does not go through the rule.
2. **A net wider than the rule.** Adjudicate a disputed row by matching a
   deliberately over-broad pattern — asserted a strict superset of the
   rule over the whole corpus — and *print the sentence*. The verdict is
   then read off the source text rather than off the regex that produced
   the row.
3. **Did anyone find it?** The question from §1. Cheap, and it settles
   most flags.

### Reading the signal correctly

- Compare **rows dropped by every trial**, not the worst pairwise
  overlap. With four trials there are six pairs and the maximum is high
  by chance; one real case flagged 64% while five of six pairs sat
  between 4% and 12%.
- Compare the **actual deliverable**. Agents leave working files behind;
  a fallback that reads any JSON in the directory will diff a scratch pad
  against the oracle and call the result a model failure.
- **Include trials with no failures.** Filtering empty sets turns
  "dropped by every trial" into "every trial that had any", which
  excludes the strongest evidence *against* a defect.

---

## 8. Iterating difficulty

### Legitimate levers

- how much of the record a task covers
- how many independent facts per row
- how confusable the rule is (see below)
- which capability tier the target is set against

### Forbidden levers

- tightening a tolerance
- reweighting criteria so the same work scores less
- withholding a rule, or trick wording
- grading a fact the surface does not serve

The test: **change what the agent must do, never what the same work is
worth.** A task that scores lower without being harder is a scoring
artifact, and the "calibration" is a property of your grader rather than
of the world.

### Confusability beats length

The hardest rule measured was the *shortest*: two spellings of one common
word, sitting a hair from its own inflections, missed at 70% by a model
that had read the text. A seven-form list of distinctive date patterns
scored far higher for every tier. **Fewer forms, more temptation.**

### Adding a fact only adds difficulty for a model that lacks it

Grading "which rule produced this row" cost the weaker tier 0.05 and the
stronger tier nothing — the stronger model matched the form in order to
emit the row, so naming it was free. Extra graded facts **widen the gap
between tiers** rather than lowering all of them. Useful for
discrimination; nearly useless for pulling a mean down.

### When a task sits just outside

Say so. A task that measures the same value across three independent
methodological corrections is a stable measurement of something just
outside the target, not a task fighting noise. Report it out rather than
adjusting until it isn't — and if a lever is applied, declare it before
seeing which way it moves the result.

---

## 9. Check your own tooling

The measurement apparatus is part of the system being measured. In one
build, the tools written to stop the author trusting a number contained
**five bugs**, each of which produced a false verdict:

- an aggregator that discarded a valid score because it was outnumbered
  by non-answers
- a detector that reported the worst pairwise overlap instead of the
  common one
- a detector that read agents' scratch files as answers
- a detector that excluded the trials with no failures — the strongest
  counter-evidence
- an unbound-method call that silently rejected its own inputs

All five were found the same way: **comparing what the tool printed
against a hand computation.** None would have been found by running it
again.

**When a defect class appears a third time, stop fixing instances.**
Promote it to a suite-wide gate, and add a companion test that fails when
a new task joins the suite without being covered — a guard whose list
goes stale is the same trap one level up.

**Write the cost into the gate.** Each gate's docstring should carry the
measured numbers of the defect it prevents. A gate that only says what it
checks gets weakened by the next maintainer who finds it inconvenient; a
gate that says "this cost 30 rows and a wrong verdict about a model" does
not.

The same applies to the shell around the experiment. Watchers that grep
for a process name are themselves processes with that name in their
command line; parallel sweeps against one account rate-limit each other;
`set -- $spec` splits in bash and does not in zsh. Each of those produced
output that looked like a finding.

---

## 10. The loop

1. **Record a world.** Determinism, loud failure, coherence green.
2. **Rebuild derived state wholesale** and reconcile counts against the
   source of truth.
3. **Cut a task.** Brief, stated rule, declared rule-kind, structural
   floors met.
4. **Gate it** — independence, reachability, degeneracy, guards,
   reference answer at 1.000. Falsify each gate once.
5. **Measure at k≥3, and k=9 wherever completion is unreliable.** Read
   every trial log before recording a number.
6. **Classify every miss.** Oracle re-derived; failures scattered rather
   than shared; disputed rows read in the source. Anything not M is a
   defect — fix it and return to step 4.
7. **When the numbers move, re-derive the queue from the blocking
   condition** rather than extending the previous plan. Long
   asynchronous work drifts from its goal silently: nothing errors, and
   the runs measure something you have stopped needing.
8. **Write down what generalizes — here, not in a run record.**
