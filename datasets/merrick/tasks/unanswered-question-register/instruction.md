# The questions nobody answered

You are the practice manager at **Merrick Stanton LLP**, a litigation and
transactions firm.

Things are being dropped in email. Somebody asks a colleague a direct
question, the thread moves on, and the question is never picked up. The
managing partner wants the list before she raises it at the partners'
meeting — not a complaint about anyone, a count of how often it happens.

**This is a record of the thread, not of the answer.** You are not judging
whether a reply was any good, or whether it addressed the question, or
whether the matter got resolved some other way. A reply that says *"no idea,
ask Bennett"* is a reply. A reply is a reply.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**. This register is about **mail
only** — chat is out of scope, and something answered in chat is still
unanswered here.

## The window

Register questions asked **on or before «MEASURE: the last day of the
window, as a weekday and a date — e.g. "Friday 6 February 2026". Two
constraints, and the second one is easy to miss.

(1) Size: the record carries ~5 questions and ~1.5 unanswered per working
day, so four weeks puts ~100 questions in front of the reader for ~30 rows,
near the 213-message load the in-band comparison task settled on.

(2) **The window must close at least three working days before the record's
last day.** A question asked on the final recorded day is unanswered only
because the world stopped: measured on the record, the last day runs
4-for-4 unanswered and the day before 3-of-5, against 1-2 a day everywhere
else. Ending the window at the record's edge grades the edge.»** — the
firm's «MEASURE: how many working days that window is, counted as weekdays
from the record's first day to the boundary above, inclusive. This is *not*
a calendar-day count; the two differ by every weekend inside the window.»
working days.

A question asked after that boundary makes no row.

Which side of the boundary a question falls on is decided by its date in the
firm's own time zone (New York) — the same date this register reports as
`asked_date` — not by UTC and not by any other clock a tool prints.

## What makes a row

A mail message makes a row when **all three** hold.

**One — it asks something.** The message body contains a question mark.
That is the whole test. A message that plainly requests something without
one — *"let me know where this landed"*, *"I'd like your view before
Friday"* — makes **no row**, and a rhetorical question makes one. You are
matching a character, not detecting intent.

**Two — somebody was actually asked.** The message has at least one
recipient in **To**. People in **Cc** are not asked, and a message with
nobody in To makes no row however plainly it asks.

**Three — no addressee replied in time.** No person who was in To sent a
later message **in the same thread** within **three working days** of the
day the question was sent.

Three working days means weekends do not count, and the day the question
was sent is day zero. Worked through, with dates:

- asked **Thursday 8 January** — the three working days are Friday the 9th,
  Monday the 12th and Tuesday the 13th, so a reply any time up to the end of
  **Tuesday the 13th** is in time, and Wednesday the 14th is late.
- asked **Monday 12 January** — the three are Tuesday, Wednesday and
  Thursday, so the deadline is the end of **Thursday the 15th**.

A weekend reply is not late for being on a weekend: it simply does not
consume one of the three.

**A reply from someone who was only in Cc does not answer it.** Neither does
a reply from the asker. Neither does a message in a different thread, however
obviously it responds.

**And a reply that arrives late does not answer it.** Four of the questions
in this record were eventually replied to, after the three working days had
run. Those are rows. "Did anybody ever reply" is a different question from
the one being asked, and it gives a different list.

## The register

Write `unanswered.json` to the workspace root:

The shape, with values shown only to fix the *format* — the boundary and
the counts are whatever the window above and your reading produce, not
these:

```json
{
  "window_end": "<the boundary this brief states, as YYYY-MM-DD>",
  "questions_read": 0,
  "unanswered": [
    {
      "message_ref": "msg-000318",
      "thread_ref": "thr-000042",
      "asker": "Bennett Ashworth",
      "asked_date": "2026-01-21",
      "subject": "Northmoor closing checklist — two open items",
      "addressees": ["Cecile Marchand", "Rosalie Duchamp"]
    }
  ]
}
```

One row per message, however many question marks the body carries. A thread
holding three unanswered questions makes three rows.

`asker` and `addressees` are people's full names as the firm's records give
them, not internal identifiers.

**`addressees` is sorted alphabetically**, and holds every person who was in
To — including any who did reply, as long as no addressee replied in time.

The **rows themselves** are sorted by `message_ref`. Nothing depends on it —
the register is compared as a set — but leaving it unsaid invites three
readers to pick three orders and wonder which was wanted.

`subject` is the message's own subject line, exactly as it stands.

`questions_read` counts the messages inside the window that contain a
question mark and have at least one To recipient — the ones whose threads
you had to walk.

## What is being measured

Whether the register is exactly the rule's output. The expensive mistake is
counting three calendar days instead of three working days; the quiet one is
treating a Cc as an addressee, or letting a late reply close a question.
