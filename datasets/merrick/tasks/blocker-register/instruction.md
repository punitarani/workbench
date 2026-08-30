# The blocker register

You are the practice administrator at **Merrick Stanton LLP**, a
litigation-and-transactions firm. The firm's standing meetings are where
people say what is not moving. Somebody reports they are waiting on a
colleague, or blocked on a document, or cannot sign something off; a
fortnight later, in the same standing meeting, they say it again.

Before the partner meeting you produce the register of **what is stuck**:
who is stuck, in which standing meeting they said so, when they first said
it, when they last said it, and how many meetings of that series they said
it in.

The firm's systems are available through tools: **meetings** (transcripts of
what was said), **clio** (matters, users and time entries), **gmail**,
**slack**, **imanage** and **calendar**.

## Where the answers are

Find them. The firm keeps statuses, tickets, mail and chat, and none of
them was built to answer this question; work out for yourself which surface
carries it and satisfy yourself the others do not.

**This register has no dates in its sentences.** A commitment says "by
Thursday" and hands you its own date. A complaint says only that somebody
is stuck. Every date in this report comes from the MEETING it was said in,
which means a reader who finds one complaint cannot tell whether it is the
first or the ninth without having read every other room in the series.

## The window and the meetings

Read the meetings held from
****Tuesday 6 January 2026**** through
****Monday 6 July 2026****, inclusive — ****129****
working days and ****520****
meetings.

A meeting is in the window when it **started** inside it.

**Only the firm's standing meetings count.** A standing meeting is one that
recurs: its title appears on **three or more days** inside the window. The
firm also holds one-off working sessions; those make no rows, however much
is stuck in them.

## What counts as a blocker

A turn is a **blocker** when the speaker says **they** are stuck, in a
clause of their own. The forms this firm uses are: *blocked on*, *waiting
on*, *waiting for*, *held up by*, *stuck on*, and *can't* followed by
*move*, *proceed*, *close*, *sign* or *finish*.

The speaker may be named by a pronoun or by something they own: *"I'm still
waiting on Ulrich"* and *"the reserve analysis in **my** memorandum is
waiting on that sign-off"* are both rows.

**The speaker may also be left out.** This firm drops the subject
constantly, and a clause that simply opens with the complaint is the
speaker reporting themselves: *"Still waiting on Clement."*, *"Waiting on
Samir, same as everyone else."* and *"blocked on the Martinez transcript."*
are each a row. The exception is a clause where the complaint is the
sentence's **subject** rather than its report -- *"waiting on Bennett before
flagging Rosalie just compounds the delay"* argues about a wait nobody is
having, and is not a row.

A dropped subject also carries **across a comma**, through a run of things
the speaker did: *"sent within her 2-day deadline, cc'd her and Adaora,
waiting on her specific line/share-count numbers"* is the speaker waiting.
It carries only where the run is what the speaker **did**: *"the Sable Ridge
deposition summary, unscheduled, blocked on the Martinez transcript"* is the
summary that is blocked, not the speaker, and is **not** a row.

Three things have to be true:

- **No negation stands between the speaker and the complaint.** *"I'll push
  for the date, no waiting for round-up"* refuses to wait, and *"I've
  escalated to a direct call rather than waiting on email"* chose something
  instead of waiting. **Neither is a row.**
- **No other subject stands between the speaker and the complaint.** *"...
  resolved on my end, and **we're** just waiting on the handbook"* is the
  room waiting. *"...and **Cecile's** waiting on the stipulation language"*
  is Cecile. *"**litigation's** still short the expert fee estimate, waiting
  on that"* is the estimate. **None is a row.** A thing owns a wait as
  readily as a person does.
- **A question is not one.** *"Is anyone waiting on me for that?"* asks; it
  does not report.
- **A wait pointed AT the speaker is not one.** *"so nothing sits waiting on
  me"* and *"the two exceptions are both waiting on me, not on anyone else"*
  say the speaker is what everybody else is waiting for. **Neither is a
  row.** *"waiting on my client's approval"* still is: there the speaker
  waits, and what they wait on merely belongs to them.
- **A wait already over is not one.** *"I **was** waiting on Klara's
  comparison before I'd sign off"* reports a wait that has ended, and the
  brief asks for turns where the speaker says they **are** stuck. *"I've
  been waiting since Tuesday"* has not ended and **is** a row.

Every first-person subject in a clause is tried, not only the first: *"I
haven't gotten written confirmation, so I can't sign off on that schedule"*
is a row, and the complaint belongs to the second **I**.

## What to produce

One file in your workspace: **`blocker_register.json`**, with exactly these
fields:

- `meetings_read` — how many standing meetings you opened: every one inside
  the window, whatever was said in it.
- `turns_read` — how many turns those meetings contained.
- `distinct_owners` — how many different people hold a blocker.

  These three are audit fields. No partner wants them; they are here so a
  reader who sampled the window can be told apart from one who read it, and
  they are reported rather than scored.
- `blockers` — **one entry per person per standing meeting**, sorted by
  `meeting` then `owner`, each with:
  - `owner` — the person's full name
  - `meeting` — the standing meeting's title, exactly as the record gives it
  - `first_raised` — the date they **first** said it in this standing
    meeting, as `YYYY-MM-DD`: the date of the earliest meeting of that
    series in which they reported themselves stuck.
  - `last_raised` — the date they **last** said it, the same way.
  - `raised_count` — how many **meetings** of this series they said it in.
    Not turns: somebody who said it twice in one room said it in one
    meeting. Somebody who said it once has `1`, and their `first_raised`
    and `last_raised` are the same date.
  - `first_meeting_id` — the meeting in which they first said it
  - `last_meeting_id` — the meeting in which they last said it

Note what those three ask of you. None of them is in any sentence. The
first and the last are the ends of a chain you can only place by having
read the whole series, and the count is its length. A reader who finds
every complaint but reads the rooms out of order has all three wrong.

## A warning about completeness

The register is only right if you have read every standing meeting in the
window. There is no index of what is stuck.
