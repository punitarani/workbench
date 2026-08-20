---
name: gating-environment-quality
description: Use when adding tests or gates that protect an eval suite's correctness - oracle independence, reachability, coherence, degeneracy, rule-phrasing, grading guards. Also covers falsifying a gate and auditing your own measurement tooling. Load before trusting any check you wrote.
---

# Earning the right to trust a gate

Every gate below exists because its absence cost a wrong verdict.

**Falsify each one before trusting it.** Break the thing deliberately and
confirm the gate fails. A gate that has never failed is a gate you are
guessing about.

## The gates

| gate | catches |
|---|---|
| **Oracle independence** — derive every answer a second time from raw events, never from the projection the solver reads | wrong solver rules that would otherwise silently become the answer key |
| **Reachability** — crawl the real servers, require every graded identifier to appear in what they serve | oracles keyed on internal ids no tool emits |
| **Coherence** — sweep served surfaces for one fact carrying two values | contradictions with no stated precedence |
| **Degeneracy** — report constant columns, empty lists, thin row counts | criteria that grade nothing |
| **Rule-accepts-its-own-phrasings** — assert the pattern matches the examples the instruction itself gives | a regex narrower than the prose it implements |
| **Textual-test declared** — any task matching forms in prose must say so | the careful reader losing to the string matcher |
| **Rounding convention declared** — any task summing quantities must say which order it rounds in | a coin toss between sum-then-round and round-then-sum |
| **Grading guards** — the reference answer scores 1.000 with criterion *bodies executed*, not merely registered | graders that silently score every boolean zero |
| **Key uniqueness on both sides** — the grader's row key distinguishes every real row, in the oracle *and* in the second derivation | a key that collapses two rows caps the achievable score below 1.0 for reasons no agent can fix |
| **Counts single-sourced** — no figure restated in an instruction, metadata, or docstring that the oracle also computes | restated numbers drift and nothing catches them |
| **Link and reference resolution** — every relative link in the guidance tree resolves, anchors included | docs are a surface no code imports, so nothing fails when one rots |

## What the independence check must not share with the solver

**The computation, where more than one is defensible.** Sum-then-round
and round-then-sum are both reasonable; the verifier must use whichever
the solver did not, or the agreement proves nothing.

**The source of the rule.** Transcribe it from the instruction the agent
is graded against, never from the solver. Copying the solver's expression
reproduces its bug and then certifies that the two agree.

This bites hardest on **tie-breaks and orderings**, which rollouts almost
never exercise because real data rarely ties. Test those on a hand-built
fixture.

And derive any assumption the generator and solver *both* rest on — a
cutoff, a snapshot boundary — separately. Their mutual agreement is not
evidence: a shifted boundary makes every row wrong together while every
row-level check stays green.

## The independence check has a blind spot

It **cannot catch a rule that disagrees with its own prose**, because the
rule is the specification both derivations share. That is why
rule-accepts-its-own-phrasings is a different gate and not a duplicate.

## Catch the type that is actually raised, not the one you reasoned about

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

## Size tolerances against the defect, not for comfort

A numeric tolerance must be strictly smaller than the smallest defect the
gate exists to catch. One epsilon set generously "for safety" was larger
than the rounding drift it was written to detect, so the gate passed
while its own defect sat underneath it.

**A tolerance chosen for safety is decoration.**

- **Falsify with the same tool you edit with.** A gate is only trusted
  once you have broken the thing and watched it fail — and the break
  itself can silently not happen. A `sed` substitution that matches
  nothing exits 0, the suite stays green, and the honest conclusion
  ("this test does not catch that") is exactly backwards. Confirm the
  mutation landed before believing the verdict, and prefer the editor you
  would use for a real change over a one-liner whose escaping differs
  between platforms.

## When you fix a gate, its old tests assert the old defect

Tests written against a gate that could not see something are, by
construction, a specification of the blind spot. Widen the gate and they
go red — and they fail in the shape of *"your fix is too aggressive"*,
which makes loosening the rule the tempting response. That restores the
blind spot and leaves the suite green.

A worked case. A timekeeping gate could not catch its own index case: one
actor missing one category of work measures ~1% however long the run,
because a rate does not accumulate. Adding a persistence rule — the same
reference invented again and again is a missing code, not a typo — turned
a test named *"a little drift is tolerated"* red. Its fixture was
`[note("x")] * 5`: **one** reference, five times. That is not drift, it
is the defect in miniature, and the test had been holding it in place.

**Read the fixture, not the assertion.** The assertion tells you what
somebody expected; the fixture tells you what was actually measured, and
it settles the argument without any appeal to thresholds. Then keep the
opposite case too — a genuine typo must still pass, or the gate fires
constantly and stops being read.

And gate the push on the *test result*, not on the commit succeeding.
`commit && push` runs the push whichever way the suite went.

## Guard the guard

A check that matches nothing passes vacuously. Every audit that iterates
a discovered set needs a companion assertion that the set is non-empty
and roughly the expected size. A guard whose list goes stale is the same
trap one level up.

## Your measurement tooling is part of the system being measured

In one build, the tools written to stop the author trusting a number
contained **five bugs**, each producing a false verdict:

- an aggregator that discarded a valid score because non-answers
  outnumbered it
- a detector reporting the *worst pairwise* overlap instead of the common
  one
- a detector reading agents' scratch files as answers
- a detector excluding trials with no failures — the strongest
  counter-evidence
- an unbound-method call silently rejecting its own inputs

All five were found the same way: **comparing what the tool printed
against a hand computation.** None would have been found by running it
again.

The shell around the experiment counts too. Watchers that grep for a
process name are themselves processes with that name in their command
line; parallel sweeps against one account rate-limit each other; word
splitting differs between shells; BSD and GNU `sed` disagree on word
boundaries, so a substitution can silently do nothing. Each of those has
produced output that looked like a finding.

## A gate that never runs agrees with everything

Before trusting any check, confirm something executes it.

An audit of a mature suite found the obvious thing nobody had looked for:
every task shipped an independent second derivation of its answer key, a
test forbade that file from sharing rule literals with the solver, the
independence was real — and **no code path ever ran it**. It had been
decorative for the life of the project. The gate protecting the gate was
present; the gate itself was never invoked.

This is cheap to check and almost never checked:

```bash
grep -rl verify.py --include='*.py' --include='*.sh' --include='*.yml' . \
  | grep -v 'tests/verify.py$'      # who *runs* it, not who *is* it
```

Quote the globs. Unquoted, zsh expands `*.py` against the current directory
before `grep` ever sees it and the whole command dies with `no matches
found` — while the pipeline still exits 0, so it reads as "nobody runs it".
A command that fails into the answer you were looking for is the same trap
this section is about, and the first version of this line had it.

The same question applies to a shared module that must ship beside the
thing importing it. One project's older suites had accumulated
twenty-eight near-identical copies of the same grading logic, each inlined
beside the task that used it. A newer suite factored them into one shared
module and stopped shipping it: every grader raised
`ModuleNotFoundError` on load, every task scored zero, and a total wipeout
across all models reads as catastrophic model failure rather than a
missing file. The unit tests passed throughout, because they add the
project root to the path and the grader does not. **The suite and the
runtime import the same file through different doors.**

## A substring pin cannot see an exception added

Pinning a verifier's assumptions to the brief with
`insists("Cc recipients are not addressees" in brief)` catches that
sentence being removed or reworded. It is blind, by construction, to a
sentence being **added**. The brief gains *"...unless the sender copied
themselves"*, every pinned string is still present, and every pin passes.

Measured on one suite: 17 of 18 and 12 of 16 brief mutations went
unnoticed, including full inversions of a rule and of a tie-break. The
pins were not weak individually. They answered *"is this sentence still
here"* when the question is *"does this section still say only what I
think it says"*.

Answer the second question with a digest of the whole normalised rule
section — strip emphasis and collapse whitespace, since rewrapping happens
constantly and means nothing, then hash the rest. Any edit breaks it,
addition included.

It is deliberately coarse: rewording a rule without changing its meaning
fails too. That is the behaviour you want. A rule the agent is graded
against should not change without someone confirming the second derivation
still implements it. Say so in the failure message, and say not to paste
the new digest in to make the check pass — because that is exactly what
the next person will reach for.

## Declaring a criterion and registering one are different acts

The worst defect this method has produced was invisible because the
declaration looks like the whole job.

Every task in a suite shipped a criteria file naming its rows, its key and
its graded fields, and a shared module holding the criterion bodies behind a
`@criterion` decorator. Nothing ever **called** them. The decorator makes a
criterion *available*; something has to invoke it with that task's answer key
before the harness has a reward to compute. A task with only declarations
discovers **zero** rewards, the harness writes an empty set, and downstream
that reads as a score rather than as a failure — so every trial of every
model returns nothing, and the transcript looks like total model collapse.

It survived two adversarial audits and a careful structural comparison
against a sibling suite that worked. The comparison asked *where the
decorators live* and concluded a star-import carried them, which was true and
beside the point. What the working suite had and this one never did was the
invocation itself, in files the broken suite had no copy of.

The check that found it was not a code reading. It was running the harness's
own discovery against both suites and comparing the counts:

```python
from your_harness.runner import discover

len(discover(f"{task}/tests"))  # working suite: 2.  broken suite: 0.
```

**Ask the harness what it found, not the source what it declares.** Any
system with a registry — rewards, plugins, routes, fixtures, migrations —
can be fully specified and entirely unregistered, and the source will read
correctly the whole time.

## A stale copy answers a question you did not ask

Four times in one session a check produced a confident result about the
wrong artefact, and every one looked like a verdict on the code:

- a materialized bundle built when the world had thirty documents, read as
  proof that two file formats were never produced — the renderer had always
  produced them;
- a world log exported nine hundred events earlier, compared against a live
  document count, reported as "one document produced no file";
- a brief resolved before a worked example was corrected, whose pin then
  fired and looked like the pin was wrong;
- a task copied to scratch before the very change under test, so the
  falsification passed and the fix looked ineffective.

None of these is a subtle bug. Each is a snapshot that was correct when
taken, used after the thing it snapshotted moved. They are hard to notice
precisely because the artefact is real and the check runs cleanly — nothing
errors, and the number that comes back is a true fact about a world that no
longer exists.

**Check the mtime before believing a derived artefact, and copy after
editing rather than before.** When testing a change, prefer running against
the real path over a copy; if isolation is genuinely needed, make the copy
the last step before the run, not the first step of the setup.

The tell is a result that disagrees with something you just did. That is
usually not a discovery.

## Test the entry point, not the parts

Three defects in one session had the same shape: a component built
carefully, verified in isolation, and never connected to the path that runs.

- A verifier's `recompute()` was updated when a field was dropped, along with
  its sort and its brief pins. `main()` was not, and raised `KeyError` on
  every invocation. Three separate verifications passed; the build calls
  `main()`.
- A module for checking one artefact against another was written, tested
  standalone, and never imported by the thing it was written for.
- A grading module was factored out and stopped being shipped beside the file
  importing it.

Every one of these passes a review that reads functions, and fails the first
time anything runs end to end. If a check has never been exercised through
the entrance the system actually uses, it is not verified — it is drafted.

## A gate against a world you cannot regenerate must refuse on impact

Two gates written in one session both had to be rewritten, for the same
reason, and the second one was written after the first was fixed.

Both refused on a **property of the generator**: one on the share of records
whose timestamps were malformed, one on the presence of files the generator
had left empty. Both were true measurements of real defects. Both would have
blocked the only build available, because the generator was frozen mid-run
and could not be corrected — so the gate's demand could not be met by any
action anyone could take.

The tempting repair is to raise the threshold until it passes. That is
relaxing a gate because it fires, and it teaches everyone downstream that
this gate means nothing. The real repair is to notice the gate is aimed at
the wrong question.

> Not *how much did the generator get wrong*, but **did any of it reach
> something that ships**.

Rewritten that way, both became stronger rather than weaker:

- the timestamp gate reports the rate at any level and refuses only if a
  malformed record survived into the **served** state, which the projection
  quarantines — a check that cannot be satisfied by moving a number;
- the empty-file gate reports, and blocks only if a task grades the content
  that is missing — which the measurement cannot know and the caller can.

**The distinction that decides it:** can a rebuild fix this? A file room
that is 40% notes, a document lost to a name collision, an oracle naming an
identifier no tool serves — all of those are shape problems, and the fix is
to rebuild. Missing content, or a corrupt field the writer keeps writing, is
not fixable downstream at all. Gate the first on presence. Gate the second
on whether it reaches a score, and record the rest where the writer gets
fixed.

A related trap in the same family: a threshold calibrated while the world is
still being written is calibrated against a moving number. One of these
gates was set at 2% when the defect measured 8% and rising; it read 15% two
weeks later. If a limit must be a number, derive it at build time from the
finished record rather than freezing yesterday's reading into the source.

## Spot-checking your own work samples the case you built most carefully

Eight mutations against the newest task, eight catches, conclusion: the
approach works. The same approach on the older tasks in the same suite
caught almost nothing. The sample was the file written most recently, with
the most attention, by someone who had just been thinking about exactly
these failures.

An independent pass over the whole suite is not redundancy. It is the only
thing that samples the work you were not careful about.

## Two files can hardcode the same wrong reading and never disagree

An independence check with **zero shared code** can still be circular.
Shared *literals* are the visible half; shared *assumptions* are the half
a diff cannot see.

A worked case. A verifier was rewritten to share nothing with its solver
— different matcher, different arithmetic, zero common expressions, and
it passed a shared-literal gate cleanly. It read the rule's vocabulary
out of the instruction's own table. But it read only two of the table's
three columns: the spellings and the key. The third column, *what each
form falls due on*, it hardcoded — identically to the solver.

So the brief could say `end of week` means the **Sunday**, and both
derivations would go on computing the Friday, agree with each other
perfectly, and report that the oracle matched an independent reading of
the instruction. Mutation-tested against the brief, **20 of 27
single-phrase rule flips went unnoticed**: every due-date cell, the
tie-break direction, the sort order, three of the four clauses defining
the follow-up, and the window's inclusivity.

**The test is to mutate the specification, not the code.** Change one
stated rule in the instruction and require the verifier to fail. If it
passes, that rule is pinned to nothing and the second derivation cannot
be a check on it.

The repair is cheap: before using a value the brief states, assert the
brief still states it. Flatten the relevant chunk — drop emphasis,
backticks, line wrapping — and refuse unless the phrases the arithmetic
rests on are still present. Keep the phrase-to-code pairing in one table
so the two cannot drift apart, and key on meaning-bearing words rather
than on layout, so reflowing a paragraph does not fire it.

One companion, found in the same pass: a structural check run against
the verifier's **own** output is arithmetic restated against itself. Run
consistency checks against the oracle, where they can fail.

## Mutate the thing under test before believing the test

Three tests written in one day contained a copy of the code they tested —
two of them *after* the same shape had been found, fixed and written up.
One's docstring read "drive the real grounding code" above a body that
constructed the expected output by hand.

The mechanism is worth naming because intention does not fix it. When a
test needs a fixture that is awkward to build, hand-constructing the
output is the path of least resistance, and the result reads exactly like
a real test. Nothing in review distinguishes them; the docstring will
even assert the thing that is not true.

So the check is mechanical, not attentional. **Break the behaviour and
confirm the test fails.** Strip the fields, delete the guard clause,
return a constant — then run. A test that stays green was testing its own
fixture.

Two riders, both learned the hard way:

- **Confirm the mutation landed.** A substitution that matches nothing
  exits zero, and the honest-looking conclusion is that a correct test is
  inadequate — exactly backwards.
- **Mutate in the direction of the defect you fear**, not an arbitrary
  one. Deleting a whole function fails everything and proves little;
  removing the single field a gate reads is the question you actually
  have.

## Two numbers that should agree and don't

The cheapest defect detector available, and it needs no audit. Find a
quantity the system reports twice by different routes, and compare them.
Three of one day's findings came from nothing else:

- the event log said 44 messages a workday; the five-day window said 46
  in total. **A window filter comparing sim-seconds to an ISO date.**
- the record declared 15 documents; the file room held 13. **Two
  documents written to one path, the second overwriting the first.**
- the corpus mentioned decks thirteen times; it contained none. **The
  occasion reached conversation and never reached the authoring turn.**

Each disagreement is free to notice and points at a specific mechanism.
None would have been caught by re-running the thing that produced either
number, which is the usual response to a figure that looks odd.

Build the pairs in deliberately: a count of what was *attempted* beside
what was *recorded*, of what is *declared* beside what is *on disk*, of
what is *discussed* beside what is *produced*. A system that can only
report one of each pair cannot tell you it is losing anything.

## Keep the failure-mode list where you will read it before reviewing

The cheapest defect I found in a day of finding defects cost one
sentence. Writing an audit prompt meant enumerating the failure modes to
look for — and one of them, *"does the test drive the real code or a copy
of it"*, answered itself about a test I had written an hour earlier. The
audit had not started yet.

That test defined a local helper reimplementing the rule and asserted
against it, so the real code could have stopped enforcing entirely with
every assertion still green. The same shape had been caught and fixed and
written up **that morning**, in a different file.

So the mechanism worth keeping is not the audit; it is the *list*. Read
the failure modes before reviewing your own work, in the order they cost
you:

- Does this test drive the real code, or a copy of it?
- Does this check pass for the reason it claims, or for another one?
- Is the fixture the case the name describes?
- Does the guard trust a number something upstream computed?
- If I broke the thing right now, would this fail — and did my break land?
- Is the fix aimed at the demonstrated case, or at the mechanism?

An audit is how you find what the list does not cover yet. The list is
how you stop paying for the same discovery twice.

## Audit your own gates the way you audit a model's answer

A gate is code, written under the same pressure as the thing it guards,
and it is not covered by the suite it belongs to — a check that cannot
fail passes every run. An adversarial pass over one day's freshly written
measurement tooling, with every finding required to reproduce by
execution, returned **24 confirmed defects in five modules**. The
instructive part is what kind they were.

**Gates that read clean on the world they exist to reject.** One
computed a loss rate by parsing the referee's rejection notes — and the
worst case took a different branch that wrote no matching sentence, so a
world that lost *everything* measured 0.0% and passed. The bias was
one-directional: the worse the gap, the more of it disappeared, which
makes the "known-bad" number the threshold was calibrated against a
floor rather than a measurement.

**Contracts carried in prose across files that import nothing from each
other.** The same sentence was written in the referee, parsed in the
gate, and transcribed into the test as "verbatim". Rewording it zeroed
the rate with the suite green. Numbers that cross a module boundary
should cross it as *fields*.

**Fixes that work for the common case.** A truncation dropped shared
codes for everyone; reserving them fixed juniors and still failed
partners, because the reservation happened after the person's own
matters. A fix that works for the common case reads as working.

**Tests that assert on source text.** Two greps for a type name passed
with every guard clause deleted, because the names survive in the import
line. Assert on types and behaviour; a grep cannot tell you the name is
still doing anything.

**Vacuous passes at the top level.** A build with no tasks ran every
world-level check, skipped every per-task gate, and exited 0 — an audit
that iterates an empty set, which is the shape the gates below it exist
to catch.

Two practical rules fall out. Require each finding to be **reproduced by
execution**, and instruct the verifier to default to refuted without one:
a good audit refutes some of its own claims with real data. And prefer
**mutation** over inspection — break the thing and confirm the test
fails, having first confirmed the break landed.

## Promote on the third instance

**When a defect class appears a third time, stop fixing instances.**
Promote it to a suite-wide gate, and add a companion test that fails when
a new task joins the suite without being covered.

**Write the cost into the gate.** Each gate's docstring should carry the
measured numbers of the defect it prevents. A gate that only says what it
checks gets weakened by the next maintainer who finds it inconvenient; a
gate that says *"this cost 30 rows and a wrong verdict about a model"*
does not.

**Stub a grading framework faithfully, not permissively.** A stub that
accepts what the real runtime would reject turns every guard built on it
into decoration. Reproduce name resolution, argument binding and
description formatting, and share one registry with the real path.
