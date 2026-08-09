# Failure-mode audit — why models score low

Five clean-room auditors (Sonnet 5), each given only the artifacts and one
question, explicitly barred from reading this run's own reports. Two
per-task grader sub-audits ran adversarial variant batteries. One auditor
ran 7 fresh episodes, read every transcript, and re-graded each deliverable
field by field. Findings below are theirs; corrections are mine, marked.

## The answer in one line

Low scores are **roughly one third grading artifact, one third search
economy, one third genuine difficulty** — and almost none of it is a broken
environment.

Cause breakdown over 7 graded episodes (transcript-level, not inferred):

| cause | count | example |
|---|---|---|
| F — model capability | 4 | never opened a single DM on a task whose instruction names DMs as the trap; quit at 31% of budget |
| C — budget exhaustion | 2 | GLM and DeepSeek both scored 0.00 on the *cheapest* task (11-call floor) by never reaching write_file |
| E — grader mismatch | 1 | 100% recall on the true answer set, scored 0 on the 0.56 field |
| B — tool obstruction | 1 contributing | a silent empty result from a plausible-but-wrong timestamp |
| A — genuine difficulty | never the sole cause | always compounded by F |

## 1. Environment — sound

Referential and causal integrity are clean: zero dangling references, zero
backwards replies, all attachments resolve, cross-server `people`/`meta`
tables byte-identical, `check_coherence` returns zero findings. Errors are
clean over real stdio. Full enumeration is cheap (all Gmail 9 calls, all
Slack 41). **No environment defect causes a single observed failure.**

## 2. Tools — one blocking gap, several silent-wrong bugs

| severity | finding |
|---|---|
| **blocking** | `slack_search_public` structurally excludes DMs — **2,157 of 3,331 messages (65%) unsearchable**, silently. Real Slack MCP ships a `search_public_and_private` variant we never implemented, so DM difficulty is partly *our missing tool*, not a realistic constraint |
| serious | iManage search matches **stale superseded versions** without saying which version hit — agents cite facts the head no longer contains, on tasks explicitly about version drift |
| serious | Clio types all three associates as `NonAttorney` (`ATTORNEY_TITLE_WORDS` omits "associate") |
| serious | Clio's substantive `matter.detail` is projected but read by **no tool** — permanently unreachable |
| serious | `WORKBENCH_SEAT` honored by Gmail, partially by Clio, **ignored by Slack and iManage**; no task sets a seat, so every agent has omniscient access including others' private DMs |
| serious | `who_am_i` fabricates an identity when no seat is set |
| minor | `slack_search_public` computes a pagination cursor and discards it |

## 3. Verifiers — the dominant artifact

**56–63% of the score in 8 of 10 tasks is a single exact-set-match field
with no partial credit.** Measured consequences:

- An otherwise-perfect answer missing **one item** of a 4–7 item set
  collapses 1.00 → **0.44**.
- Outcomes cluster in two bands — ~0.10–0.20 (nothing) and ~0.44–0.73
  (near-perfect) — with almost nothing between. Poor for ranking, worse as
  RL gradient: improving 60% → 95% coverage moves the score not at all.
- **Shotgun vulnerability is task-specific.** `visitor-log-audit`: marking
  all 74 requests open scores **0.44** — identical to near-perfect work, so
  that number is uninterpretable. `operative-deadline` closes the same hole
  with an exact-length check (kitchen sink → **0.00**). The fix is already
  in the repo; the sibling graders just lack it.
- `vantage-triage` scores **0.92 with keyword-stuffed boilerplate and zero
  tool calls** — its `basis` field is substring-matched and carries 60% of
  each clause. The template the suite was built from is its worst grader.
- `client-departure-postmortem` scopes to "the Cascadia engagement" in
  prose but enforces literal `"Cascadia" in subject`. The client contact
  also sends templated filler ("Availability next week") that a reasonable
  agent judges on-engagement. Luna had **100% recall on the true four** and
  scored 0 on the 0.56 field.

Where ground truth was independently re-derived it was **exact** —
billing-hygiene (all 7 fields), operative-deadline (two methods),
visitor-log, vanished-clause's clean set, redline-provenance. Graders are
deterministic and crash-safe. `vantage-triage`'s evidence trail cites a
document revision that does not exist, and its playbook explicitly
disclaims vendor paper while the ground truth requires applying it —
costing a careful agent 0.3.

## 4. Data — real needles, degenerate corpus

Verified signal: billing-hygiene's answer is **7 of 1,427 entries (0.49%)**
ringed by three decoy classes (77 DM-only, 13 email-only, 59 channel-only)
that defeat any single-surface shortcut. Cross-message numeric consistency
holds across independent senders.

Degeneracy, measured:

| surface | volume | distinct | note |
|---|---|---|---|
| Gmail | 671 | 434 bodies | **91.5% is 9 admin templates** with names swapped |
| Slack | 3,331 | 459 bodies | **86% exact duplicates** |
| Slack DMs | 2,157 (65% of chat) | **62 strings** | one repeated 114× |
| Clio narratives | 1,427 | 78 | 8 phrases × 10 matters |
| Clio notes | 178 | 5 phrases + 2 | the 2 unique notes *are* the planted needles |

Plus: **zero weekend or holiday activity in four months**, time entries
only 15:00–18:00, 2.08 billed hrs/person/day, **no rate/dollar/invoice
field anywhere in Clio**, 49 calendar events projected into no database,
7 of 10 matters with zero documents, `matter_history` with one row.

Consequence: usable for retrieval evals, **not suitable as post-training
corpus** without aggressive dedup — and the filler is *load-bearing* for
the ambiguity in §3's Cascadia case.

## 5. Design problems that outlast any bug fix

1. **No code execution.** The harness offers `write_file`/`finish` plus
   read-only MCP. Exhaustive-recall tasks (1,427 activities × 8 people ×
   120 days) must be tracked in-context across dozens of turns with no way
   to verify bookkeeping. This is the structural reason those tasks cluster
   at 0.10–0.15 while the same model scores **1.00** on standard-drift's
   small enumerable universe. A real professional would use a spreadsheet.
2. **Call budgets derived from an oracle.** `measure_floors.py` hardcodes
   ground-truth markers, so the floor never counts exploratory search.
   Budget exhaustion then scores identically to never trying.
3. **~4–5 distinct skills across 10 tasks**; one anti-join idiom supplies
   56% of the score in six of them. Ranking on this suite over-weights one
   shape.
4. **One world, eight framings** — all bundles byte-identical. No
   distributional coverage, no generalization evidence.
5. **Workspace leakage**: head-version documents sit in the agent
   workspace, so some graded sub-fields are answerable with zero tool calls.

## What this means for the headline result

"All three models under 0.5" is **not** established as a competence claim.
Luna's 0.44 on two tasks is exactly the near-miss value; on
`client-departure-postmortem` it demonstrably found the right answer and
lost to grader operationalization. The suite currently separates "did
nothing" from "did the work" and cannot separate competent models from each
other.

## Fix order (highest value first)

1. Replace exact-set-or-zero with F1/precision-recall partial credit —
   mechanical, the hits/extras computation already exists in these files.
   Restores both ranking power and RL gradient.
2. Add the `operative-deadline` exact-length guard to every set field that
   lacks it (closes the shotgun band).
3. Fix `vantage-triage`'s `basis` grading (semantic or rubric, not
   substring) — currently 0.92 for boilerplate.
4. Implement `slack_search_public_and_private`; make iManage search report
   the matching version; fix the Clio associate and `matter.detail` bugs.
5. Add a code-execution tool, then re-measure — the exhaustive tasks may be
   testing note-taking stamina rather than professional competence.
6. Re-derive call budgets from a blind-search strategy.
7. State each grader's operative rule verbatim in its instruction.
8. Dedup the filler corpus, or stop routing it through client contacts.
