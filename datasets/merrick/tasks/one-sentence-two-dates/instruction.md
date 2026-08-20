# Dates the firm put in writing

You are covering the docket desk at **Merrick Stanton LLP**, a litigation
and transactions practice. Courts set some of this firm's deadlines and
the docket system holds those. The rest never reach it: somebody names a
date in an email and the matter runs on it until somebody else names a
different one.

The partners want the opening days' mail read for exactly that — every
date the firm's own correspondence put on the record, whoever named it,
and whatever they happened to be doing when they did.

The firm's systems are available through tools: **gmail**, **clio**,
**slack**, **imanage**, and **calendar**. Only **mail** is in scope here.

## The window

Report only dates named in mail sent **on or before «MEASURE: the last
day of the window, written as a weekday and a full date — e.g. Friday 16
January 2026. Take the smallest window whose mail carries at least 12
rows, of which at least 12 are a message's second or later row; the note
on how to count them belongs with the solver, not here»** — the firm's
first **«MEASURE: the number of working days that window covers»**
working days. A message sent after that makes
no row here, however firm the date in it.

`messages_read` counts the mail **inside the window** — the messages you
actually had to read. Nothing sent later is part of this question, and
there is no need to open it.

Every date in this brief and in the answer is the firm's own local date,
as the mail itself shows it. A message the mail dates late on the last
day of the window was sent on that day and is inside it; do not shift it
to another clock before deciding which day it belongs to.

## What names a date

Exactly these forms, matched case-insensitively, anywhere in a message
body. Nothing else names a date, however plainly a sentence fixes one.
Where a form runs to more than one word, any run of whitespace between
its words is the space: two spaces, or a line break, and the form is
still the form.

| what appears in the text | still counts carrying | `at` points at | when it falls due |
|---|---|---|---|
| `by Monday` … `by Friday` | `this` or `next` between the two words — `by next Tuesday` | the `b` of `by` | the **next** such weekday **strictly after** the sent date |
| `end of week`, `EOW` | a preceding `by`, `the`, `this` or `next` | the `e` of `end`, or the `E` of `EOW` | the **Friday of the week the message was sent**, weeks running Monday to Sunday |
| `end of month`, `EOM` | the same preceding words | the `e` of `end`, or the `E` of `EOM` | the **last day of the month the message was sent** |
| `by <Month> <day>`, the month spelled in full — `by March 14`, `by March 14th` | the ordinal suffix | the `b` of `by` | **that date, in the year the message was sent**, even where that date has already gone by |
| `EOD`, `COB`, `end of day`, `close of business` | — | the first character of the form | the **sent date itself** |
| `within N days`, `within N business days`, N written in digits or as one of `a`, `two`, `three`, `five`, `ten` | `business`, and the singular `day` for `days` | the `w` of `within` | the sent date **plus N calendar days** — `business` changes nothing |
| `by tomorrow` | — | the `b` of `by` | the **day after** the sent date |

«MEASURE: the table itself. Count how this firm writes dates before this
vocabulary is fixed — strike any form the window never carries, and add
any form it writes often that this table omits. A rule requiring a word
the corpus does not use admits a fraction of the real instances and
scores the rest as inventions. The `within` numerals are a guess until
they are a count, and so is the month-and-day form. Two candidates in
particular, both shut out below: `by Saturday` / `by Sunday`, and the
abbreviated month `by Mar 14`. If the window writes either of them often,
admit it in the table above rather than leaving the rule to score real
instances as inventions — and delete the paragraph that excludes it.»

**`next` changes nothing.** `by next Tuesday` falls due exactly where `by
Tuesday` does: the next Tuesday strictly after the sent date.

**A date the calendar does not have is not a date.** `by February 30`
makes no row.

**Only the five working weekdays are on the list.** `by Saturday` and `by
Sunday` are not forms and name nothing. (A due date *resolved* from one of
the forms above may still land on a weekend — that is a different matter,
and it is covered below.)

**The month is spelled in full.** Only `by March 14` is the form. `by Mar
14` is not, and neither is `by 14 March`.

**The test is textual, not editorial.** A form counts because the words
are there, whatever the sentence is doing with them. *"There's no way
we're filing by Friday"* names Friday. *"Can you get me the exhibit list
by tomorrow?"* names tomorrow. *"We agreed EOD and they blew through
it"* names the sent date. A question, a refusal, a complaint and a
recollection all count exactly as a promise does. Do not weigh up whether
anybody undertook anything.

**A form counts inside a longer phrase.** *"I can usually turn these
within a day or two"* contains `within a day`, so it names the day after
the sent date; the hedge that follows does not remove the form in front
of it. *"reply by end of day tomorrow"* contains `end of day`, so it
names the sent date — the word after the form does not move it. Match
the words that are there.

## One row per date, not one row per message

A message makes one row for **each distinct date its forms fall on**.

- **Two forms falling on the same date are one row.** *"Friday works —
  by Friday, end of week at the latest"*, sent on a Tuesday, names that
  Friday twice over. One row.
- **Two forms falling on different dates are two rows.** *"I'll have the
  redline over by Thursday, end of week at the outside"* names Thursday
  and it names Friday. Both go in.
- **The same sentence changes nothing.** The two forms above sit in one
  sentence, and that has no bearing on it: two dates, two rows.
- **A second form that reads as an explanation of the first is still a
  second row.** *"Get it to me by tomorrow — EOD if you can manage it"*
  reads as one deadline stated twice, and it is two dates: the day after,
  and the day of. Two rows.
- **The same form twice is one row.** A message saying `by Friday` in the
  first line and again in the last named one date.

Do not decide which date the writer really meant, or whether the second
was a correction, a softening or a gloss of the first. Two different
dates in the text are two rows in the register.

## Where `at` points

`at` is a **character position in the message's plain-text body** — the
position of the first character of the form, as the **`at` points at**
column of the table above names it.

Count from **0**: the first character of the body is position 0. Count
**characters, not bytes**, and count every character the body contains,
including spaces and line breaks, exactly as the body comes back.

Where two forms fall on the same date, the row carries the position of
the **earlier of them in the text** — the leftmost.

## Two forms in one sentence

`same_sentence_pairs` counts **pairs of rows**, from the same message,
with no sentence ending anywhere between their two positions.

A sentence ends at a full stop, a question mark, an exclamation mark, or
a line break — `.`, `?`, `!`, or the end of a line. Nothing else ends
one: not a semicolon, not a colon, not a dash, not a comma. **The test is
the character, not the grammar** — a full stop inside an abbreviation or
a number ends a sentence here exactly as any other full stop does.

Count pairs, not messages: a message with three rows whose forms all sit
in one sentence contributes three pairs. Rows in different messages are
never a pair.

## What to produce

One file in your workspace: **`date_register.json`**, with exactly these
fields:

- `messages_read` — how many mail messages the window holds: every
  message sent on or before its last day, whether or not it named a date.
  Nothing sent after it counts, whether or not you opened it.
- `rows_total` — how many rows are in `dates`.
- `messages_with_dates` — how many different messages produced at least
  one row.
- `same_sentence_pairs` — as defined above.
- `distinct_authors` — how many different people wrote a message that
  produced a row.
- `top_author` — the person on the most rows. Break a tie
  alphabetically, earlier first.
- `due_weekday_counts` — an object keyed by weekday, each key mapped to
  **how many rows of `dates`** have a due date falling on that weekday.
  Rows, not distinct dates: two rows falling on the same day count twice.
  Give **all seven** keys, spelled and capitalised exactly `Monday`,
  `Tuesday`, `Wednesday`, `Thursday`, `Friday`, `Saturday`, `Sunday`, and
  give a `0` for any weekday no row falls on. A due date may land on a
  weekend; that is a Saturday or a Sunday like any other.
- `dates` — one entry per row, sorted by `ref` ascending and, within one
  `ref`, by `at` ascending. `ref` is compared as text:
  - `ref` — how the message's own system names it, an id like
    `msg-000104`
  - `at` — the character position, as above, as a number
  - `due_date` — the date the form falls on, `YYYY-MM-DD`
  - `author` — the full name of whoever wrote the message
  - `sent_date` — the date the message was written, `YYYY-MM-DD`, in the
    firm's own time

Mail identifies its senders by an internal id. Resolve each through the
directory — `author` is a person's full name, never an id.

## A warning about completeness

Every figure here depends on having read the **body** of every mail
message in the window, not its subject and not its snippet, and on having
read each body to the end. A message's second date is usually further
down than its first. The systems hand messages back a page at a time, and
there are «MEASURE: how many mail messages sit inside the window» of them
in the window.
