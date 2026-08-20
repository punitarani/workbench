# The prebill narrative screen

You are the practice administrator at **Merrick Stanton LLP**, a
litigation-and-transactions firm. Before a billing cycle's prebills go out,
the firm runs a screen over the time-entry narratives: any entry whose
narrative uses one particular word is pulled out for a partner to read
before the bill leaves the building, because that is the word clients write
back about.

What the partners want is the screen's output — laid out by matter and by
timekeeper, with the time behind it and what that time is worth.

The firm's systems are available through tools: **clio** (matters, users
and time entries), **gmail**, **imanage**, **slack**, and **calendar**.

The screen reads **time entries and nothing else**. The narrative is the
note recorded on the entry. A mail message, a chat message or a document
that uses the same word is not a time entry and makes no row here.

## The window

Screen only time recorded on the working days from
**«MEASURE: window first day — the calendar date of the Monday the window
opens, written as e.g. "Monday 2 February 2026". Choose it early enough in
the six months of history that an agent paging `list_activities` in time order
can reach the end of the window without walking the whole record, and
report the page count it costs.»**
through
**«MEASURE: window last day — the calendar date of the Friday the window
closes.»**, inclusive — **«MEASURE: the number of working days in that
span»** working days.

The window is its two endpoints. An entry dated **on or after** the first
day and **on or before** the last day is in scope, whatever weekday it
carries; an entry dated a single day either side of the span is out, however
plainly it belongs to the same piece of work.

`entries_read` counts the time entries **inside the window** — the ones you
actually had to read. There is no need to open the rest of the firm's
timekeeping; it is not part of this question.

## What the screen admits

A time entry is **flagged** when its narrative contains one of these exact
forms, matched case-insensitively, anywhere in the text:

| form | matches |
|---|---|
| «MEASURE: admitted form 1 — the first spelling of the chosen root» | the word *«MEASURE: admitted form 1»* |
| «MEASURE: admitted form 2 — the second spelling of the same root» | the word *«MEASURE: admitted form 2»* |

«MEASURE: how many admitted forms the family has, and which they are. Run
the family screen over `activities.note` inside the window — the existing
screen in `datasets/merrick/measure_candidates.py` reads mail and chat
bodies, and narratives are a different corpus with a different vocabulary.
Three numbers decide it: both forms must actually fire; each must match
entries the other does not; and the *off-sense share* of the admitted form
— how often it appears meaning something other than the idea the screen is
named after — must be high, because that is the share a model reading for
meaning throws away. Add or remove table rows to match what the corpus
carries. Every prose count below is downstream of this choice.»

**A form is a whole word.** It counts when there is **no letter
immediately before it and no letter immediately after it**. A digit, a
hyphen, a slash or a punctuation mark is not a letter, so
*«MEASURE: a hyphenated or slashed compound the corpus actually writes
whose second part is an admitted form»* carries the form and **is**
flagged.

**The test is textual, not editorial.** An entry is flagged when the word
is in its narrative, whatever the sentence is doing with it.
*«MEASURE: a narrative from the corpus where the admitted form is used in
an off-sense — adjectival, idiomatic, future or conditional — and which the
screen therefore flags anyway»* is flagged. Do not weigh up whether the
narrative is really about the thing the screen is named after; read the
words, not the intent.

**A form inside a longer phrase still counts.** The words around it do not
remove it. *«MEASURE: a real narrative in which the admitted form sits
inside a longer set phrase»* contains the form, so it is flagged.

Nothing else counts, and that cuts two ways.

No **synonym** counts — «MEASURE: the four or five near-synonyms this
corpus actually writes for the same act, with the count of narratives that
use one and never use an admitted form. Every one of them stays out, and
this is the sentence that says so.»

No **other form of the word** counts. «MEASURE: the excluded inflections —
the -ing, -s and nominal forms of the same root — with how many narratives
carry only one of those.» A narrative carrying only one of those is not
flagged.

**One flagged entry per time entry**, however many admitted forms its
narrative carries and however many times. For `form_counts`, an entry
carrying more than one form counts once, under whichever form is **listed
first in the table above**.

## Which matters are in scope

Every matter the firm records time to. That includes the firm's own
standing codes — intake and conflicts, billing and WIP, administration,
internal meetings, business development, professional development, pro
bono, recruiting — which carry no client and are named for the firm rather
than for a client. Time booked to them is time, it is screened the same
way, and it makes rows like any other matter's.

## The arithmetic

Quantities are recorded in **seconds**. **Hours are seconds ÷ 3600.**
Rates are **dollars per hour**, recorded against the individual entry.
Fees are in **dollars**: an entry's fee is the rate on that entry times
that entry's hours.

**Fees are per entry, not per person and not per matter.** Charge each
entry at the rate that entry carries and add the results. Do not total
somebody's hours and multiply once by a rate found elsewhere: people work
at different rates in different places, and the two methods give different
answers.

**Not every hour can be charged, and there are two separate reasons.**

- Some time is recorded **non-billable**. It is real time and it was really
  worked. It belongs in `entries` and in `hours`, and it carries **no
  dollars**.
- Some timekeepers carry **no rate at all** — the firm has staff whose time
  is recorded and never charged out. Their entries belong in `entries` and
  in `hours` too, and they carry **no dollars**, because there is no rate
  to charge them at. This holds even for an entry marked billable that has
  no rate on it.

An entry contributes to `fees_dollars` only when it is billable **and** has
a rate. Everything flagged contributes to `entries` and to `hours`.

**Round once, at the end — every figure, not only the totals.** Each row's
`hours` and `fees_dollars`, and the report totals `hours_total` and
`fees_total_dollars`, are computed **from the time entries themselves** and
rounded to two decimal places only when they are written. They are **not**
computed by adding up figures that have already been cut to two decimals.
This decides rows as much as it decides totals: a row is a sum over as many
as «MEASURE: the largest number of flagged entries in one matter-and-
timekeeper row» entries, and the two orders disagree on «MEASURE: the share
of rows on which sum-then-round and round-then-sum give different figures at
2 dp. `tests/verify.py` computes and prints this, and fails the derivation
below a fifth. On the two-day probe bundle it is 0.0% of 59 rows, because
those rows average 1.2 flagged entries each and a one-entry row cannot
disagree with itself — so this paragraph is decoration until the window is
long enough that the median row carries several flagged entries. Size the
window on that, and if a window wide enough to do it costs too many pages
to walk, coarsen the grain to the matter alone and drop `timekeeper` from
the row.» of the rows here. The firm's screened hours come to
«MEASURE: hours_total computed from the entries» from the entries and
«MEASURE: the same figure computed by summing the rounded row figures»
from the rounded rows, and only the first is the answer.

## What to produce

One file in your workspace: **`prebill_screen.json`**, with exactly these
fields:

- `entries_read` — how many time entries you examined: every entry inside
  the window, whatever its narrative says.
- `entries_flagged` — how many of those the screen admits.
- `pairs` — how many matter-and-timekeeper combinations appear in
  `screened`.
- `hours_total` — the flagged hours, all of them, 2 dp.
- `fees_total_dollars` — what the flagged time comes to, 2 dp.
- `form_counts` — an object with **every** form in the table above as a
  key, including any that no narrative in the window uses, each mapped to
  how many flagged entries carry it.
- `heaviest_matter` and `heaviest_timekeeper` — the matter and the
  timekeeper of the single row in `screened` with the most `hours`. Break a
  tie by taking the earlier `matter`, then the earlier `timekeeper`,
  alphabetically.
- `screened` — **one entry per matter-and-timekeeper combination with at
  least one flagged entry**, sorted by `matter` then `timekeeper`, each
  with:
  - `matter` — the matter's display number, exactly as clio shows it
  - `timekeeper` — the person's full name
  - `entries` — how many flagged entries they recorded on that matter
  - `hours` — the hours those entries carry, 2 dp
  - `fees_dollars` — what those entries come to, 2 dp

A matter-and-timekeeper combination with time in the window but nothing
flagged makes no row.

## A warning about completeness

The firm's timekeeping runs to «MEASURE: the total number of time entries
in the six-month record» entries and the tools hand them back a page at a
time. Every figure in this report depends on having read the narrative of
every entry inside the window — not a sample of them, and not the matter
descriptions instead. A page left unread is not a small error; it is a
wrong row and very likely a missing one.
