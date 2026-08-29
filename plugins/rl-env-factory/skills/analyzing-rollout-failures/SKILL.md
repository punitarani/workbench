---
name: analyzing-rollout-failures
description: Use when reading eval rollouts, trial logs, or trajectories to work out why a model scored below ceiling - covers what a zero actually means, DNF handling, sample size, and certifying a miss as a model failure rather than a task defect. Load before recording any score.
---

# Reading a rollout without fooling yourself

## A zero is not a score

At least five distinct causes produce 0.000 and only one is a claim about
capability:

| cause | signature |
|---|---|
| wrong answer | a deliverable exists and grades badly |
| harness incompatibility | tool bridge rejects the model's payload; no tool calls land |
| rate limiting | tool calls succeed, then a limit error, trials die in seconds |
| clock | many tool calls, real work in progress, no deliverable, timeout raised |
| abandoned delegation | a few steps of a large budget, work handed to sub-agents, turn ends with them uncollected |
| **sub-agent auth** | the main agent works and writes scratch files; sub-agents 401 against the *provider's real endpoint* rather than the pinned gateway |

The sub-agent row is the newest and the easiest to misread, because the
trial looks busy. One sweep scored 0.000 three times over; the transcript
showed eight sub-tasks dispatched, four ticked complete in under three
seconds each, and scratch files written to the workspace — and then, buried
in the agent log, eighty lines of:

    [subagent-6] Non-retryable error (HTTP 401): Missing Authentication header
    [subagent-6] Endpoint: <the vendor's public API, not the pinned gateway>

Every one of them from a sub-agent and none from the main agent, which had
planned the task correctly. Two details separate this from a bad key.
*Missing*, not rejected: no credential was sent at all. And the endpoint is
the vendor's own, so the pin was lost as well.

The obvious diagnosis — sub-processes did not inherit the environment — was
wrong, and cost a sweep to disprove. The sub-agents knew the provider and
the model, which they could only have read from the framework's **config
file**; what that file did not carry was the endpoint or the key, because
the harness had supplied both as environment variables. A sub-agent that
rebuilds its client from config gets whatever config holds and nothing
else.

**Put the endpoint and the credential where the framework's own config
lives, not only in the environment.** A credential and its endpoint are one
setting: set them the same way, in the same place, and never with a
fallback that a pre-existing value silently wins.

**An agent whose delegation is broken still looks like an agent that is
working**, right up until the deliverable is missing. The tell is timing:
sub-tasks that "complete" faster than a model can answer did not answer.

Check `submitted-*.json` in the verifier directory. If the names are the
agent's own scratch vocabulary rather than the deliverable the brief names,
it never reached an answer — and *why* it did not is the question, not
*whether* it could.

**Read the trial log before recording the number.** A model scoring 0.000
where another scores 1.000 has usually not been measured at all.

A timeout is a DNF **only when nothing was written**. If the deliverable
exists and the grader scored it, the trial answered and the score stands
however the run ended.

Before attributing any failure to a model, verify that model directly
against the provider with a minimal two-turn tool round-trip. Harness
incompatibility and model incapacity are indistinguishable downstream,
and the round-trip separates them in one call.

## Prove the harness against a known number before trusting a sweep

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

## Never average a non-answer as a zero

A DNF averaged in as zero drags any task into any band you like:
`1.000 + 0.600 + nothing` reads as 0.533 and looks well calibrated.

Score the trials that produced an answer. Require at least two, so the
estimate is never a single sample. Report the completion rate *beside*
the score rather than folded into it — **how well a model answers and how
often it manages to answer are different facts.**

## Sample enough to see through the harness

Abandonment is a *rate*, not a capability. One task measured 1-of-3
answered at k=3 and 8-of-9 at k=9: the sample was the artefact, and a
whole account of the model's behaviour had been built on it.

Three samples of a binary outcome cannot distinguish 1-in-3 from 1-in-9.
Use **k=9 wherever completion is unreliable**, and never describe a
completion rate estimated from three attempts as a property of the model.

## Measure one version of the task

An instruction edited mid-sweep means tiers were measured on different
tasks. Timestamp the job against the instruction and re-run any tier that
read a superseded version. Nothing errors when this happens; only a
timestamp comparison catches it.

## Two grading shapes that decide what a score means

**Normalize per-row credit by the truth set, never by the submission.**
Iterating over what the agent sent and skipping unmatched rows makes
under-reporting free: an agent returning three perfect rows out of a
hundred scores 1.000. Iterate the oracle's rows, and cap the invented-row
penalty so a wrong answer cannot wipe out work that was right — a cliff
to zero tells the reader nothing about what the agent knew.

**Split grading into a reward dimension and a diagnostic dimension**,
ship only the reward as the score, and assert the dimension set is
exactly what you expect. Presentation and process checks belong in the
diagnostic half, where they inform without silently moving the number.

---

# Classifying a miss

## The circularity trap

The most expensive error available: verifying a disputed row by re-running
*the pattern that produced it* over the source. That check cannot fail. It
agrees with the oracle by construction — and it agrees just as
confidently about rows the pattern never produced.

> **A check that cannot fail is not a check.**

Two published scores were certified as model failures this way. Both were
the answer key. Every miss in them was the author's.

## Three checks that can disagree with you

1. **Identical failures across independent trials.** Genuine model error
   is stochastic; two runs drop overlapping but different rows. When
   independent trials drop the *same* set, the oracle is what they have in
   common. This is the only mechanical test for a task defect that does
   not go through the rule.
2. **A net wider than the rule.** Adjudicate a disputed row by matching a
   deliberately over-broad pattern — an asserted strict superset of the
   rule, over the whole corpus — and *print the sentence*. The verdict is
   then read off the source text rather than off the regex that produced
   the row.
3. **Did anyone find it?** Cheap, and it settles most flags.

## When the models agree with each other and not with you

Three model families declining the *same* rows is the strongest signal
available that the answer key is wrong, and it is worth spelling out what
to do with it, because it recurs.

**Partition twice, independently.** From the rollouts: which oracle rows
did EVERY trial decline. From the corpus: pull each disputed speaker's
whole contribution with **no pattern applied** and read the sentence the
oracle cites. If the two partitions name the same rows, you are done
arguing. On one task they matched exactly — 10 rows, derived two ways.

**Then re-grade the submissions you already have.** They are on disk and
they cost nothing, and the models never saw the correction, so it is
uncontaminated evidence. **Validate the re-scorer first by reproducing
every shipped reward exactly.** A first attempt missed the extra-row
penalty and read every score high by ~0.06 — it would have "confirmed"
the fix either way.

Expect the ordering to be preserved and the spread to *widen*. If a
correction reorders the models, it is not a correction.

**The likeliest cause is not a typo in the rule — it is that the prose is
right and the code implements something weaker.** Check the brief before
blaming it. On one task the brief already forbade all eleven bad rows in
its own words; the extractor tested same-sentence co-occurrence and
nothing else.

**A second derivation will not save you here.** Two implementations
written from the same brief tend to under-implement it the same way. One
walked characters, the other tokens, and both encoded the identical
too-narrow negation rule — citing the same justifying example. They
agreed on all 2,872 utterances and were both wrong.

**Fix in both directions or not at all.** Every candidate rule reports
*defects removed* AND *sound rows kept*. Validating on the disputed rows
alone is how a clause rule that removed 7 of 10 defects also destroyed 7
of 10 good rows.

## Structure in an error is a convention mismatch, not a mistake

Model error is shapeless. When the error has *structure* — a constant
offset repeated across many rows, values far too meaningful to be
invented, a whole category missing — the oracle's convention differs from
the agent's, and the agent is usually reading the world correctly.

The clearest instance: rows dismissed as hallucinated dates turned out to
be a quarter end and a national filing deadline. Dates that meaningful
are read, not invented.

**Ask what would have to be true for the agent to be right, before asking
why it was wrong.**

## Reading the signal correctly

- Compare **rows dropped by every trial**, not the worst pairwise
  overlap. With four trials there are six pairs and the maximum is high
  by chance; one real case flagged 64% while five of six pairs sat
  between 4% and 12%.
- Compare the **actual deliverable**. Agents leave working files behind;
  a fallback that reads any JSON in the directory will diff a scratch pad
  against the oracle and call the result a model failure.
- **Include trials with no failures.** Filtering empty sets turns "dropped
  by every trial" into "every trial that had any", which excludes the
  strongest evidence *against* a defect.

## A task at ceiling hides its ambiguities

Only low scores get audited, so a task scoring 1.000 for the strongest
tier is not thereby clean — the strong model resolved the ambiguity the
way the oracle happened to, and the defect stays invisible until a model
careful enough to read semantically meets the same corpus.

**A score that jumps to ceiling when an instruction is clarified was
never measuring the model.** Audit the class, not just the outliers.


---

# A stale sweep is worse than a missing one

It is a real number, from a real run, against a question nobody is asking
any more, and nothing about it looks wrong.

**Measured:** a summary table reported the strongest tier at 1.000 on a
task from a 42-day sweep after the window had moved to 147 days, and
another tier at 0.631 from a superseded key while its current sweep said
0.545 — hiding a third in-band task from the count entirely.

Three ways to go stale, and they need three checks:

- **A changed KEY.** Look for each graded field in the brief that trial was
  given. A trial never asked for a field cannot be scored on it.
- **A changed WINDOW.** This changes no field at all, so the field check is
  blind. Compare the brief's own generated literals — the dates and counts
  written into the prose rather than typed.
- **A changed ORACLE.** Compare the reward file's timestamp against the
  oracle's. This needs nothing from the trajectory, which matters because
  some harnesses never record the prompt at all — and for those, no content
  check can work.

**Guard the content checks with an anchor.** Require the deliverable's own
name to appear before reading a field's absence as evidence; without that,
the same logic refuses every trial whose harness kept no prompt.

**Break ties by recency, never by tag name.** Alphabetical ordering put
`glm-rev-k3` ahead of `glm-rev2-k3` and reported the older sweep.
