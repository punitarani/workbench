# Which staged tasks the corpus can actually support

Measured on the recording in progress at **day 13 of 130** — 595 message
bodies, 2,325 time entries, 55 documents. Rates, not totals, are what
carry to the full window; each row below extrapolates linearly and says
so.

Every one of these five tasks was authored *before* the world existed,
from a picture of how a law firm writes. Three of the five premises turn
out not to match what the firm actually writes. That is the entire reason
the `«MEASURE»` placeholders exist, and it is cheaper to find here than
in a rollout where a starved rule reads as a model failure.

## Verdicts

| task | mechanism | measured | verdict |
|---|---|---|---|
| `off-sense-register` | word admitted in a non-register sense | `confirm` 200 msgs, `file` 51 | **ship** — narrow the word list to these two |
| `deadline-week-promise-clock` | promise → due date → followed up? | 4 of 7 forms live; followed-up 39% | **ship** — 4-form table, not 7 |
| `prebill-narrative-screen` | defective time-entry narratives | 48 defects in 2,325 (2.1%) | **ship bounded** — see below |
| `one-sentence-two-dates` | two forms, one sentence, different dates | ~0 real instances | **retire** |
| `court-clock-computation` | interval form + calendar date | 0 and 0 | **retire** |

## Why the two retire rather than widen

`court-clock-computation` needs `within N days` (0 occurrences) *and* a
`<Month> <day>` date (0). Both halves absent.

`one-sentence-two-dates` looked alive at 18 messages until the text was
read. Fourteen were **compound spellings of one deadline** — `by tomorrow
EOD`, `EOD Friday` — where two form words name a single date. The rest
were multi-item lists sharing a due date: *"Earnout terms — call EOD
tomorrow"* and *"Northmoor diligence — due EOD tomorrow"* in one message
is two items on one date, not two dates.

A count matched the premise; reading the matched rows refuted it. **The
detector agreed with me and the data did not.**

Widening either rule — admitting `two weeks`, or counting compound
spellings as two dates — would swap a rule the firm does not write for a
rule nobody stated, and the register would then measure the author's
vocabulary rather than the model.

## Why `prebill-narrative-screen` must be bounded

2.1% of entries are defective: 35 vague openers, 8 notes of three words
or fewer, 5 billable blocks of four hours or more, 0 orphans. At the full
window that is roughly **480 defects in 23,250 entries**.

Unbounded, that is a coverage task, and coverage difficulty is bimodal —
a model either sweeps the corpus or samples it, and the score lands near
1 or near 0 rather than in the band. Bound it to one matter for one
month, ~200 entries with a handful of defects, and the difficulty moves
into the *rule*: which of these notes actually violates the stated
standard. Rule difficulty survives bounding; coverage difficulty does not.

## What the corpus carries in volume

Replacements should be drawn from here rather than from imagination.
Counts are 13 workdays, extrapolated in brackets.

| signal | events | at 130 days |
|---|---|---|
| time entries, median 11-word note, 59% billable | 2,325 | ~23,000 |
| `EOD`/`COB` deadlines | 104 msgs | ~1,000 |
| calendar events / responses | 750 / 138 | ~7,500 / ~1,400 |
| `confirm` in a message body | 200 | ~2,000 |
| meetings with transcripts | 75 | ~750 |
| document revisions / creates | 104 / 55 | ~1,000 / ~550 |
| tickets created / updated | 31 / 48 | ~310 / ~480 |

Two replacements are needed. The volumes above admit several shapes the
current five do not touch — a calendar with 1,400 responses supports a
scheduling-commitment task; 750 meeting transcripts support extracting
what was agreed in a room against what was later written down.
