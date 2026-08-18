# The approvals on file

You are the quality partner at **Ashgrove Reid LLP**, an audit and assurance
practice. The peer reviewers want the firm's approval trail: who approved
what, in writing, and where it is recorded.

An approval has to be an approval. A colleague replying *"sounds good"* has
agreed with you; they have not approved anything, and a reviewer reading
the file will not accept the one as the other. So this register admits a
short, fixed list of words and nothing else.

The firm's systems are available through tools: **gmail**, **slack**,
**clio**, **imanage**, and **calendar**.

## What counts as an approval

A message is an approval when its body contains any of these six forms,
matched case-insensitively, anywhere in the text:

| form | matches |
|---|---|
| `approved` | the word *approved* |
| `i approve` | the phrase *I approve* |
| `signed off` | the phrase *signed off* |
| `sign-off` | *sign-off*, *sign off* or *signoff*, singular or plural |
| `authorised` | *authorise*, *authorised*, *authorize*, *authorized* |
| `cleared` | the word *cleared* |

**The test is textual, not editorial.** A message counts when one of the
six words is in it, whatever the sentence is doing with it. *"Sign-off
protocol once substantive testing wraps"* sets out a procedure; *"for any
items without documented client sign-off"* reports the absence of one.
Both carry the form and both are rows here. Do not weigh up whether
anybody actually approved anything — read the words, not the intent.

Nothing else counts. Not *agreed*, not *go ahead*, not *fine by me*, not
*confirmed*, not *no objection* — however plainly the writer meant to
approve something.

**One row per message**, however many of the six it contains. For
`form_counts`, a message carrying more than one counts once, under
whichever form appears **first in the table above** — not first in the
text.

## What to produce

One file in your workspace: **`approvals.json`**, with exactly these
fields:

- `messages_read` — how many messages you examined, mail and chat together.
- `approvals_total` — how many rows are in `approvals`.
- `distinct_approvers` — how many different people gave one.
- `form_counts` — an object with **all six** forms as keys, each mapped to
  how many rows carry it. A form nobody used is present with `0`.
- `top_approver` — the person on the most rows. Break a tie alphabetically,
  earlier first.
- `approvals` — one entry per approving message, sorted by `ref`:
  - `ref` — how the message's own system names it. **Mail** uses an id like
    `msg-000104`. **Chat** has no such id on the wire: Slack addresses a
    message by its timestamp, a string like `1767661500.000003`. Use that,
    unchanged, every digit.
  - `approver` — the full name of whoever wrote the message
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
directory — `approver` is a person's full name, never an id.

## A warning about completeness

Every figure here depends on having read the body of every message in the
record, mail and chat, not its subject or its snippet. The systems hand
them back a page at a time and there are well over a thousand.
