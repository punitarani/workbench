# Why each criterion missed — the E/T/M ledger

Every score below 1.0 is a defect until proved otherwise. **E** is an
environment defect (the fact is not served, or the record contradicts
itself with no stated rule), **T** is a task defect (ambiguous
instruction, wrong oracle, wrong grader, unfair tolerance), and **M** is a
model failure — reachable, unambiguous, oracle independently confirmed,
and the agent got it wrong anyway. Only **M** may ship.

World: `epoch-r12`, 11 workdays, 6,150 events, `validates=True`, coherence
clean, 0.1% mis-booked time. Model: Opus 5 through codex.

## The correction that reframes everything below

`commitment-register` was published at **0.783 with all 42 misses
certified as model failures**. It is **1.000**. Every one of those 42 was
mine.

Two defects, found in sequence:

1. **Ordinals.** The stated form is `by <Month> <day>`; the pattern was
   `\bby (month) (\d{1,2})\b`, whose word boundary drops `by April
   15th`. 17 rows.
2. **Articles.** The stated form was `by the end of the/this/next week`.
   The corpus contains that spelling **once**; the firm writes `by end of
   week` (24) and `by end of next week` (10). The rule admitted 1 of 35
   end-of-week promises and scored the other 34 as hallucinations. 30
   rows, in two trials, identically.

Re-grading the three original submissions against the corrected key:

| trial | rows | false positives | missing | F1 |
|---|---|---|---|---|
| 1 | 400 | **0** | 41 | 0.951 |
| 2 | 430 | **0** | 11 | 0.987 |
| 3 | 430 | **0** | 11 | 0.987 |

**Not one invented commitment in three trials.** `commitment-follow-through`
is the same story and worse for the hypothesis it was built to test: three
chained derivations per row, **403 of 403 correct**, zero wrong verdicts,
every loss a membership gap from the same two pattern defects.

### Why nothing caught it

The certification was circular. Each of the 42 was "verified" by
re-running *the same pattern* over the message it came from, and the
independence check shares those patterns deliberately, as the task's
specification. Two confirmations, one regex. A check that cannot fail is
not a check.

The tell was in the data and was read past: the disputed dates were
2026-03-31 and 2026-04-15 — a quarter end and the US tax deadline. Dates
that meaningful are read, not hallucinated.

Two gates now exist that could have said otherwise, and neither shares the
solver's patterns:

* `tests/analysis/test_stated_rules_match_their_patterns.py` — every rule
  must accept its own stated phrasings. The instruction's own example is
  `by March 14th`, and nothing had ever asked whether the pattern matched
  it. Extended to the approval and completion tables, which survived it.
* `datasets/ashgrove/adjudicate.py` — a net deliberately wider than the
  seven forms, asserted a strict superset over the corpus, which prints
  the sentence so a verdict is read off English.

**Standing rule, learned twice at cost:** identical failures across
independent trials are a task defect. Genuine model error is stochastic.

## The three re-measured tasks — all 1.000 (k=3, corrected oracles)

| task | rows | was published as | measured, corrected |
|---|---|---|---|
| commitment-register | 441 | 0.783, "all misses M" | **1.000** |
| commitment-follow-through | 155 | 0.607 | **1.000** |
| workpaper-open-items | 55 | *(new)* | **1.000** |

Every trial perfect, every criterion. Both band candidates are withdrawn:
neither was ever a measurement of the model.

`workpaper-open-items` is the sixth lever built specifically to break the
ceiling and the sixth to fail. It grades nineteen rendered workbooks and
sixty-one sheets with nothing in SQL and no index — and Opus 5 opened all
of them, applied exact-match against 143 distinct status spellings,
kept `Pending PBC` out while keeping `Not Started` in, and normalised a
lone `1/15/2025` among a hundred ISO dates. Three times, without error.

## The band, on glm-5.2, corrected oracles, k=3

### engagement-time-allocation — 0.736 (0.473–1.000) — IN BAND — all misses M

188 person-and-engagement rows over 1,260 time entries. One trial scored
**1.000**, which is the first thing that has to be true before any miss
here can be called the model's: the task is solvable exactly as written.

Two failure modes, neither shared by any two trials:

**Double-counted entry.** Priscilla Wong on Harbor Light: 34 entries
totalling 162,540 seconds — exactly 45.15 h. Round-once gives 45.15 and
sum-of-rounded gives 45.15, so the convention this task was once broken
by no longer decides anything. The agent wrote 45.90, exactly 45 minutes
more, and three of the 34 entries are 45 minutes long. It counted one
twice, and that single row moved `total_hours`, `total_billable_hours`
and `total_fees` off exact match — 187 of 188 rows right and three
scalars lost to one entry. **M.**

**A filter the instruction does not authorise.** One trial returned 139
rows instead of 188 and 810 entries instead of 1,260. Every one of the 49
missing rows sits on `00011-shaw`, `00012-calder` or `00013-mendes` — the
firm's four internal matters (peer-review prep, methodology refresh, two
location setups). The agent decided internal work is not an engagement.
The instruction says `allocations` carries "one entry per
person-and-engagement combination **that has any logged time**" and
`pairs` counts "how many person-and-engagement combinations logged any
time". No exclusion is stated and none is implied. **M.**

Checks that could have said otherwise and did not: the oracle agrees with
its independent derivation; every value is served; and the two trials
that failed did not fail alike.

### work-product-review — 0.926 (0.779–1.000) — above band — all misses M

Two of three trials scored 1.000. The third had all 52 rows, invented
nothing, and got `reached_client` wrong on two of them.

Both are served and both are true. `doc-000024` is attached to
`msg-000162`, which carries Garrett Poole, external. `doc-000005` is
attached to three messages — `msg-000122` carries Idris Mensah, external;
the other two are internal-only. That second one is the interesting
error: the answer is an OR across every attachment of a document, and an
agent that checks one send and stops gets False for a document that did
reach a client. **M**, and a good failure — it is the kind a real
reviewer makes.

Above the band on the mean, so not a candidate. Kept because a task that
lands 0.926 with two perfect trials is evidence the suite is fair, not
evidence it is easy.

### commitment-follow-through — 0.142 (0.000–0.308) — below band — all misses M

Three trials, three shapes, and none of them shared:

| trial | score | wrote `follow_through.json`? |
|---|---|---|
| 7iEkxvG | 0.308 | yes, beside 3 working files |
| a5zTFwx | 0.118 | yes, beside 7 working files |
| afUktz6 | 0.000 | **no** — only its scratch files |

The best trial read 253 of 354 messages and found 71 of 155 commitments,
with 91 missing and 7 invented. Two of the invented are the clearest M in
the whole run: `msg-000108b` is not a message id in this record at all —
the agent suffixed a real one — and no reachability question arises,
because the thing it named does not exist.

**The rows it missed close this morning's loop.** `msg-000044` carries
*"Surety deadline: audited statements by April 15th"* and *"records ready
by March 31st"*, and both rows are missing from glm-5.2's answer. Those
are the same two dates — quarter end and the US tax deadline — that the
broken oracle counted *against* Opus 5 as hallucinations. Corrected, they
are now doing exactly the work they should: Opus 5 finds them, this tier
does not.

A defect that penalises the strong model and a real discriminator look
identical in a score column. They diverge only on which way the error
points.

## opening-days-completion-claims — 0.774 — IN BAND — all misses M

**Final:** gpt-5.6-sol 0.687 over 8 answered trials of 9 (0.573–0.865),
Opus 5 1.000, glm-5.2 0.635 over 3 of 3. **Mean 0.774.**

The cleanest certification in the suite: the oracle survives its
independent derivation, and across eight gpt trials **no row is dropped
by every trial and the typical pair of miss-sets overlaps 0%** — on both
the missing rows and the invented ones. Errors that scattered are model
noise with no systematic cause available to explain them.

Worth noting against the earlier k=3 run on the same task, which answered
1 of 3 and read 0.627: the abandonment was luck, not a property of the
task. Nine trials put it at 8 of 9. A completion rate estimated from
three attempts is not an estimate.

### The earlier account of this task, kept for the record

| tier | score | trials answered |
|---|---|---|
| gpt-5.6-sol | 0.627 | 1 of 3 |
| glm-5.2 | **0.635** (0.573–0.684) | 3 of 3 |
| opus-5 | *pending* | |

Projected mean with Opus at 1.000: **0.754 — in band**, and it stays in
band for any Opus score at all.

**glm's misses are M.** Oracle independently confirmed; no two trials
fail alike and their overlap is below the 50% the detector flags; and
each missed message was read rather than re-matched. Two of its three
trials read exactly 213 messages — the bound — and found 22 and 24 of
the 25 claims.

The rows it dropped are the semantically awkward ones: *"Once I've
completed the analysis"*, *"Once that call is complete"*, *"once we have
completed our review"*. Every one is conditional or refers to something
other than delivered work, and every one contains the word. The
instruction says outright that the test is textual and not editorial, so
these count, and filtering them on meaning is the model's error — the
same error, made the other way round, that made this task's *own*
instruction defective an hour earlier.

**What made it work**, after three attempts that did not:

1. **Rule difficulty, not coverage difficulty.** gpt read 1,574 of 1,585
   messages on the unbounded parent and still found 48 of 110 claims. A
   70% miss rate applying a two-word rule is a *rate*, and a rate
   survives bounding where a coverage failure does not.
2. **Bound the reading, not only the answer.** The first bounded version
   still demanded `messages_read` over all 1,585, so the agent set out to
   read all 1,585, delegated it, and ended its turn 3 times out of 3.
   Counting only the 213 in the window fixed that.
3. **State that the test is textual.** Without it the task graded whether
   a model filtered on meaning, which is not a skill anyone should be
   trained to lose.

## commitment-follow-through — 0.576 — IN BAND — all misses M

| tier | score | answered |
|---|---|---|
| gpt-5.6-sol | 0.515 (0.414–0.655) | 4 of 9 |
| opus-5 | 1.000 | 3 of 3 |
| glm-5.2 | 0.213 | 2 of 3 |

**Mean 0.576.** The first task to clear `band.py`'s own rules, and it is
the *unbounded* task — no corpus trimming, just k=9 to see through
gpt's one-in-three abandonment rate.

gpt's misses certified M on every check:

* the oracle survives its independent derivation;
* **no row is dropped by every trial** — recall runs 136–145 of 155 and
  the typical pair of miss-sets overlaps 12%, which is scattered;
* the inventions are wrong date arithmetic on real rows (60 of 87 in the
  worst trial) plus 27 rows on messages that carry **no time-shaped
  sentence at all**, under a net deliberately wider than the rule.

### The detector needed three fixes to say that honestly

Each would have produced a false verdict, and each was found by checking
its answer against a hand computation rather than trusting it:

1. **It reported the worst pairwise overlap.** With four trials there are
   six pairs; it flagged 64% while five of the six sat between 4% and
   12%. It now reports rows dropped by *every* trial, which is what a
   rule the instruction fails to settle actually looks like.
2. **It read scratch files as answers.** `_submitted` falls back to any
   dict-shaped JSON so a reader can see what a failed trial was doing —
   right for the per-trial dump, wrong here, where five abandoned trials
   fed their working notes into the comparison.
3. **It excluded trials that had no failures.** `if row[index]` dropped
   the empty sets, so "dropped by every trial" meant "every trial that
   had any" — and the trial which invented *nothing*, the strongest
   evidence against a systematic defect, was the one being filtered out.

## open-items-triage — 1.000 / 1.000 / 1.000 — what ambiguity looks like

It scored 0.630 for gpt-5.6-sol and 0.630 for glm-5.2 before its
instruction was fixed, and both models missed the *same* thread every
time. That reads like a discriminating task and was nothing of the kind:
the rule admits any last client message containing one of twelve
phrases, and `thr-000022` ends with *"I want to confirm we're aligned on
what we need to deliver"* — which contains `we need` while asking the
firm for nothing.

With the instruction saying outright that the phrase test is textual,
all three tiers score 1.000.

**The lesson is the contrast.** A task made hard by an ambiguity and a
task made hard by its rule look identical in a score column: both sit
below ceiling, both discriminate between models. They separate on one
question — do the trials fail the *same way*? Ambiguity is deterministic
because every careful reader resolves it identically; real difficulty is
scattered. That is the whole basis of the identical-across-trials check,
and this task is the clean example of the first kind.

## opening-week-follow-through — 0.761 — IN BAND

gpt-5.6-sol 0.600, Opus 5 1.000, glm-5.2 0.684 over 7 answered trials of
9. **Mean 0.761.**

Opus scored 0.773 twice here before the hedged-form clause and 1.000
after it, which is the defect confirming itself: both trials had dropped
the identical pair of "within a day or two" rows.

glm's misses are M. The two rows its trials share are found by other
trials (3 of 8 and 2 of 8), so nothing is systematically blocked, and the
mechanism is compositional rather than arithmetic: `msg-000082` reads
*"Investor deadline: End of next week (Friday, close of business)"* and
carries **two** forms — `close of business` for the sent date and `end of
next week` for that Friday. Every trial found the first. Two found the
second. Reading the parenthetical as a description of one deadline rather
than as a second form is the natural mistake, and the instruction says
outright that two forms resolving to different dates make two rows.

*A defect blocks everyone; difficulty makes most people miss.* That
distinction is what separated this from the hedged-form defect, which
looked identical in the detector.

**One caveat, being re-run:** gpt's number was measured at 03:35 and the
hedged clause landed at 07:10, so it read a different instruction from
the other two tiers. The mean is in band either way — the clause moved
Opus *up* — but a task should be measured on one version of itself.

## E-class: the bundle had been accumulating three worlds

Found while building the first task graded on files rather than on a
database. `materialize` writes and never removes, and every Ashgrove
build since epoch-r10 had been pointed at one directory. The staged
workspace held **161 files for a record containing 52 documents** —
workbooks and memos from two dead worlds, describing engagements at
statuses the live record left behind.

Latent, not active: every shipping task read `state/`, which is projected
from scratch each build. Confirmed by rebuilding with the workspace
cleaned first — twelve of thirteen oracles came back byte-identical, and
the only one that moved was the new task, from 169 rows to 55.

Had it not been caught, `workpaper-open-items` would have keyed its answer
to files that no longer belonged to the world it grades. Fixed in
`build_tasks.build`, which now clears `workspace/` and `state/` before
materializing and prints the file count beside the document count.

## tracker-reconciliation — 1.000

No miss to classify. Built specifically for correlated error — one sheet,
three bridging decisions, each moving all 139 effort rows together — and
solved perfectly in 26 shell commands. Recorded in `DIFFICULTY.md` as the
measurement that closed the correlated-error hypothesis.

## work-product-review — 1.000

No miss to classify. Worth noting what changed: on the previous world this
task's key collapsed 52 documents to 49 and capped a perfect answer at
0.94. Re-keyed on iManage's served document number, the ceiling is gone and
the model reaches it.

## engagement-time-allocation — 1.000, client-responsiveness-sla — 1.000

No misses to classify. 188 rows over 1,260 time entries and 43 threads
respectively, both perfect. These are the tasks `DIFFICULTY.md` records as
proof that width does not create difficulty.

## The suite on r12, Opus 5, one trial each

| task | rows | answer |
|---|---|---|
| **commitment-register** | 388 | **0.770** |
| tracker-reconciliation | 139 + 10 | 1.000 |
| work-product-review | 52 | 1.000 |
| engagement-time-allocation | 188 | 1.000 |
| client-responsiveness-sla | 43 | 1.000 |

One task in band; four at ceiling. The one that moved is the one whose
rule a competent reader is tempted to override.

## Cross-tier: glm-5.2 on the same world

The suite separates tiers on r12, which it did not do before.

| task | Opus 5 | glm-5.2 | gap |
|---|---|---|---|
| commitment-register | **0.783** | — (timed out) | — |
| **engagement-time-allocation** | 1.000 | **0.540** | **0.460** |
| work-product-review | 1.000 | **0.778** | 0.222 |
| tracker-reconciliation | 1.000 | **0.832** | 0.168 |
| client-responsiveness-sla | 1.000 | 1.000 | 0 |

Three of the four discriminate, and all three land in band for the weaker
model.

Both gaps have the same shape, and it is worth naming: **the weaker model
finds every row and cannot total them.** `effort.f1` and `documents.f1` are
1.000 in both; what it loses are the aggregates that need a second surface.

### work-product-review, glm-5.2 — 0.778 — all misses M

```
answer.reached_client   0.000   count: agent 4, oracle 7
answer.never_attached   0.000   count: agent 47, oracle 45
answer.row_facts        0.990   52 rows, 0 missing, 0 invented
wrong fields on shared rows: {'reached_client': 3}
```

Fifty-two rows, none missing, none invented, every field right except
`reached_client` on three documents. Each was checked against the record:

| document | attached to | outside recipient |
|---|---|---|
| 19 — FY2025 Audit Calendar & Resource Plan | 4 messages | Harriet Vance ×3, Benedict Shaw |
| 24 — Audit Engagement Status Summary | msg-000162 | Garrett Poole |
| 5 — Standard Rate Sheet 2026 | msg-000122 | Idris Mensah |

All three plainly reached a client, through the mail surface, on messages
the tools serve. **Verdict M**: the model did not carry the
attachment-to-recipient join through, and both wrong counts fall out of
those same three rows.

### engagement-time-allocation, glm-5.2 — 0.540 — all misses M

```
entries_total  agent 1218, oracle 1260      pairs  agent 173, oracle 188
total_hours    agent 1093.04, oracle 1125.07
rows: 188 expected, 15 missing, 0 invented
wrong fields on shared rows: {'fees_dollars': 36, 'hours': 1, ...}
```

**All fifteen missing rows are on one engagement.** `00013-Mendes` — "New
Location Setup – Accounting Records Update", 41 time entries — is returned
by `list_matters`, the first discovery call clio offers. The model dropped
it whole, and every firm total is wrong by exactly its contents.

It is the firm's own engagement, carrying no client, which is very likely
why: "engagement" was read as "client engagement". The instruction asks for
every person-and-engagement pair *with any logged time*, and says nothing
about clients.

**Verdict M** — and it is the commitment register's failure in mirror
image. There the model *added* rows a narrow rule excluded; here it *drops*
rows a broad rule includes. Both are the same act: substituting its own
sense of what belongs for the rule it was given.

### tracker-reconciliation, glm-5.2 — 0.832 — all misses M

```
answer.verdict_counts     0.000   absent 33/understated 85 against 35/83
answer.hours_understated  0.000   431.20 against 531.37
answer.effort_figures     0.981   139 rows, 0 missing, 0 invented
wrong fields: {'actual_hours': 4, 'tracker_hours': 2, 'verdict': 2}
```

Eight wrong fields across six rows, out of 139. Two checked against the
record:

* `00002-Fairmount / Sylvia Nakamura` — the agent credits the tracker with
  0.75 hours for her. **The sheet has nine lines for `tkt-000002` and she
  is on none of them.** The invented figure then flips the verdict from
  `absent_from_tracker` to `understated`.
* `00007-HarborLight / Priscilla Wong` — the agent totals 27.62 hours.
  Clio holds **34 entries, 45.15 hours**. It under-summed by a third.

Both facts are served, the oracle passes its independent derivation, and
the instruction decides both cases. **Verdict M.**

## Retired

**engagement-status-integrity.** Its answer on r12 is empty — nothing moved
backwards anywhere, and twelve of fourteen engagements never changed status
at all. A task with no rows grades nothing: every agent that reports
nothing is exactly right. Retired rather than repaired, because the world
became coherent, which is the outcome that was wanted.

Its history is the reason this ledger exists. It once scored 0.067, and
establishing that as **E** — clio served no matter history at all — took a
rollout, a tool fix and a careful re-read. The task was sound the whole
time.
