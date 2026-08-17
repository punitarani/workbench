# Who came back when they said they would

You are the practice administrator at **Ashgrove Reid LLP**, an audit and
assurance practice. The partners have the firm's promises; what they want
now is which of them were answered in time.

Somebody writes *"I'll have that to you by Thursday"* and then either
writes again by Thursday or does not. Neither the promise nor the answer is
recorded anywhere — both are in the mail, and the only way to the report is
to read it.

The firm's systems are available through tools: **gmail**, **clio**,
**slack**, **imanage**, and **calendar**. Only **mail** is in scope here.

## What to produce

One file in your workspace: **`follow_through.json`**, with exactly these
fields:

- `messages_read` — how many mail messages you examined in total.
- `commitments_total` — how many rows are in `commitments`.
- `followed_up_count` — how many were answered in time.
- `unanswered_count` — how many were not.
- `worst_offender` — the author with the most unanswered commitments. Break
  a tie alphabetically, earlier first.
- `commitments` — one entry per commitment, sorted by `message_id` then
  `due_date`:
  - `message_id` — the message the promise was made in
  - `due_date` — the date promised, `YYYY-MM-DD`
  - `author` — the full name of whoever sent that message
  - `sent_date` — the date the message was sent, `YYYY-MM-DD`
  - `followed_up` — true or false

## What counts as a commitment

Exactly these seven forms, matched case-insensitively anywhere in a message
body. Nothing else counts, however deadline-like it sounds:

| what appears in the text | when it falls due |
|---|---|
| `by Monday` … `by Friday`, with or without `this`/`next` | the **next** such weekday **strictly after** the sent date |
| `by the end of the/this/next week` | the **Friday of the week the message was sent** |
| `by the end of the/this/next month` | the **last day of the month the message was sent** |
| `by <Month> <day>` (`by March 14`) | that date, **in the year the message was sent** |
| `EOD`, `COB`, `end of day`, `close of business` | the **sent date itself** |
| `within N days` / `within N business days`, where N is a digit or one of `a`, `two`, `three`, `five`, `ten` | the sent date **plus N calendar days** — `business` changes nothing |
| `by tomorrow` | the **day after** the sent date |

**One row per message and due date.** A message saying `by Friday` twice
promised one thing. A message saying `by Friday` *and* `EOD` promised two,
and gets two rows. Two different forms resolving to the same date in one
message is still one row.

**`next` changes nothing.** `by next Tuesday` resolves exactly as `by
Tuesday` does: the next Tuesday strictly after the sent date.

## What counts as coming back

`followed_up` is true when **the same author** wrote **another message in
the same thread**, **after** the message carrying the promise, and on a
date **on or before** the due date.

Three things that decide rows:

- **The due date itself counts.** A promise `by Thursday` answered on
  Thursday was answered in time.
- **It must be the same thread.** The author writing to somebody else about
  the same subject, in a different thread, is not coming back.
- **It must be the same person.** A colleague answering on their behalf is
  not the author coming back, however well it served the client.

## A warning about completeness

Every figure depends on having read the body of every mail message in the
record, and on having read each thread far enough forward to know what came
next. The tools hand messages back a page at a time.
