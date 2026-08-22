# The live commitment register

You are the practice administrator at **Merrick Stanton LLP**, a
litigation-and-transactions firm. The partners meet daily and weekly, and
the meetings are where dates get set. Somebody says they will have a thing
done by a day; a week later, in the same standing meeting, they say a
different day. Neither statement is written down anywhere except in the
transcript of the room it was said in.

Before the partner meeting you produce the register of **what is still
owed**: who owes it, on which matter, and by when — counting only the most
recent thing each person said about each matter.

The firm's systems are available through tools: **meetings** (transcripts
of what was said), **clio** (matters, users and time entries), **gmail**,
**slack**, **imanage** and **calendar**.

## Where the answers are

**In the transcripts, and only there.** A commitment made out loud is not a
field in any system. A matter in clio has an assignee and a status; it does
not have "Cecile said Thursday". This register is built by reading what
people said.

Mail and chat are not this register. A promise made in an email is a
different act from a promise made in a room, and this report is about the
room. If somebody commits in a meeting and mentions it later in mail, the
meeting is what counts and the mail changes nothing.

## The window

Read the meetings held on the working days from
**«MEASURE: window first day — the calendar date of the Monday the window
opens, written as e.g. "Monday 2 February 2026". Choose it so the window
contains at least «MEASURE» meetings and stays under the word ceiling the
screen enforces; `datasets/merrick/measure_transcripts.py` prints both.»**
through
**«MEASURE: window last day — the calendar date of the Friday it closes.»**,
inclusive — **«MEASURE: the number of working days in that span»** working
days, **«MEASURE: the number of meetings held in it»** meetings and
**«MEASURE: the total word count»** words of transcript.

A meeting is in the window when it **started** inside it. `meetings_read`
counts the meetings you opened — every meeting in the window, whatever was
said in it.

## What counts as a commitment

A turn is a **commitment** when the person speaking says they will do a
specific thing, on a named matter, by a named day.

All three have to be present in what that person said:

- **a person taking it on.** They are speaking about their own work —
  *«MEASURE: a real turn from the corpus in which somebody takes work on
  themselves»*. Somebody assigning work to another person is not that
  person's commitment; it is an instruction, and it makes no row.
- **a matter.** The work has to attach to one of the firm's matters, named
  in the turn. Use the matter's display number as clio shows it.
- **a deadline.** A day named for this coming week, either as a weekday or
  in the forms the firm actually uses for a near date —
  *«MEASURE: the admitted deadline forms, with a count for each, and the
  normalisation. `EOD`, `COB` and "end of the day" are one deadline and
  must be reported as one token; a reader who treats them as three reports
  three live commitments where the firm has one.»*

«MEASURE: how often all three co-occur, and the count of turns carrying
each part alone. Measure this on the finished record and do not carry the
earlier numbers over — the deadline rate is the one that moved. On the
first recording 27% of meetings named a weekday; on the corrected engine
it was 14%, while owner phrases and matter mentions held steady, and a
weekday-only rule fell to six rows with no supersession at all. The
relative forms are what the corpus writes: 243 turns against 83.»

Nothing else is a commitment. In particular:

- **A question is not a commitment.** *«MEASURE: a real turn asking when
  something will be done»* names a matter and a day and promises nothing.
- **Somebody else's work is not your commitment.** *«MEASURE: a real turn
  in which a chair assigns work to a named colleague»* makes a row for
  nobody: not for the chair, who is not doing it, and not for the
  colleague, who did not say it.
- **A date already passed is not a commitment.** A turn reporting that
  something *was* done on a day is a report, not a promise.

## Which one is live

**A person makes one live commitment per matter: the most recent one.**

When the same person names a day for the same matter in a later meeting,
the later statement replaces the earlier one entirely. The earlier one is
not a second row, not a note, and not part of the register — it is simply
no longer what they owe.

Later means later by **when the meeting started**, not by where the turn
sits in the transcript. Two meetings on the same day are ordered by their
start times; a person who names a day twice inside one meeting is making
one commitment, and the later turn is the one that counts.

«MEASURE: the share of rows whose deadline differs between the person's
first and last statement about that matter. `measure_transcripts.py`
prints it and refuses under 15%, because a corpus in which nothing is ever
superseded makes a reader who takes the first answer always right.

Measure it with the admitted forms this brief settles on, and ignore the
earlier figures rather than carrying them over: a weekday-only rule read
45% on the first recording, 11% on a 30-day window of it, and 0% on the
corrected engine, which is three answers to one question and none of them
this task's. On 26 recorded days of the corrected engine with weekday and
relative forms both admitted it was 32% of 31 rows.»

A commitment made once and never mentioned again is live. It does not need
repeating to count.

## What to produce

One file in your workspace: **`live_commitments.json`**, with exactly these
fields:

- `meetings_read` — how many meetings you opened: every meeting inside the
  window, whatever was said in it.
- `turns_read` — how many turns those meetings contained.
- `distinct_owners` — how many different people hold a live commitment.
- `matters_with_a_commitment` — how many different matters appear in
  `live`.
- `superseded_count` — how many commitments you found that a later one
  replaced. These make **no row**; this is the count of what you discarded.
- `live` — **one entry per live commitment**, sorted by `matter` then
  `owner`, each with:
  - `matter` — the matter's display number, exactly as clio shows it
  - `owner` — the person's full name
  - `day` — the deadline they last named, normalised to the token the
    table above gives it, lowercase — e.g. `thursday`, or `end of week`
  - `meeting_id` — the meeting in which they last named it
  - `said_at` — the ISO-8601 start of that meeting

Two entries by the same person on the same matter is always wrong: the
later one replaced the earlier.

## A warning about completeness

The register is only right if you have read every meeting in the window.
A commitment you never saw is a missing row; a commitment whose later
replacement you never saw is a **wrong** row, reported as live when the
firm has moved on. There is no field anywhere that lists commitments and
no summary that collects them — the only way to know what was said is to
read what was said.
