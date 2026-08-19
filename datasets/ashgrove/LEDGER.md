# The E/T/M ledger

Why every criterion below 1.0 missed, and the evidence for calling it
one thing rather than another. The classification rules are in
[`../../docs/METHOD.md`](../../docs/METHOD.md) §1 and §7; this is their
application to this suite.

**Only M ships.** Every score below 1.0 is a defect — environment (E),
data (D), harness (H), or task (T) — until proved otherwise. Nothing here
is called M without three things: the oracle survives an independent
derivation from the world log; the failures are scattered rather than
shared across trials; and each disputed row was read in the source rather
than re-matched against the rule that produced it.

---

## In band — all misses M

### commitment-follow-through — 0.576

gpt-5.6-sol 0.515 over 4 answered trials of 9, Opus 5 1.000, glm-5.2
0.213 over 2 of 3. The unbounded task; k=9 was enough to see through
gpt's abandonment rate.

Evidence for M:

- Oracle agrees with its independent derivation.
- **No row is dropped by every trial.** Recall runs 136–145 of 155 and
  the typical pair of miss-sets overlaps 12%.
- The inventions are wrong date arithmetic on real rows (60 of 87 in the
  worst trial) plus **27 rows on messages carrying no time-shaped
  sentence at all**, under a net deliberately wider than the rule.
- glm's 72 shared misses are low recall, not a blocked rule: **every one
  of the 72 was found by a gpt trial.**

### opening-days-completion-claims — 0.774

gpt-5.6-sol 0.687 over 8 of 9, Opus 5 1.000, glm-5.2 0.635 over 3 of 3.

The cleanest certification in the suite: across eight gpt trials **no row
is dropped by every trial and the typical pair of miss-sets overlaps 0%**
— on both the missing rows and the invented ones. Errors that scattered
have no systematic cause left to find.

glm's misses are the semantically awkward rows — *"Once I've completed
the analysis"*, *"Once that call is complete"* — each conditional or
about something other than delivered work, and each containing the word.
The instruction states the test is textual, so they count, and filtering
them on meaning is the model's error.

### opening-week-follow-through — 0.793

gpt-5.6-sol 0.686 over 9 of 9, Opus 5 1.000, glm-5.2 0.693 over 8 of 9.
Every tier reads the same instruction.

The mechanism is compositional rather than arithmetic: one message reads
*"Investor deadline: End of next week (Friday, close of business)"* and
carries **two** forms — `close of business` for the sent date and `end of
next week` for that Friday. Every trial found the first; two of nine
found the second. Reading the parenthetical as describing one deadline
rather than as a second form is the natural mistake, and the instruction
says outright that two forms resolving to different dates make two rows.

The rows glm's trials share are found by other trials (3 of 8, 2 of 8),
which is what separated this from a defect that looked identical in the
detector.

---

## T — task defects, all fixed, gated and re-measured

Six defect classes. Every one was certified as a model failure first, or
would have been.

| defect | scale | gate that now prevents it |
|---|---|---|
| **Ordinals dropped** — the rule said `by <Month> <day>`; the pattern's word boundary made `by April 15th` invisible | 17 rows | rule-accepts-its-own-phrasings |
| **Articles required** — the rule said `by the end of the week`, which the corpus contains once; the firm writes `by end of week` 24 times | 30 rows | rule-accepts-its-own-phrasings |
| **Rounding order unstated** — sum-then-round vs round-then-sum disagree on 34% of person-and-engagement pairs and 100% of firm totals | 6 tasks | rounding-convention-declared |
| **Prose framing vs literal test** — instructions describing a concept and grading a string match | 5 tasks | textual-test-declared |
| **Hedged form** — `within a day or two` contains `within a day`; the rule admitted it and both trials read it as an approximation | 2 rows | stated in the form table |
| **`messages_read` over the whole corpus** — made the agent read 1,585 messages for a 213-message window, producing 0/3 deliverables | 3 tasks | bound the work, not only the answer |

### Why the first two survived every check

The certification was circular. Each disputed row was verified by
re-running *the same pattern* over the message it came from, and the
oracle-independence check shares those patterns deliberately, as the
task's specification. Two confirmations, one regex.

The tell was in the data and was read past: the disputed dates were a
quarter end and the US tax deadline. Dates that meaningful are read, not
hallucinated.

### Why the fourth survived four rounds of auditing

`completion-claims` was scoring 1.000 for Opus and only low scores get
audited. **A task at ceiling hides its ambiguities** — the strong model
resolves them the way the oracle happens to, and the defect stays
invisible until a model careful enough to read semantically meets the
same corpus. The fifth instance was found by auditing the class rather
than by a rollout, on a task that had been reading 0.997.

---

## E — one environment defect

**The staged bundle accumulated three worlds.** `materialize` writes
files and never removes them, and every build since `epoch-r10` was
pointed at one directory: 161 files for a record containing 52 documents,
describing engagements at statuses the live record had long since left.

Blast radius proven nil — a rebuild with the workspace cleaned first
returned **twelve of thirteen oracles byte-identical**, and the only one
that moved belonged to the not-yet-measured task that grades those files.
It survived because nothing had ever graded the workspace: a defect in an
unread surface has no test that can fail.

A second, related defect was found in the same pass: `--refresh-truth`
defaulted to a fixed world path while the bundle shipped from another, so
a fresh answer key was being derived from a stale world. It never fired
only because the coherence gate refused the old world. That is luck, not
a check.

**D — data: none.** Coherence clean, 0 contradictions, 0 dangling refs,
0.1% mis-booked against a 5% limit. The two duplicate-title ambiguities
are reported and keyed around, not silently graded.

---

## H — harness failures, never scored

Not environment defects: the served surfaces pass reachability and
vendor parity. Each produced a `0.000` indistinguishable from a wrong
answer.

| failure | signature |
|---|---|
| codex bridge rejects gpt-5.6-sol | `tool exec invoked with incompatible payload`, nothing written |
| opencode loops | agent repeats its opening line |
| hermes subagent abandonment | 5–9 steps of a 90-step budget, turn ends with children uncollected |
| setup timeout | 360s exceeded on `apt-get` + `nvm` + npm install |
| rate limiting | tool calls succeed, then a limit error, trials die in seconds |

The abandonment is **not** scored against the model: the same model
scores 0.997 and 0.865 on other tasks when it does not delegate. It is a
completion rate belonging to the orchestration layer, and the correct
instrument is more trials.

---

## At ceiling

`open-items-triage`, `self-review-exposure`, `workpaper-open-items` —
1.000 on all three tiers. `tracker-reconciliation` 0.970,
`work-product-review` 0.889, `engagement-time-allocation` 0.912.

`open-items-triage` is worth keeping in view: it read 0.630 on two
models, which looked like difficulty and was ambiguity. Its rule matched
twelve phrases and `we need` appears inside *"what we need to deliver"*;
saying the test was textual took every tier to 1.000. **A score that
moves to ceiling when an instruction is clarified was never measuring the
model.**

## Retired

`engagement-status-integrity` — clio served no matter history at all, so
the answer was not derivable through the tools. Fixed, then retired when
the corrected world produced no backward status move to find.
