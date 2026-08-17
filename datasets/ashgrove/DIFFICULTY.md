# Where difficulty actually comes from in this suite

Measured, not assumed. Everything here is evidence gathered while seven of
eight tasks refused to leave 1.000.

## What does not work: width

| task | work the agent did | Opus 5 |
|---|---|---|
| engagement-time-allocation | 1,304 entries, 27 pages, 197 rows | ~1.0 |
| work-product-review | 154 tool calls, 6.96M input tokens | 0.991 |
| client-responsiveness-sla | 41 threads | 1.000 |

More rows buys labour, not error. A number sitting in a SQL column is read
correctly however many pages deep it is. **Volume is a cost multiplier, not
a difficulty multiplier**, and every attempt to make these tasks harder by
widening them has come back at ceiling.

Two of the sub-1.0 scores were not difficulty either — they were defects:
`engagement-time-allocation`'s 0.816 was a rounding rule the instruction
never named, and `engagement-status-integrity`'s 0.067 was clio serving no
matter history at all.

## What should work: where the fact lives

### 1. Prose — the fact is in no column at all

Measured on the 10-day world (the 15-day world is ~1.5× this):

```
messages: 328   with >=1 commitment phrase: 160 (49%)
    92  EOD/COB                   9  end of week
    64  by <weekday>              7  within N days
    25  by <month> <day>          2  end of month
                                  1  tomorrow
messages with 2+ phrases: 34
chat messages with a commitment phrase: 274 of 1,219
```

So roughly **200 graded rows in email alone**, each of which exists only in
a message body. The agent must read every body through a paginated tool
surface — about half a megabyte of prose — apply the stated patterns, and
resolve each relative date against that message's own sent date.

Resolution is deterministic, which is what makes it gradeable. Sampled:

```
msg-000005  sent Mon 2026-01-05  "by Friday"    -> Fri 2026-01-09
msg-000007  sent Mon 2026-01-05  "by Thursday"  -> Thu 2026-01-08
```

The rule — *the next occurrence of that weekday strictly after the sent
date* — goes in the instruction verbatim, along with the phrase list. The
agent is not being asked to guess a grader's taste; it is being asked to
not miss any of two hundred needles while reading everything.

**Expected failure mode: recall.** Missed instances cost F1, which produces
partial credit naturally instead of the near-binary outcomes a 4-row task
gives. That is a genuine model failure and the whole point.

### 2. Reconciliation — the fact is recorded twice, differently

The ticket system's status against what the correspondence asserts. The
instruction must **state the precedence rule and the tie-break, in words**.

This is the line that keeps the axis honest: a contradictory record *with*
a stated rule is the task; a contradictory record *without* one is an
environment defect. `engagement-status-integrity` is the seed for this and
already reads `matter_history`.

### 3. Entity ambiguity — the fact is attached to the wrong twin

The world has already produced this on its own: two documents titled
"Single Audit Playbook", which capped `work-product-review`'s own reference
solver at 0.976 until the key became `(document, workspace)`. Also
available: a client's trading name in email against its legal name in clio,
and people who share a surname.

### 4. Absence — the fact is that there is no fact

Proving a negative requires reading everything, and one missed page flips a
row from a finding to a miss.

**But the obvious grain does not work, and this was measured rather than
assumed.** "Engagements with logged time but no workpaper / no client mail /
no closing review", keyed per engagement × evidence kind, gives 52 rows of
which three of the four kinds are constant:

```
  time logged      present=13 absent= 0  <- DEGENERATE
  workpaper        present= 0 absent=13  <- DEGENERATE
  client mail      present= 0 absent=13  <- DEGENERATE
  closing review   present= 7 absent= 6
```

The two zeros are the reason: **the world has no explicit engagement↔document
or engagement↔thread link**. The only hard references are activity→ticket and
attachment→document. Everything else has to be joined by inference, and an
oracle built on inference is not deterministic.

Two joins that *are* deterministic and do work:

- **Client by email domain.** `fairmountcommunityfoundation.example` ↔
  `Fairmount Community Foundation`, for all ten organisations. This is how a
  thread reaches an engagement.
- **Client named in prose.** Eight of ten organisations are named in message
  bodies, with real spread and two genuine zeros — variation, not degeneracy:

```
  Kestrel Manufacturing        email  52  chat 686
  Harbor Light Distribution    email  18  chat 141
  Ashfield Pension Trust       email  10  chat   0
  Cardinal Ridge Builders      email   0  chat   0
  Northwind Software           email   0  chat   0
```

So the absence task is built on those, at the person×engagement grain (197
pairs), not on an engagement↔document link that does not exist.

## Row counts available in this world (10 days; 15 days is ~1.5×)

| axis | grain | rows |
|---|---|---|
| prose | (message, commitment phrase) | **536** (200 email + 336 chat) |
| reconciliation | **status change**, not engagement | **40** (13 engagements is far too thin) |
| entity | document | 34, over 101 versions, 17 authors, 8 workspaces |
| absence | person × engagement | 197 |

The reconciliation row is the one to be careful about: keyed per engagement
it is 13 rows and lands back in the near-binary regime that made six of the
original tasks useless. Keyed per status change it is 40.

## Two artefacts found while sizing this

**Fixed.** The surface served `Engagements` and `engagements` as two
workspaces, splitting one engagement's papers across both — and
`work-product-review` keys rows on `(document, workspace)`, so two identical
filings would have graded as two different answers. The workspace is now
folded; a file room is not case-sensitive.

**Recorded, not fixed.** Personas file documents under raw internal ticket
ids — `engagements/tkt-000004/…`, and two documents sit in a workspace
literally named `tkt-000004`. Real firms do not name a file room after a
row id, and `reachability.py` already documents that clio never serves the
`tkt-` form (it serves `00004-KestrelManufacturing`), which once split one
model's two rollouts to 1.000 and 0.273 on which vocabulary each found.
Fixing it means changing the persona prompt, which invalidates every
cassette — so it waits until a re-record is being paid for anyway.

## Rules for tuning difficulty

**Legitimate levers**: how much of the record a task covers, how many
independent facts per row, how many precedence rules apply, how much of the
answer is prose-only.

**Never**: tightening tolerances, trick wording, withholding a stated rule,
grading a fact the tools do not serve. Difficulty must come from the work
being hard, not from the scoring being mean — otherwise the failure is a
task defect wearing a model's clothes, and the whole exercise measures
nothing.

## Floors every task must clear

- **≥12 rows.** Below that a score is a verdict on the rule, not a measure
  of the work: six of seven tasks answered with 4–10 rows and every rollout
  came back 1.000 or near zero, with nothing in between.
- **No constant column.** A field with one value in every row grades
  nothing — an agent that never looks it up and writes the majority value
  scores full marks. `build_tasks.degenerate()` reports these. The 10-day
  `work-product-review` oracle had `reviewed` false in all 34 rows.
- **Oracle independence** (`verify_oracle.py`) and the grading guards must
  pass **before** a rollout is spent.
