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
