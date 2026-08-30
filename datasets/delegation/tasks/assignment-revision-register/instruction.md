# The assignment register

You are the practice administrator at **Merrick Stanton LLP**, a
litigation-and-transactions firm. The firm's standing meetings are where
work gets handed out. A partner says somebody else will have a thing done
by a day; a fortnight later, in the same standing meeting, they say a
different day. Neither statement is written down anywhere except in the
transcript of the room it was said in.

Before the partner meeting you produce the register of **what has been
handed to whom**: who owes something because they were told to, in which
standing meeting they were told, the date it is due, the date they were
**first** given, and how many earlier versions of that instruction this one
replaced.

The firm's systems are available through tools: **meetings** (transcripts of
what was said), **clio** (matters, users and time entries), **gmail**,
**slack**, **imanage** and **calendar**.

## Where the answers are

**In the transcripts, and only there.** Work handed out loud is not a field
in any system. Clio has assignees and statuses; it does not have "Dov told
Mira Thursday". This register is built by reading what people said.

**The owner of a row is never the person who said the words.** That is the
whole of this task. A reader who keys on the speaker will find every turn
and get every row wrong.

## The window and the meetings

Read the meetings held from
****Monday 5 January 2026**** through
****Tuesday 19 May 2026****, inclusive — ****99****
working days and ****411****
meetings, of which the standing ones are yours to identify.

A meeting is in the window when it **started** inside it; one that runs past
the last day is still that day's meeting.

**Only the firm's standing meetings count.** A standing meeting is one that
recurs: its title appears on **three or more days** inside the window. The
firm also holds one-off working sessions, called to settle a single
question; those are **not** part of this register and make no rows, however
much work is handed out in them.

## What counts as an assignment

A turn is an **assignment** when the person speaking says **somebody else**
will do something, and names **when**. Both have to be present **in the same
clause** — not merely somewhere in the same turn, and not merely in the same
sentence.

The colleague must be named from the firm's own roster, and the words that
hand them the work are the firm's own: *owes*, *owns*, *will*, *'ll*, *has*,
*is*, *needs to*, *committed*, or a possessive that puts the work on them —
*"Mira's reconciliation is due Thursday"*. **A possessive may also hand
work over through an infinitive**: *"the covenant-trigger analysis is
Adaora's to finalize by Wednesday EOD"* is Adaora's row, due Wednesday. An
adverb may stand between the name and the verb: *"Jamal still owes
confirmation, due next Tuesday"* is one row.

**The day belongs to the nearest thing it can belong to.** A later day in
the same clause that another item or another person's calendar owns is not
this assignment's: *"...is Adaora's to finalize by Wednesday EOD, with the
outside counsel spend breakdown due separately Friday"* is due Wednesday,
and *"Lucien owes me the summaries by Wednesday so I can finish before
Aldrete's hearing next Monday"* is due Wednesday too — the Monday is when
a judge sits.

Five things have to be true, and each is a way the same sentence can name a
colleague and a day that have nothing to do with each other:

- **The speaker outranks.** A first-person promise earlier in the clause
  makes any later colleague a purpose clause rather than an assignee.
  *"I'll pull it together today so Fionnuala has them ahead of 9:30
  tomorrow"* is the speaker's own promise. **No row.**
- **A recipient is not an assignee.** *"Dov will send Mira the schedule by
  Friday"* is Dov's row, not Mira's.
- **A relative clause is not an assignment.** *"the schedule that Mira
  needs by Thursday"* describes the schedule.
- **Nobody else's clause stands between the colleague and the day**, and a
  new subject marks one.
- **A question is not an assignment.** *"Can Mira have that by Thursday?"*
  asks; it does not hand anything over.

## Turning what was said into a date

A deadline said out loud is relative. Resolve it against the day the
meeting was held, in the firm's own timezone, and report the calendar date.
`EOD` and `COB` are the day itself; `tomorrow` is the next working day;
a weekday name is the next occurrence of that weekday; `end of week` is
that week's Friday.

## Which one is live

**A colleague holds one live assignment per standing meeting: the most
recent one.**

When the same colleague is handed work again in a later meeting of the same
series, the later statement replaces the earlier one entirely. This is true
**even when the words are the same**: somebody told "EOD" a fortnight ago
and "EOD" again this week owes this week's date, not the old one.

Later means later by **when the meeting started**, not by where the turn
sits in a transcript. A colleague handed the same work twice inside one
meeting was handed it once, and the later turn is the one that counts.

## What to produce

One file in your workspace: **`assignment_register.json`**, with exactly
these fields:

- `meetings_read` — how many standing meetings you opened: every one inside
  the window, whatever was said in it.
- `turns_read` — how many turns those meetings contained.
- `distinct_owners` — how many different people hold a live assignment.
- `superseded_count` — how many assignments a later one replaced, across
  the whole register. **The unit is one assignment per meeting.**
- `assignments` — **one entry per live assignment**, sorted by `meeting`
  then `owner`, each with:
  - `owner` — the colleague's full name, as the firm's roster gives it
  - `meeting` — the standing meeting's title, exactly as the record gives it
  - `due` — the date it is due, as `YYYY-MM-DD`
  - `first_due` — the date this colleague was **first** given in this
    standing meeting, as `YYYY-MM-DD`: their earliest qualifying statement
    in the series, resolved **against the meeting it was said in**.
    Somebody told "EOD" in January and "EOD" in April was given two
    different dates, and this is the January one. Where they were told only
    once, it is the same date as `due`.
  - `superseded` — how many **earlier** assignments this colleague was
    handed in this same standing meeting that this one replaced. Somebody
    told once has `0`.
  - `meeting_id` — the meeting in which they were last told
  - `said_at` — the ISO-8601 start of that meeting

Note what those three ask of you. The **last** statement gives the date
owed. The **first** gives the date originally set. The **count** gives the
length of the chain. A reader who finds one end and stops has one of the
three and cannot get the other two — they are not derivable from each
other, and none of them is in any system here.

## A warning about completeness

The register is only right if you have read every standing meeting in the
window. There is no index of who was told what; the only way to know is to
read the rooms.
