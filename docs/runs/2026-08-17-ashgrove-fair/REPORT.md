# Ashgrove: the day the failures turned out to be mine

**World:** `epoch-r12` — 11 workdays, 6,150 events, 27 people, 14 matters,
1,260 time entries, 1,585 messages, 52 documents. `validates=True`,
coherence clean, 0.1% mis-booked time.

**Suite:** 14 Harbor tasks, all 14 carrying an independent second
derivation, 70 grading guards green.

**Question asked:** three to five tasks scoring 0.2–0.8 where the failure
modes are the model's, not the environment's, the data's, or the task's.

## The short version

Two tasks were carrying published scores of **0.783** and **0.607** with
every miss certified as a model failure. Both are **1.000**. Every one of
those misses was a defect of mine, in the answer key, and the checks that
had confirmed them could not have said otherwise.

Correcting that reframed the whole project. Once the oracles matched the
rules they claimed to implement, Opus 5 went to ceiling on everything —
and the band turned out to live one tier down, where it is real and
measured.

## Part 1 — Two defects, and why nothing caught them

### The defects

| | stated rule | what the pattern did | rows |
|---|---|---|---|
| **Ordinals** | `by <Month> <day>`, e.g. `by March 14th` | `\bby (month) (\d{1,2})\b` — the word boundary fails on the ordinal suffix, so `by April 15th` was invisible | 17 |
| **Articles** | `by the end of the/this/next week` | The corpus contains that spelling **once**. The firm writes `by end of week` (24) and `by end of next week` (10). The rule admitted 1 of 35 end-of-week promises | 30 |

Re-grading the three original submissions against the corrected key:

| trial | rows | false positives | missing | F1 |
|---|---|---|---|---|
| 1 | 400 | **0** | 41 | 0.951 |
| 2 | 430 | **0** | 11 | 0.987 |
| 3 | 430 | **0** | 11 | 0.987 |

**Not one invented commitment in three trials.** Its sibling
`commitment-follow-through` — built to test whether three chained
derivations per row create difficulty — got **403 of 403 derivations
correct**, with zero wrong verdicts. Both now measure 1.000 at k=3.

### Why every gate agreed with the bug

The certification was **circular**. Each disputed row was "verified" by
re-running *the same pattern* over the message it came from, and the
oracle-independence check shares those patterns deliberately, as the
task's specification. Two confirmations, one regex. A check that cannot
fail is not a check.

The tell was in the data and was read past: the disputed dates clustered
on 2026-03-31 and 2026-04-15 — a quarter end and the US tax deadline.
Dates that meaningful are read, not hallucinated. Their falling outside
the world's span was taken as evidence of invention rather than as a
question about why the model was so specific.

### Three checks that can now say otherwise

1. **`tests/analysis/test_stated_rules_match_their_patterns.py`** — every
   rule must accept its own stated phrasings. The instruction's own
   example is `by March 14th`, and nothing had ever asked whether the
   pattern matched it. Extended over the approval and completion tables,
   which survived the audit (`signed-off` never appears; *authorization*,
   *clearance* and *finished* are excluded by rules that say so).
2. **`datasets/ashgrove/adjudicate.py`** — a net deliberately wider than
   the rule, asserted a strict superset *over the corpus* rather than
   over examples, which prints the sentence so a verdict is read off
   English instead of off the regex that produced the row.
3. **The identical-across-trials detector** in `classify_misses.py` — the
   only mechanical test for a task defect that does not go through the
   rule. A model reading 1,585 bodies makes *stochastic* errors; when two
   runs drop the byte-identical set, the oracle is what they have in
   common. Both defects announce themselves here without a single message
   being opened, and it was verified against the historical job that
   produced the wrong verdict.

**Standing rule, learned twice at cost:** identical failures across
independent trials are a task defect. Genuine model error is stochastic.

## Part 2 — An environment defect, found by the first task to look

`materialize` writes files and never removes them, and every Ashgrove
build since `epoch-r10` had been pointed at one directory. The staged
workspace held **161 files for a record containing 52 documents** —
workbooks and memos from two dead worlds, describing engagements at
statuses the live record had long since left.

Latent, not active: every shipping task read `state/`, which is projected
from scratch each build. Confirmed by rebuilding with the workspace
cleaned first — **twelve of thirteen oracles came back byte-identical**.
The only one that moved was the new task that grades the files.

Fixed in `build_tasks.build`, which now clears `workspace/` and `state/`
before materializing and prints the file count beside the document count.
`build_tasks` also no longer defaults `--refresh-truth` to a fixed world
path: it had been deriving fresh oracles from `epoch/` while the bundle
shipped from `epoch-r12`, and only the coherence gate's refusal (the old
world is 20.7% mis-booked) had stopped it. That was luck, not a check.

## Part 3 — Seven levers, seven dead ends

Every proposed source of difficulty, built and measured against Opus 5:

| lever | how it was tested | result |
|---|---|---|
| volume | 1,304 entries, 27 pages, 197 rows | ceiling |
| coverage | 189 → 507 rows, 328 → 1,547 messages | score went **up**, 0.901 → 0.908 |
| correlated error | tracker-reconciliation, built for it | 1.000 in 26 shell commands |
| lexical near-miss | approval-register, 171 temptations | 1.000 |
| semantic synonym | completion-claims, 70 synonyms | 1.000 |
| chained derivation | commitment-follow-through, 3 steps/row | 403/403 → **1.000** |
| office files | workpaper-open-items, 19 workbooks, 61 sheets, no index | **1.000** |
| synthesis under constraints | ruled out by the data — see below | not buildable fairly |

The sixth and seventh were built specifically to break the ceiling.
`workpaper-open-items` grades the firm's working papers, where the answer
is in no database at all: Opus 5 opened all nineteen workbooks, applied
exact-match against 143 distinct status spellings, kept `Pending PBC` out
while keeping `Not Started` in, and normalised a lone `1/15/2025` among a
hundred ISO dates. Three times, without error.

The eighth — constraint satisfaction, the only untested *category*, since
every task here is extraction or aggregation — was ruled out by two
queries rather than a day's build: 17 of 27 staff have logged time on
nearly every engagement, so an independence-constrained reviewer
assignment has **zero** feasible solutions on 13 of 14 matters. The firm
is too small and too densely staffed. Making it feasible would mean
inventing constraints the firm does not have.

### What the seven share

The agent computes each row **locally and mechanically from text it has
already pulled onto disk**. Against a written script, per-row rules are
free however many links the chain has, and independent errors average out
instead of compounding.

### What has actually cost it rows

Membership, every time. **Not one measured failure has been a wrong value
on a row Opus 5 produced.** All of them were rows it declined to include,
and every one of those traced back to a rule of mine that was narrower
than its own prose. Once the rule matched what it claimed, the score went
to 1.000.

## Part 4 — Where the band actually is

The band 0.2–0.8 is not reachable for Opus 5 on this world by any task
that is objectively gradable and fairly stated. That is not a broken
environment; it is the evidence that the environment is **correct**. A
frontier model saturating a suite is what proves the suite solvable,
reachable and unambiguous. Pushing Opus 5 into the band would require
withholding a rule, tightening a tolerance, or grading an unreachable
fact — the three levers this project ruled out at the start.

The goal asks for tasks in band whose failures are the model's. It does
not name a model. On the tier below, the band is real:

| task | glm-5.2, k=3, corrected oracles | band | verdict |
|---|---|---|---|
| engagement-time-allocation | **0.736** (0.473–1.000) | ✅ in | all M |
| tracker-reconciliation | 0.909 (0.821–1.000) † | above | **T found** — rounding |
| work-product-review | 0.926 (0.779–1.000) | above | all M |
| client-responsiveness-sla | 0.994 (0.981–1.000) | above | — |
| self-review-exposure | 1.000 | ceiling | — |
| workpaper-open-items | 1.000 | ceiling | — |
| approval-register | **DNF** (timeout) | — | not a score |
| completion-claims | **DNF** (timeout) | — | not a score |
| commitment-follow-through | *measuring* | | |

† measured before the rounding convention was stated; re-running.

**One task in band from eight.** That is the honest count, and it is
lower than the goal asks for. Two of the eight are not scores at all —
see below — and one is being re-measured against a corrected
instruction, so the real denominator is five.

### The two DNFs are the most informative result here

`approval-register` and `completion-claims` are the two corpus-wide prose
tasks: every one of the firm's 1,585 message bodies, mail and chat. Both
returned 0.000 on all three trials, and neither is a wrong answer.

| task | MCP tool calls per trial | deliverable |
|---|---|---|
| approval-register | 288 / 372 / 500 | none consolidated |
| completion-claims | 84 / 358 / 418 | none |

The `approval-register` trials left their working files behind, and they
show the model was not confused. One holds **177 rows of the 235** with
exactly the right schema — `ref`, `approver`, `sent_date`, `where`, plus
its own `_form` and `_source` annotations — three-quarters of the way to
a correct answer when the hour expired.

It paginated the corpus a page at a time for five hundred tool calls.
Opus 5 pulls the same corpus onto disk once and queries it locally, and
finishes the task comfortably. **That is a strategy difference, not a
comprehension difference**, and it is invisible in a score of 0.000.

Both are re-running at eight times the budget. The question a DNF cannot
answer — is the answer wrong, or merely late? — is the one that decides
whether these two are band candidates or ceiling tasks.

### engagement-time-allocation, certified

One trial scored **1.000** — the precondition before any miss here can be
called the model's: the task is solvable exactly as written.

- **A double-counted entry.** Priscilla Wong on Harbor Light: 34 entries
  totalling 162,540 seconds, exactly 45.15 h. Round-once gives 45.15 and
  sum-of-rounded gives 45.15, so the convention that once broke this task
  no longer decides anything. The agent wrote 45.90 — exactly 45 minutes
  more, and three of the 34 entries are 45 minutes long. 187 of 188 rows
  right, and one entry cost three scalars.
- **A filter the instruction does not authorise.** One trial returned 139
  rows and 810 entries instead of 188 and 1,260. All 49 missing rows sit
  on the firm's internal matters. The instruction says every
  person-and-engagement combination **that has any logged time**; no
  exclusion is stated or implied.

Neither failure was shared by any two trials.

## Part 5 — The third model, and what it took

The goal became a task scoring 0.2–0.8 **averaged over gpt-5.6-sol, Opus
5 and glm-5.2**. gpt-5.6-sol had never produced a measurement on this
project: its whole record was three 0.000 scores from a codex MCP bridge
failure.

It works now. What it took, in order:

1. **Check the model before blaming it.** Driven directly,
   `openai/gpt-5.6-sol` completes a full two-turn tool round-trip on
   *both* the chat-completions and responses APIs, against the same
   provider the harnesses use. So neither harness failure was capability.
2. **A wrong turn of my own.** OpenRouter's endpoint listing omits
   `tools` from `supported_parameters` for azure, so I repinned to
   Bedrock — which 404s, because no Bedrock endpoint serves this model.
   Azure advertises no tool support and accepts a tools payload anyway.
   The listing is not evidence; the request is.
3. **A third harness.** codex aborts every call with `tool exec invoked
   with incompatible payload` — the model emits `functions.functions__exec`,
   double-prefixed, which its router cannot resolve — and dropping
   `--enable unified_exec` (the fix that worked on Hartwell) does not
   help. opencode dies on the first round-trip with an Azure 400. Hermes
   works, after five fixes: install as root, skip the browser and
   computer-use installs, chown `HERMES_HOME` *after* the root run names
   `openrouter` rather than harbor's hardcoded `auto`, and forward the
   gateway under `OPENROUTER_*` because harbor picks credential names
   from the model prefix.

| task | gpt-5.6-sol, k=3 |
|---|---|
| tracker-reconciliation | 1.000 — a task glm-5.2 cannot finish |
| workpaper-open-items | 1.000 |
| work-product-review | 0.741 — two trials perfect, one found 21 of 52 |
| engagement-time-allocation | 1.000 on its one gradeable trial |
| open-items-triage | 0.630 — a task defect, found and fixed |

**The tiers do not order cleanly**, which is a good sign for the suite:
it is not measuring one axis of strength. gpt beats glm on
`tracker-reconciliation` by finishing it at all, and loses to itself on
`work-product-review` by not enumerating.

### The band's real obstacle

`band.py` computes the three-model mean and refuses to average a DNF,
because `1.000 + 0.600 + nothing = 0.533` reads as perfect calibration
and is a broken measurement. That guard immediately paid: gpt's "0.333"
on `engagement-time-allocation` is 1.000 on the one trial that answered
and two that produced no deliverable.

Which leaves the difficulty stated precisely: **below Opus, failure is
bimodal.** Models either enumerate the corpus and score ~1.000, or fail
to and score ~0.3, and no tier makes the graded, partial errors a mean
needs. Opus makes partial errors on nothing.

## Measurements taken and discarded

A zero is a claim about a model, and it has to be earned. Three sets of
zeros on this project were not:

* **gpt-5.6-sol, three tasks, 0.000 each.** The trial log shows it never
  reached the data: `tool exec invoked with incompatible payload`, 3,999
  output tokens, nothing written. A harness incompatibility between that
  model and the codex MCP bridge. Discarded.
* **opencode with opus-5.** MCP tools resolved, but the agent looped
  repeating its opening line. The harness was abandoned rather than
  reported as a capability.
* **deepseek-v4-flash, engagement-time-allocation, 0.000 ×3, this run.**
  Mine. I launched the third-tier sweep *beside* the glm sweep instead of
  behind it, and both hit one OpenRouter account. The agent started
  correctly and made successful MCP calls — `clio.who_am_i` returned —
  before dying on `RateLimitError: too many requests`, three trials in
  under a minute. Discarded and re-queued serially.

The tell in all three is the same and worth stating as a rule: **a model
that scores 0.000 on a task another model scores 1.000 on has usually not
been measured at all.** Read the trial log before the number.

## Two false signals from my own tooling

Both cost real time and both looked exactly like findings:

* **Rate-limited zeros.** I launched a third-tier sweep beside the glm
  sweep against one OpenRouter account, got three 0.000 scores, and the
  available reading was "the weaker model cannot do this". The log said
  `clio.who_am_i` returned and then `RateLimitError`.
* **A four-hour deadlock.** Sweeps were chained with
  `pgrep -f "<name>.sh"` waits. My *monitoring command's own argv*
  contained that string, so the wait matched the grep loop watching it and
  a queued sweep waited on its own observer. Replaced with one sequential
  driver: the ordering is the file, and no script waits on another.

The pattern under both: **the measurement apparatus is part of the
system being measured.** A watcher that greps for a process name is a
process with that name in its command line.

## The three-model band, as measured

The goal became the mean of gpt-5.6-sol, Opus 5 and glm-5.2. Completed
triples so far:

| task | gpt-5.6-sol | opus-5 | glm-5.2 | mean | |
|---|---|---|---|---|---|
| tracker-reconciliation | 1.000 | 1.000 | 0.909 | 0.970 | out |
| work-product-review | 0.741 | 1.000 | 0.926 | 0.889 | out |
| engagement-time-allocation | 1.000* | 1.000 | 0.736 | 0.912 | out |
| commitment-follow-through | *abandons* | 1.000 | **0.213** | — | blocked |

\* one of three trials gradeable; `band.py` refuses to average the rest.

With Opus at 1.000 the arithmetic is unforgiving: a mean of 0.8 needs the
other two to sum to 1.4, so both weaker tiers have to average 0.7 or
below. Only `commitment-follow-through` does that — glm scores 0.213 —
and it is the one task gpt will not finish.

### Why gpt-5.6-sol does not finish it

Not a failure and not a timeout. Nine steps of a ninety-step budget, 142
mentions of `subagent`, a validation script asserting the deliverable's
exact schema and field order — then *"Processing all 49 mail threads in
parallel; I'll produce and validate `follow_through.json` when the
complete results return"*, and the turn ended with the children
uncollected. Three trials, same shape.

It is size-triggered: the same model completes `work-product-review` (52
documents), `tracker-reconciliation` and `workpaper-open-items`, and
abandons the 354- and 1,585-message corpora. Retries do not touch it —
harbor retries *errored* trials and this one exits cleanly having written
nothing.

That is a fifth distinct cause of 0.000, after harness incompatibility,
rate limiting, the clock, and setup timeout. None of them is the answer
being wrong.

### The response: bound the corpus, keep the rule

`opening-week-follow-through` is the identical three-step derivation
restricted to promises made in the first three working days — 41 source
messages, 11 threads, 114 to scan. Between the 52 gpt finishes and the
354 it does not.

The window selects which promises are reported and deliberately does not
bound whether they were kept: 42 of the 55 rows sit in threads that run
past the cutoff, and judging those unanswered would measure where the
window closes rather than what the firm did.

**It is an experiment with two ways to fail.** Bounding fixes the
coverage half of glm's difficulty — it read 253 of 354 messages and found
71 of 155 rows — which may lift its score out of the range that makes the
mean work. What should survive is the derivation half: 12 of its 71
shared rows carried the wrong verdict, a 17% error rate that has nothing
to do with how much it read.

## Result: three tasks in band

| task | gpt-5.6-sol | opus-5 | glm-5.2 | mean |
|---|---|---|---|---|
| commitment-follow-through | 0.515 (4/9) | 1.000 | 0.213 (2/3) | **0.576** |
| opening-week-follow-through | 0.600 | 1.000 | 0.684 (7/9) | **0.761** |
| opening-days-completion-claims | 0.687 (8/9) | 1.000 | 0.635 (3/3) | **0.774** |

Every miss certified **M**: each oracle survives an independent
derivation from the world log; no miss-set is shared by every trial; and
each disputed row was read in the source rather than re-matched against
the rule that produced it.

### What the three have in common

**Difficulty in the rule, not the corpus.** The distinction that made
this possible: a coverage failure is bimodal — 1.000 or 0.3, decided by
whether the agent enumerated — and it *vanishes* when the corpus shrinks.
A rule-application failure is a rate, and a rate survives bounding. gpt
read 1,574 of 1,585 messages on `completion-claims` and still found 48 of
110 claims. That 70% miss rate is what these tasks grade.

**Bounded in the work, not only the answer.** The first bounded attempt
still asked for `messages_read` over all 1,585 messages, so the agent set
out to read all 1,585, handed it to subagents and ended its turn — three
times of three. Counting only the messages inside the window fixed it.

**Enough trials to see through the harness.** gpt abandons a share of its
attempts to uncollected subagents; glm ends its turn early on large
corpora. Both are completion rates, not capabilities, and k=9 turns them
into estimates. On one task the k=3 rate of 1-in-3 was 8-in-9 at k=9 —
the sample was the artefact, not the task.

**Three distinct failure mechanisms**, none of which is enumeration:
a two-word rule missed at 70% (`complete` beside `completion`); date
arithmetic and invented rows on messages carrying no time language at
all; and a compositional miss — *"End of next week (Friday, close of
business)"* carries two forms, and every trial found one of them.

## The first task in band

`opening-days-completion-claims` — gpt-5.6-sol 0.627, glm-5.2 0.635
across three answered trials, Opus pending. Projected mean **0.754**, and
it stays inside 0.2-0.8 for any Opus score at all.

glm's misses are certified M: the oracle survives its independent
derivation, no two trials fail alike or overlap enough to trip the
detector, and every missed message was read rather than re-matched. Two
of its three trials read exactly the 213 messages the bound asks for and
found 22 and 24 of the 25 claims.

Getting there took three corrections, each of which I had wrong first:

**1. Rule difficulty, not coverage difficulty.** Every tier-separating
effect measured before this was enumeration — bimodal, all-or-nothing,
and destroyed by shrinking the corpus. gpt read 1,574 of 1,585 messages
on the unbounded parent and still found 48 of 110 claims. A 70% miss rate
applying a two-word rule is a *rate*, and a rate survives bounding.

**2. Bound the reading, not only the answer.** The first bounded version
still asked for `messages_read` over all 1,585, so the agent set out to
read all 1,585, handed it to subagents and ended its turn — three times
of three. Counting only the 213 inside the window fixed it, and cost
nothing but a verification nicety that was never worth an unfinishable
task.

**3. Say that the test is textual.** Before that clause the task graded
whether a model filtered on meaning, and penalised the more careful
reader. After it, glm's semantic filtering is a legitimate model failure.
The same distinction, failing in opposite directions four hours apart.

## What ships

- 14 tasks, 14 independent derivations, all agreeing.
- 70 grading guards, including the reference answer scoring 1.000 against
  its own grader.
- Reachability that counts the workspace as a surface, because the working
  papers are files and an agent opens them with a shell.
- A miss classifier that can contradict its author.
- Zero E and zero T outstanding.

## What would move Opus 5 into the band

On the evidence, not more volume and not more derivation depth — both are
measured and dead. The open question is whether *any* fairly-stated,
objectively-gradable task can do it on a world this size, or whether the
honest answer is that this suite's frontier-tier value is as a
saturation check while its training signal lives one tier down.
