# Every deadline the firm has promised

You are the practice administrator at **Ashgrove Reid LLP**, an audit and
assurance practice. The partners have asked for something no system in the
firm keeps: a register of every deadline anyone has committed to in
writing.

These promises are not in a field anywhere. Nobody logs them. They exist
only inside the text of messages — *"I'll have that to you by Thursday"*,
*"we'll send the package by the end of next week"*, *"the schedule is
yours EOD"* — and the only way to build the register is to read the mail.

The firm's systems are available through tools: **gmail**, **clio**,
**slack**, **imanage**, and **calendar**.

## What to produce

One file in your workspace: **`commitments.json`**, with exactly these
fields:

- `messages_read` — how many mail messages you examined in total.
- `commitments_total` — how many rows are in `commitments`.
- `messages_with_commitment` — how many distinct messages carry at least
  one.
- `busiest_due_date` — the date the most commitments fall due, as
  `YYYY-MM-DD`. Break a tie by taking the earlier date.
- `top_counterparty` — the counterparty named on the most rows. Break a
  tie alphabetically, earlier first.
- `commitments` — one entry per commitment, sorted by `message_id` then
  `due_date`, each with:
  - `message_id` — the message the promise was made in
  - `due_date` — the date promised, resolved to `YYYY-MM-DD`
  - `author` — the full name of whoever sent that message
  - `sent_date` — the date the message was sent, `YYYY-MM-DD`
  - `counterparty` — the outside organisation on the message, by its
    name as clio records it, or `(none)` if everyone on it works at
    Ashgrove Reid

## What counts as a commitment

Exactly these seven forms, matched case-insensitively anywhere in a
message body. Nothing else counts, however deadline-like it sounds:

| what appears in the text | when it falls due |
|---|---|
| `by Monday` … `by Friday`, with or without `this`/`next` | the **next** such weekday **strictly after** the sent date |
| `by the end of the/this/next week` | the **Friday of the week the message was sent** |
| `by the end of the/this/next month` | the **last day of the month the message was sent** |
| `by <Month> <day>` (`by March 14`) | that date, **in the year the message was sent** |
| `EOD`, `COB`, `end of day`, `close of business` | the **sent date itself** |
| `within N days` / `within N business days`, where N is a digit or one of `a`, `two`, `three`, `five`, `ten` | the sent date **plus N calendar days** — `business` changes nothing |
| `by tomorrow` | the **day after** the sent date |

Two rules that decide a surprising number of rows:

**One row per message and due date.** If a message says `by Friday` twice,
that is one commitment. If it says `by Friday` *and* `EOD`, that is two —
different dates, two rows. If two different forms happen to resolve to the
same date in the same message, that is still one row.

**`next` changes nothing.** `by next Tuesday` resolves exactly as `by
Tuesday` does: the next Tuesday strictly after the sent date. The firm's
people do not use the word consistently and the register does not try to
read their minds.

## Naming the counterparty

A message's counterparty is the outside organisation of anyone on it —
sender, `to`, or `cc` — who does not work at Ashgrove Reid. Give its name
as clio records it, not as its mail domain: match by stripping every
character that is not a letter or a digit from the organisation's name,
lowercasing it, and comparing that to the first label of the address's
domain. `shawassociates.example` is therefore **Shaw & Associates**.

If more than one outside organisation appears, take the alphabetically
earliest name. If everyone on the message works at Ashgrove Reid, the
counterparty is exactly `(none)`.

## A warning about completeness

There is no shortcut. Every figure here depends on having read the body of
every message in the record — not its subject, not its snippet, the body —
and the promises are scattered through roughly half of them. A message
skipped is a row missing, and a row missing costs twice: once in the
register and once in every total computed from it.
