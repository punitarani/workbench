# Work reported complete in the opening days

You are the practice administrator at **Ashgrove Reid LLP**, an audit and
assurance practice. The partners want a register of every time someone
reported a piece of work complete, in writing.

The register admits **one word, in its two spellings**, and nothing else.
That is a narrower net than the idea it is named after, and deliberately
so: the firm's traffic is full of people saying work is finished, wrapped
up, closed out, delivered or issued, and none of those goes in.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**.

## The window

Report only claims made in messages sent **on or before Tuesday 6 January
2026** — the firm's first two working days. A message sent on the 7th or
later makes no row here, however plainly it reports work complete.

`messages_read` still counts **every** message in the record, mail and
chat, not merely those inside the window: it says whether you examined
the whole traffic before narrowing it.

## What counts as a completion claim

A message is a completion claim when its body contains either of these two
forms, matched case-insensitively, anywhere in the text:

| form | matches |
|---|---|
| `complete` | the word *complete* |
| `completed` | the word *completed* |

Nothing else counts, and that cuts two ways.

No **synonym** counts. Not *finished*, not *done*, not *wrapped up*, not
*closed out*, not *finalised*, not *delivered*, not *issued* — however
plainly the writer is reporting the same thing. Seventy messages in the
record say one of those and never say *complete*, and every one of them
stays out.

No **other form of the word** counts either. *Completes*, *completing* and
*completion* are not the two spellings named above, so a message carrying
only one of those is not a claim. *Completion* alone appears fifty times.

**One row per message**, however many times either form appears. For
`form_counts`, a message carrying both counts once, under `complete`.

## What to produce

One file in your workspace: **`opening_claims.json`**, with exactly these
fields:

- `messages_read` — how many messages you examined, mail and chat together.
- `claims_total` — how many rows are in `claims`.
- `distinct_claimants` — how many different people made one.
- `form_counts` — an object with **both** forms as keys, each mapped to how
  many rows carry it.
- `top_claimant` — the person on the most rows. Break a tie alphabetically,
  earlier first.
- `claims` — one entry per claiming message, sorted by `ref`:
  - `ref` — how the message's own system names it. **Mail** uses an id like
    `msg-000104`. **Chat** has no such id on the wire: Slack addresses a
    message by its timestamp, a string like `1767661500.000003`. Use that,
    unchanged, every digit.
  - `claimant` — the full name of whoever wrote the message
  - `sent_date` — the date it was written, `YYYY-MM-DD`
  - `where` — for a **mail** message with anyone from outside Ashgrove Reid
    on it, that outside organisation's name as clio records it: match by
    stripping every non-alphanumeric character from the organisation's
    name, lowercasing, and comparing to the first label of the address's
    domain, so `shawassociates.example` is **Shaw & Associates**. If more
    than one appears, take the alphabetically earliest. For a mail message
    where everyone works at Ashgrove Reid, exactly `the firm`. For a
    **chat** message, the channel's name.

Chat identifies its authors by Slack user id. Resolve each through the
directory — `claimant` is a person's full name, never an id.

## A warning about completeness

Every figure here depends on having read the body of every message in the
record, mail and chat, not its subject or its snippet. The systems hand
them back a page at a time and there are well over a thousand.
