# Promises made in the week of «MEASURE: window start, as a person would say it, e.g. "2 March"»

You are the **docket and calendar manager** at **Merrick Stanton LLP**, a
litigation and transactions firm. You keep the dates the courts set for the
firm. Nobody keeps the dates the firm sets for itself.

Somebody writes *"redline back to you by Thursday"* or *"draft to the client
EOD"*, and then either comes back in time or does not. Those promises are in
the mail and nowhere else — no matter file records them, no calendar holds
them. The partners want one week of them written down, each with the one
fact that settles it: whether the person who wrote it wrote again before it
fell due.

The firm's systems are available through tools: **gmail**, **clio**,
**slack**, **imanage** and **calendar**. Only **mail** is in scope. Chat
makes no rows here, however plainly somebody promises something in it.

## The week

A promise makes a row only if the message carrying it was sent on or between
**«MEASURE: window start — the Monday, YYYY-MM-DD»** and **«MEASURE: window
end — the Friday of the same week, YYYY-MM-DD»**, inclusive. A message sent
before that Monday or after that Friday makes no row, however plainly it
promises something.

`messages_read` counts the mail messages **sent inside those five days** —
the ones you had to read to find the promises. Nothing sent outside the week
needs opening for that figure.

Every date in this brief and in the answer is the firm's own local date, as
the mail itself shows it. A message the mail dates late on the Friday was
sent on that Friday and is inside the week; do not shift it to another
clock before deciding which day it belongs to.

A thread, though, does not stop on Friday. A promise made on Thursday and
falling due the following Wednesday is answered — or not — by a message sent
after the week closed. **Follow each thread that carries a promise forward
as far as that promise's due date, and no further.** Threads that carry no
promise are not part of this question, whenever they run.

## What counts as a promise

Exactly the forms in this table, matched case-insensitively in the **body** of a
mail message. Nothing else counts, however deadline-like it sounds. Where a
form runs to more than one word, any run of whitespace between its words is
the space: two spaces, or a line break, and the form is still the form.

| what appears in the text | key in `form_counts` | when it falls due |
|---|---|---|
| `by Monday` … `by Friday`, with or without `this` or `next` | `by weekday` | the **next** such weekday **strictly after** the date the message was sent |
| `end of week` or `EOW`, with or without `by`, `the`, `this` or `next` | `end of week` | the **Friday of the week the message was sent**, weeks running Monday to Sunday |
| `end of month` or `EOM`, with or without `by`, `the`, `this` or `next` | `end of month` | the **last calendar day of the month the message was sent** |
| `by <Month> <day>` — `by March 14`, `by March 14th` | `by date` | that day of that month, **in the year the message was sent**, even where that date has already gone by |
| `EOD`, `COB`, `end of day`, `close of business` | `end of day` | the **date the message was sent** |
| `within N days` or `within N business days` — singular `day` counts the same — N a digit or one of «MEASURE: which number words the corpus writes after `within` — count `a`, `two`, `three`, `five`, `ten` and any others before fixing this list» | `within days` | the sent date **plus N calendar days**; `business` changes nothing |
| `by tomorrow` | `by tomorrow` | the **day after** the sent date |

«MEASURE: how this firm spells rows two, three and five. Three variants,
and the table above admits only the first:

1. the words *before* the form — `by`, `the`, `this`, `next`;
2. the article *inside* it — `end of **the** week`, `end of **the**
   month`, `end of **the** day`. The table names the bare form only. In
   the mail of a comparable firm in this record the article form appears
   fifteen times and the bare form not once, so this is not a hypothetical:
   whichever way it comes out, the table has to say so;
3. the hyphenated form — `end-of-week`, `end-of-day`. A second corpus
   here writes four of them.

Count all three in the window before fixing the table, and make the table
match the count. A rule that requires a wording the corpus writes once
where it writes another thirty-four times admits one instance of
thirty-five and scores the rest as inventions.»

«MEASURE: `by Saturday` and `by Sunday`. The table names Monday to Friday.
If the window carries weekend weekdays, either admit them in the row above
or say in this brief that they stay out — leaving it unsaid is a coin flip
the reader cannot win.»

«MEASURE: month abbreviations. The table names `by March 14`. If the window
carries `by Mar 14`, the row above has to say whether it counts.»

**The test is textual, not editorial.** A form counts because the words are
in the message, not because anybody was promising anything. *"The scheduling
order closes discovery end of week"* is nobody's promise to anybody, and it
makes a row, because `end of week` is in it. *"We should hear from the court
by Tuesday"* is a guess about somebody else's timetable, and it makes a row
too. Do not weigh up whether a commitment was really made — read the words,
not the intent.

**A form counts wherever it appears, including inside a longer phrase.**
*"I can usually turn these within a day or two"* contains `within a day`, so
it makes a row falling due the next day; the hedge that follows does not
cancel the form that precedes it. *"...by Friday at the latest"* is `by
Friday`. Match the words that are there.

**One row per message and per due date.** A message saying `by Friday` twice
promised one thing and makes one row. A message saying `by Friday` *and*
`EOD` promised two and makes two rows. Two different forms in one message
that resolve to the **same** date make one row.

**`this` and `next` change nothing.** `by next Tuesday` resolves exactly as
`by Tuesday` does: the next Tuesday strictly after the sent date.

## What counts as coming back

`followed_up` is true when **the same author** sent **another message in the
same thread**, at a **later** time than the message carrying the promise, on
a date **on or before** the due date.

Three things decide rows:

- **The due date itself counts.** A promise `by Thursday` answered on
  Thursday was answered in time.
- **It must be the same thread.** The same person writing about the same
  subject in a different thread is not coming back.
- **It must be the same person.** A colleague answering on their behalf is
  not the author coming back, however well it served the client.

## What to produce

One file in your workspace: **`promise_clock.json`**, with exactly these
fields:

- `messages_read` — how many mail messages were sent inside the week.
- `promises_total` — how many rows are in `promises`.
- `answered_in_time` — how many of those rows have `followed_up` true.
- `distinct_authors` — how many different people wrote a message that
  produced a row. Every row, not only the answered ones.
- `form_counts` — an object carrying **one key per row of the table above**,
  each mapped to how many rows it accounts for, **including the forms that
  turn out to be zero**. Every form in the table gets a key whether or not
  the week contains one. Attribute a row to the form listed **first in
  the table**, among the forms in that message that resolve to that row's
  due date.
- `most_unanswered` — the author with the most rows whose `followed_up` is
  false. Break a tie alphabetically, earlier first. If every row was answered
  in time, `null`.
- `promises` — one entry per row, sorted by `ref` and then by `due_date`,
  both compared as text, ascending:
  - `ref` — how the system names the message, an id like `msg-000104`
  - `due_date` — the date the form resolves to, `YYYY-MM-DD`
  - `author` — the full name of whoever sent that message, never an id
  - `sent_date` — the date the message was sent, `YYYY-MM-DD`, in the
    firm's own time
  - `followed_up` — true or false

## A warning about completeness

Every figure depends on having read the **body** of every mail message sent
inside the week — not its subject, not its snippet — and then on having read
each promise's own thread far enough forward to know what came next. The
systems hand messages back a page at a time, and the week holds «MEASURE:
mail messages sent inside the window» of them.
