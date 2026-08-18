# Every deadline promised in the opening days

You are the practice administrator at **Ashgrove Reid LLP**, an audit and
assurance practice. The partners have asked for something no system in the
firm keeps: a register of every deadline anyone has committed to in
writing.

These promises are not in a field anywhere. Nobody logs them. They exist
only inside the text of messages — *"I'll have that to you by Thursday"*,
*"we'll send the package by the end of next week"*, *"the schedule is
yours EOD"* — and the only way to build the register is to read the
traffic. Both kinds of it: the firm makes as many promises to itself in
chat as it makes to its clients by mail.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**.

## What to produce

One file in your workspace: **`opening_commitments.json`**, with exactly these
fields:

- `messages_read` — how many messages you examined in total, mail and chat
  together.
- `commitments_total` — how many rows are in `commitments`.
- `messages_with_commitment` — how many distinct messages carry at least
  one.
- `busiest_due_date` — the date the most commitments fall due, as
  `YYYY-MM-DD`. Break a tie by taking the earlier date.
- `top_made_to` — the value appearing on the most rows in `made_to`. Break
  a tie alphabetically, earlier first.
- `commitments` — one entry per commitment, sorted by `ref` then
  `due_date`, each with:
  - `ref` — how the message's own system names it (see below)
  - `due_date` — the date promised, resolved to `YYYY-MM-DD`
  - `author` — the full name of whoever wrote the message
  - `sent_date` — the date it was written, `YYYY-MM-DD`
  - `made_to` — who the promise was made to (see below)

## The window

Report only the commitments made in messages sent **on or before Tuesday
6 January 2026** — the firm's first two working days. A message sent on
the 7th or later makes no row here, however plainly it promises
something. Due dates are resolved as always, against the day the message
was written, and many of them fall well outside the window; that is
expected and does not exclude the row.

`messages_read` counts the messages **inside the window** — the ones you
actually had to read. Nothing sent later needs opening.

## What counts as a commitment

Exactly these seven forms, matched case-insensitively anywhere in a
message body. The test is **textual, not editorial**, and it cuts both
ways: nothing else counts however deadline-like it sounds, and everything
that does count counts however little it reads like a promise. *"Harbor
Light closes end of week"* is nobody's commitment to anything, and it goes
in the register, because the words are there. Do not filter by whether
someone was promising.

| what appears in the text | when it falls due |
|---|---|
| `by Monday` … `by Friday`, with or without `this`/`next` | the **next** such weekday **strictly after** the sent date |
| `end of week` or `EOW`, with or without `by`, `the`, `this` or `next` | the **Friday of the week the message was sent** |
| `end of month` or `EOM`, with or without `by`, `the`, `this` or `next` | the **last day of the month the message was sent** |
| `by <Month> <day>` (`by March 14`, `by March 14th`) | that date, **in the year the message was sent** |
| `EOD`, `COB`, `end of day`, `close of business` | the **sent date itself** |
| `within N days` / `within N business days`, where N is a digit or one of `a`, `two`, `three`, `five`, `ten` | the sent date **plus N calendar days** — `business` changes nothing |
| `by tomorrow` | the **day after** the sent date |

**A form counts wherever it appears, including inside a longer phrase.**
*"I can usually sort these within a day or two"* contains `within a day`,
so it is a commitment due the next day — the hedge that follows does not
remove the form that precedes it. Match the words that are there; do not
decide the writer was being approximate.

Two rules that decide a surprising number of rows:

**One row per message and due date.** If a message says `by Friday` twice,
that is one commitment. If it says `by Friday` *and* `EOD`, that is two —
different dates, two rows. If two different forms happen to resolve to the
same date in the same message, that is still one row.

**`next` changes nothing.** `by next Tuesday` resolves exactly as `by
Tuesday` does: the next Tuesday strictly after the sent date. The firm's
people do not use the word consistently and the register does not try to
read their minds.

## Naming a message

Give each message the name **its own system uses**, exactly as that system
hands it to you:

- **Mail** identifies a message by an id like `msg-000104`. Use it.
- **Chat** has no such id on the wire. Slack addresses a message by its
  timestamp, a string like `1767661500.000003`. Use that, unchanged —
  every digit, including the trailing zeros.

## Naming who it was made to

- A **mail** message with anyone from outside Ashgrove Reid on it — sender,
  `to`, or `cc` — was made to that outside organisation. Give its name as
  clio records it, not as its mail domain: match by stripping every
  character that is not a letter or a digit from the organisation's name,
  lowercasing it, and comparing that to the first label of the address's
  domain. `shawassociates.example` is therefore **Shaw & Associates**. If
  more than one outside organisation appears, take the alphabetically
  earliest name.
- A **mail** message where everyone works at Ashgrove Reid was made to
  exactly `the firm`.
- A **chat** message was made to the channel it was posted in, by that
  channel's name.

Chat identifies its authors by Slack user id rather than by name. Resolve
each one through the directory — `author` is the person's full name, never
the id.

## A warning about completeness

There is no shortcut. Every figure here depends on having read the body of
every message in the record — not its subject, not its snippet, the body —
across both systems, and the promises are scattered through hundreds of
them. A message skipped is a row missing, and a row missing costs twice:
once in the register and once in every total computed from it.
