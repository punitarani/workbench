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

The mechanism is worth stating because it predicts the next failed
lever: **deterministic gradeability implies programmatic solvability.**
The oracle is a program, so a task with a deterministic answer key is by
construction reducible to a program — and an agent with a shell will
write it. Scale is then a cost, not a difficulty.

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
- **Every ordering on the replay path is explicit.** Gather concurrent
  results in declaration order, never completion order; assign sequence
  numbers at emission rather than at enqueue. Concurrency that reorders
  is nondeterminism wearing a performance argument.
- **Split generation by kind.** Structure a real institution's own
  systems would produce — rosters, engagement records, cycles, calendars
  — derives deterministically from the seed. Every piece of language or
  judgment is a model call grounded against that structure. A structural
  generator that starts emitting prose has crossed into authorship.
- **The referee is deterministic: zero model calls.** Whatever turns
  actor intents into world facts resolves each reference against world
  state or rejects the intent, and rejections become feedback the actor
  sees. A referee that improvises cannot be replayed.
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
- **Find what actually serializes before provisioning for parallelism.**
  A generated world's cost is not its total call count, it is the length
  of its critical path. In one engine, actors wake in cohorts and the
  whole cast wakes together, so useful concurrency equals the cast size —
  measured at exactly the internal headcount, with everything provisioned
  above it doing nothing. Two consequences, and the first is easy to get
  backwards: **cast size is nearly free**, because a cohort runs in
  parallel, while **tick count and tail latency are the whole cost**.
  A rate like "calls per minute" hides this; a histogram of concurrent
  work does not.
- **A cohort's wall time is its slowest member.** A model tier used by one
  call in ten still sets the pace for the other nine. Reach for the fast
  tier when buying fidelity — it writes the world — and keep the deep tier
  cheap enough not to dominate the critical path.
- **Coarsening the simulated clock does not buy wall time.** Widening the
  wake interval threefold gave each actor threefold more accumulated
  context per wake, so per-tick work rose and cancelled the tick
  reduction. The work a simulated day contains is a property of the day,
  not of how finely it is sliced.
- **Read what the referee refused, not only what it recorded.** A
  deterministic referee resolves every reference against world state and
  rejects what it cannot resolve — that is exactly right, and it means a
  world can be *structurally incomplete* while every component behaves
  correctly. The actors reach for something the world does not offer, the
  referee refuses, and the record simply has less in it than the day did.
  Measured: 16.8% of one firm's attempted timekeeping vanished because the
  people had administrative and internal work to book and no code to book
  it against, so they invented plausible ones and every rejection was
  correct.

  Nothing else catches this. **Coherence checks look for a fact carrying
  two values; they cannot see a fact that was never recorded.** The
  materializer writes what exists, and any figure computed over the
  survivors is perfectly self-consistent and answers a question about an
  institution that does not exist. Gate the *loss rate* out of the
  referee's own rejection notes, and write the gate's message so it blames
  the world rather than the referee — otherwise the next reader fixes it
  by making the referee permissive, which trades a visible gap for an
  invisible one.
- **A bound applied in declaration order encodes a priority nobody
  chose.** Any list an actor is shown gets capped so it does not flood the
  prompt, and the cap almost always keeps the first N. But what is
  declared last is usually the *shared* material — the institution-wide
  codes, the defaults, the things belonging to nobody in particular — and
  those are exactly what every actor needs. Measured: standing matter
  codes fell outside the cap for the whole cast, people invented
  references for work they genuinely had to record, the referee correctly
  refused, and 20.7% of attempted timekeeping vanished.

  The trap has a second half worth naming. The obvious fix — *add the
  missing codes* — made it **worse**, 16.8% to 20.7%, because six more
  entries pushed the shared ones further past the cap. **Fixing the
  symptom a rejection names, without measuring the mechanism underneath,
  can move the number the wrong way.** Reserve the shared slots
  explicitly, and make the reservation a no-op below the cap so every
  existing recording stays byte-identical in content *and order*.
- **Set thresholds between two measured worlds**, a known-bad and a
  known-good, rather than at a round number. A band picked by intuition
  either never fires or fires constantly, and in both cases stops being
  read.
- **Vendor parity constrains realism.** Adding *content* a real product
  would serve is a gain; adding *tools* it would not is a loss wearing a
  gain's clothes — an agent trained against an invented tool learns a
  call that fails in the real product. When a surface cannot host your
  content, put the content where the real product would.
- **Artifacts must be the file types the institution exchanges, and the
  mix must be gated.** A world whose every document is markdown has
  quietly removed a whole class of work — opening a workbook, reading a
  deck, pulling a table out of a print form. Format is an *emergent*
  property, so it drifts: one recorded world produced 19 markdown and 33
  workbooks with no documents, decks or issued PDFs at all, from an
  authoring prompt that asked for the real form every time, while a later
  run of the same firm produced documents and still no decks. Assert the
  share of each form directly, and treat a form the institution really
  produces but the world never emits as a failure rather than a
  preference.
- **Validate on every write path, not only the first one.** Creation
  checked that a document declaring a structured format really parsed as
  one; revision did not, and the revise path drafts prose. A workbook
  worked forward came back as text, kept its declaration, and
  materialized as a file claiming a form it did not have — 10 of 52
  documents, discovered only when something finally read the file room.
  **An invariant enforced at one entry point is not enforced.**
- **Which artifact is which is domain knowledge, so it belongs to the
  world.** A shared authoring prompt can describe form in the abstract;
  it cannot know that filing a brief is what makes it final. Put that
  vocabulary in the workplace definition — and where recorded runs key on
  exact prompt bytes, make it an opt-in field that renders nothing when
  unset, so every existing recording stays byte-identical.

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

### The deliverable's shape must not answer the question

**A schema that names each half of a distinction has given the
distinction away.** A rule says what the answer *is*; a procedure says
where to *look*. State the first, never the second, and check that the
output shape does not decompose the judgment the task exists to measure.

### Every decision the rule leaves open is a coin flip

An agent cannot win an unstated choice by working harder. Enumerate the
vocabulary of any object-valued field and require every key, including
the zero-valued ones; fix every tie-break and ordering in the
instruction; and name the units. If two defensible answers exist, the
task is measuring which one the agent guessed.

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
| **Grading guards** — the reference answer scores 1.000 with the criterion *bodies executed*, not merely registered | graders that silently score every boolean zero |
| **Key uniqueness on both sides** — the grader's row key distinguishes every real row, in the oracle and in the second derivation | a key that collapses two rows caps the achievable score below 1.0 for reasons no agent can fix |
| **Counts single-sourced** — no figure restated in an instruction, metadata, or docstring that the oracle also computes | restated numbers drift and nothing catches them |

### Two things the independence check must not share with the solver

**The computation, where more than one is defensible.** Sum-then-round
and round-then-sum are both reasonable; the verifier must use whichever
the solver did not, or the agreement proves nothing.

**The source of the rule.** Transcribe it from the instruction the agent
is graded against, never from the solver — copying the solver's
expression reproduces its bug and then certifies that the two agree.
This bites hardest on **tie-breaks and orderings**, which rollouts almost
never exercise because real data rarely ties. Test those on a hand-built
fixture.

And derive any assumption the generator and solver *both* rest on — a
cutoff, a snapshot boundary — separately. Their mutual agreement is not
evidence, and a shifted boundary makes every row wrong together while
every row-level check stays green.

### Catch the type that is actually raised, not the one you reasoned about

A guard is written against the exception the failing code *constructs*.
By the time it propagates, a framework in between has often re-raised it
wrapped in its own type — after its own fallback also failed. The guard
then catches something that no longer arrives, and the failure it exists
to absorb goes straight through.

This is invisible to review and to the obvious test. The one guarding
this boundary asserted `"except <TypeName>" in source`: a **source grep
cannot tell whether a guard catches what is thrown**, so the source went
on saying exactly what the test wanted to see while a third failure mode
walked past it. Assert on types — construct the real error, including
the wrapped form, and check `isinstance` against the caught tuple.

Two companions, both of which have bitten:

- **The rescue must not raise inside itself.** A handler that calls a
  method only one arm of its caught tuple has will take down the run it
  exists to keep alive — a rescue that works only for the failure it was
  already catching.
- **Degrading content is not degrading loudly.** Keep the split explicit:
  transport, budget and replay-integrity failures raise, because they
  mean the run is invalid; one actor's one malformed turn becomes that
  actor doing nothing, which the record shows.

Worth knowing what triggers it: a stronger model writing more natural
prose. Quotation marks inside a string field — *characterize this as
"compliant" until* — close the JSON early. Upgrading a model tier changes
the distribution of outputs, so it re-tests every parser downstream.

- **Falsify with the same tool you edit with.** A gate is only trusted
  once you have broken the thing and watched it fail — and the break
  itself can silently not happen. A `sed` substitution that matches
  nothing exits 0, the suite stays green, and the honest conclusion
  ("this test does not catch that") is exactly backwards. Confirm the
  mutation landed before believing the verdict, and prefer the editor you
  would use for a real change over a one-liner whose escaping differs
  between platforms.

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

### Prove the harness against a known number before trusting a sweep

A rollout harness has many parts in series — a provider gateway, a job
runner, a container, an agent binary, a model, a grader — and a fault in
any of them produces the same artifact: a deliverable that is absent and
a score of 0.000. That is indistinguishable from a model that cannot do
the task, which is why the taxonomy calls it *not a score at all*.

So run **one trial of an already-measured task** and check the number it
returns against the number on record. Not "did it error" — a green run
proves the pipes connect; a run that lands on a previously measured value
proves they connect *correctly*. A harness returning 0.62 with no
exceptions looks healthy, and every measurement after it is quietly
wrong.

Expect the faults to be **chained**, and expect reading not to find them.
One such path had five, each strictly gating the next: a job name the
aggregator does not search, a hardcoded port where the gateway binds an
ephemeral one, an import root the child process never inherited, a
missing gateway credential, and a model id in the wrong form for the
driving agent. Four of the five were invisible to inspection, because the
earlier ones stop the process before the later stages exist.

Two of them had already been *verified* — in a configuration the real code
path never uses. An import checked with the variable set by hand tests
your shell, not what the child inherits. **A check that passes for
reasons unrelated to what it claims to establish is the circularity trap
wearing a harness.**

While you are there, time a trial. Trials times tiers times k, divided by
concurrency, is the wall clock of every sweep you are about to plan.

### Never average a non-answer as a zero

A DNF averaged in as zero drags any task into any band you like:
`1.000 + 0.600 + nothing` reads as 0.533 and looks well calibrated. Score
the trials that produced an answer; require at least two so the estimate
is never a single sample; and report the completion rate *beside* the
score rather than folded into it. **How well a model answers and how
often it manages to answer are different facts.**

### Two grading shapes that decide what a score means

**Normalize per-row credit by the truth set, never by the submission.**
Iterating over what the agent sent and skipping unmatched rows makes
under-reporting free: an agent that returns three perfect rows out of a
hundred scores 1.000. Iterate the oracle's rows, and cap the
invented-row penalty so a wrong answer cannot wipe out work that was
right — a cliff to zero tells the reader nothing about what the agent
knew.

**Split grading into a reward dimension and a diagnostic dimension**,
ship only the reward as the score, and assert the dimension set is
exactly what you expect. Presentation and process checks belong in the
diagnostic half where they inform without silently moving the number.

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

### Structure in an error is a convention mismatch, not a mistake

Model error is shapeless. When the error has *structure* — a constant
offset repeated across many rows, values that are far too meaningful to
be invented, a whole category missing — the oracle's convention differs
from the agent's, and the agent is usually reading the world correctly.

The clearest instance: rows dismissed as hallucinated dates turned out to
be a quarter end and a national filing deadline. Dates that meaningful
are read, not invented. **Ask what would have to be true for the agent to
be right, before asking why it was wrong.**

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

### Do the band's arithmetic before designing for it

A three-model mean with a frontier tier pinned at 1.000 is not a target
on all three models — it is a budget on the other two. For a ceiling of
0.8:

    mean = (1.000 + a + b) / 3 <= 0.80   <=>   a + b <= 1.40

Every task measured in band on one suite has the frontier at 1.000; what
separated in from out was entirely the weaker pair's sum, and the
boundary is about 0.05 wide. Three in-band tasks summed 0.73, 1.32 and
1.38; the one that missed summed 1.43.

Two consequences worth internalising before a build:

- **"A frontier model would score 1.000" is not, by itself, a rejection.**
  It is the expected case, and the design question is what the *named*
  weaker tiers do. Treat frontier 1.000 as a defect only when the
  frontier *misses* — because then the miss is far more likely to be a
  task defect than a capability limit.
- **The margin is thin, so measure the mechanism before building.** At a
  0.05-wide boundary, an unmeasured guess about difficulty is a coin
  flip, and the honest response to landing at 0.81 is to report it rather
  than to lever it.

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

### Confusability beats length — and the operative variable is off-sense share

The hardest rule measured was the *shortest*: two spellings of one common
word, sitting a hair from its own inflections, missed at 70% by a model
that had read the text. A seven-form list of distinctive date patterns
scored far higher for every tier. **Fewer forms, more temptation.**

**Corrected by measurement.** The natural reading of that result — pick
the family with the densest *excluded* near-misses, the inflections a
careless matcher would over-admit — is wrong, and it is wrong in a way
that wastes builds. A machine matching a word boundary is never confused
by a neighbouring inflection; only a human or a model reading for
*meaning* is.

What actually predicts the miss is the **off-sense share of the admitted
form**: how often the required word appears in the corpus meaning
something other than the thing the register is named after. In the family
that produced the hardest measured task, a majority of occurrences of the
admitted word are adjectival (*the complete picture*, *the complete,
dated calendar*), idiomatic, future (*I can typically complete this
analysis*), or conditional (*once that call is complete*) — measured at
79% inside the graded window. Those are precisely the rows the weaker
tiers dropped: a model reading for sense filters them out, and the rule
says they count.

So the selection metric is: **for each candidate family, hand-classify a
sample of admitted-form occurrences as on-sense or off-sense, and choose
the highest off-sense share.** Exclusion density is a decoy — and worse,
it is easy to satisfy with a family that is dead on the actual corpus.
Check both forms are alive before anything else: one family that looked
ideal on paper had its second spelling appear in a single message out of
1,585, and another's in none at all.

Two shapes with the same root, both measured:

- **A form inside a longer phrase**, where the rule admits it and a
  reader hears a hedge (`within a day` inside *"within a day or two"*).
- **One sentence carrying two forms that resolve to different values**,
  where the second reads as an explanation of the first. Every trial
  found the first; two of nine found the second.

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

**Stub the grading framework faithfully, not permissively.** A stub that
accepts what the real runtime would reject turns every guard built on it
into decoration — reproduce name resolution, argument binding and
description formatting, and share one registry with the real path.

The same applies to the shell around the experiment. Watchers that grep
for a process name are themselves processes with that name in their
command line; parallel sweeps against one account rate-limit each other;
`set -- $spec` splits in bash and does not in zsh. Each of those produced
output that looked like a finding.

---

### Smoke the whole pipeline on one day before recording many

Generating a long history is the most expensive step and the last one you
can cheaply redo. Every gate downstream of it — coherence, the derived
rebuild, artifact mix, whatever the world owes its tasks — reads
something the recording produces, and none of them run until the
recording is done.

So record **one day**, export it, and run the entire downstream pipeline
against it before starting the long window. Four separate defects were
found this way in a single pass, each in minutes, each of which would
have cost the whole recording had it surfaced at the end: a validator
missing from one of three write paths, a bound that hid the shared
codes everyone needs, a format the world could never produce because
nothing gave anyone a reason to produce it, and a malformed document in
the world's own definition.

The last one is the sharpest argument for the practice. **It was a defect
in the spec, not in the engine** — the seeded workbook folded its header
into the data rows. It is valid JSON and reads correctly to a human, and
the first thing that would ever have disagreed was the renderer, at
materialization, at the very end.

A one-day world costs a few minutes and exercises every stage. Order the
work so the expensive irreversible step is the *last* thing you start,
not the first.

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
8. **Write down what generalizes — here, not in a run record.** Record
   falsified hypotheses with their measurements, including the ones that
   make a headline result smaller, and correct earlier conclusions **in
   place** rather than appending a softening note. Date difficulty claims
   separately from defect claims: a defect is permanent once found, while
   a difficulty claim is only true of the tiers that were measured, and a
   later measurement can overturn it.

   When the same defect class appears a third time, stop fixing instances
   and promote it to a gate with a companion test that fails when a new
   task of that shape joins uncovered.
