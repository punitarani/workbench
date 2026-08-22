# The live commitment register

You are the practice administrator at **Merrick Stanton LLP**, a
litigation-and-transactions firm. The firm's standing meetings are where
dates get set. Somebody says they will have a thing done by a day; a week
later, in the same standing meeting, they say a different day. Neither
statement is written down anywhere except in the transcript of the room it
was said in.

Before the partner meeting you produce the register of **what is still
owed**: who owes something, in which standing meeting they said so, and the
date it is due — counting only the most recent thing each person said in
each meeting.

The firm's systems are available through tools: **meetings** (transcripts of
what was said), **clio** (matters, users and time entries), **gmail**,
**slack**, **imanage** and **calendar**.

## Where the answers are

**In the transcripts, and only there.** A commitment made out loud is not a
field in any system. Clio has assignees and statuses; it does not have
"Cecile said Thursday". This register is built by reading what people said.

Mail and chat are not this register. A promise made in an email is a
different act from a promise made in a room, and this report is about the
room. If somebody commits in a meeting and mentions it later in mail, the
meeting is what counts and the mail changes nothing.

## The window and the meetings

Read the meetings held from
**«MEASURE: window first day — the calendar date the window opens, written
as e.g. "Monday 2 February 2026". `datasets/merrick/measure_transcripts.py`
prints meetings, turns and words per window and refuses over 60,000 words
or under 25 meetings.»** through
**«MEASURE: window last day.»**, inclusive — **«MEASURE: working days»**
working days and **«MEASURE: the number of standing meetings in it»**
meetings.

A meeting is in the window when it **started** inside it; one that runs past
the last day is still that day's meeting.

**Only the firm's standing meetings count.** A standing meeting is one that
recurs: its title appears on **three or more days** inside the window. The
firm also holds one-off working sessions, called to settle a single
question; those are **not** part of this register and make no rows, however
much is promised in them. `meetings_read` counts the standing meetings you
opened, whatever was said in them.

## What counts as a commitment

A turn is a **commitment** when the person speaking says **they** will do
something, and names **when**. Both have to be present in the same turn.

- **The speaker is taking it on themselves**, in the first person, about a
  **future** act. In this firm's transcripts that is written
  «MEASURE: the admitted owner forms as a CLOSED SET, not an example.
  Measured on the previous record: `I'll` 501 turns, `I will` 9, and
  nothing looser survives contact — `I have` is possession, `I'd` is
  conditional, `I can` is as often `I can't`.

  A probe is why this says "closed set". The brief stated the deadline
  forms as a table and gave only an *example* for this one, so the two
  halves of one rule were written asymmetrically and Opus 5 generalised —
  correctly, by the brief's own words. The oracle took Dov Reinhardt's
  "i'll have a firm answer by eod"; the agent took his later "i'm calling
  their counsel", which does say he will do something. It came out broader
  on some turns and stricter on others, 22 rows against 33 with only one
  of its own spurious, which is what a boundary nobody pinned down looks
  like from the outside. The score then measures agreement with a regex.

  A count of EXCLUDED material is safe and useful — `off-sense-register`
  publishes them freely and nobody chases them, because reproducing a
  count of what makes no rows earns nothing. A count of the ANSWER'S OWN
  composition is a specification. Publish the first, never the second
  unless it is an exact reproducible partition.» —
  *«MEASURE: a real turn in which somebody takes work on themselves»*.
  Nothing looser counts, and two things that read like commitments are not:
  - **A report of what is already under way.** *«MEASURE: a real turn
    describing present activity — the previous record wrote "I'm calling
    their counsel now"»* names no future act. It makes no row.
  - **Work handed to somebody else.** *«MEASURE: a real turn in which
    somebody assigns work to a named colleague»* is an instruction, and it
    makes a row for nobody: not for the speaker, who is not doing it, and
    not for the colleague, who did not say it. The same is true of a chair
    recapping what other people promised.
- **A day is named.** In the forms this firm actually uses for a near date:
  *«MEASURE: the admitted deadline forms, and the compound forms that occur,
  stating that each compound names one deadline. Include the relative forms;
  a weekday-only rule is measured dead on this world.*

  ***Name the forms. Do NOT publish a count for each.*** *A count in a brief
  is not colour, it is a specification: a probe watched Opus 5 read
  "end of day — 66 turns; tomorrow — 42; a named weekday — 28; `EOD
  tomorrow` — 15" as a target to reproduce, write `target eod66 tom42 wd28
  eodt15 total151` into its own scratch file, and spend turns trying
  counting modes against it — 223 under one, 270 under another — because
  raw match counts over overlapping patterns are not a partition and cannot
  be reproduced by anyone. Measure them for yourself, to choose the forms;
  publish only the forms.»*

Nothing else is a commitment. In particular, **a question is not one**
(*«MEASURE: a real turn asking when something will be done»* names a day and
promises nothing), and **a date already past is not one** — a turn reporting
that something *was* done on a day is a report, not a promise.

## Turning what was said into a date

The register reports **dates**, not the words. "EOD" said three weeks apart
is two different obligations, so every deadline is resolved against **the
day the meeting was held**:

- **end of day** — including `EOD`, `COB` and "close of business" — is the
  day of that meeting.
- **tomorrow** is the next working day. Said on a Friday it means the
  following Monday: the firm does not work weekends, and a Saturday
  deadline is a day on which nobody can deliver.
- **end of week** is that week's Friday. Said on a Friday it means that same
  day, not a week later.
- **a named weekday** is its next occurrence, always *after* the day it was
  said. Said in a Thursday meeting, "Thursday" is next Thursday.
- **a compound** such as "EOD tomorrow" is one deadline, not two.

## Which one is live

**A person makes one live commitment per standing meeting: the most recent
one.**

When the same person commits again in a later meeting of the same series,
the later statement replaces the earlier one entirely. The earlier one is
not a second row, not a note, and not part of the register — it is simply no
longer what they owe. This is true **even when they say the same words**: a
person who said "EOD" a fortnight ago and "EOD" again this week owes this
week's date, not the old one.

Later means later by **when the meeting started**, not by where the turn
sits in a transcript. Two meetings on the same day are ordered by their
start times; a person who commits twice inside one meeting is making one
commitment, and the later turn is the one that counts.

«MEASURE: the share of rows whose deadline differs between the person's
first and last statement. `measure_transcripts.py` prints it and refuses
under 15%, because a corpus in which nothing is ever superseded makes a
reader who takes the first answer always right. On 45 days of the partial
record it was 82% of 28 rows once resolved to dates.»

A commitment made once and never repeated is live. It does not need
restating to count.

## What to produce

One file in your workspace: **`live_commitments.json`**, with exactly these
fields:

- `meetings_read` — how many standing meetings you opened: every one inside
  the window, whatever was said in it.
- `turns_read` — how many turns those meetings contained.
- `distinct_owners` — how many different people hold a live commitment.
- `superseded_count` — how many commitments you found that a later one
  replaced. These make **no row**; this is the count of what you discarded.
- `live` — **one entry per live commitment**, sorted by `meeting` then
  `owner`, each with:
  - `owner` — the person's full name
  - `meeting` — the standing meeting's title, exactly as the record gives it
  - `due` — the date it is due, as `YYYY-MM-DD`
  - `meeting_id` — the meeting in which they last committed
  - `said_at` — the ISO-8601 start of that meeting

Two entries by the same person in the same standing meeting is always
wrong: the later one replaced the earlier.

## A warning about completeness

The register is only right if you have read every standing meeting in the
window. A commitment you never saw is a missing row; a commitment whose
later replacement you never saw is a **wrong** row, reported as live when
the firm has moved on — and it will be wrong in the date, which is the field
that cannot be recovered from anywhere else. There is no field anywhere that
lists commitments and no summary that collects them: the only way to know
what was said is to read what was said.
