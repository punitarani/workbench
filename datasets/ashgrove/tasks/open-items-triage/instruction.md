# Open-items triage — what still needs the firm

You are the engagement-support associate at **Ashgrove Reid LLP**, an
audit and assurance practice. It is the end of the record and the
partners want to know what has been left sitting with the firm before
the next status meeting.

The firm's systems are available through tools: **gmail** (firm-wide
mail), **clio** (engagements, notes, time), **slack**, **calendar**, and
**imanage** (documents).

## What to produce

One file in your workspace: **`open_items.json`**, with exactly these
fields:

- `threads_reviewed` — how many mail threads exist in the record.
- `awaiting_firm_count` — how many of them are awaiting the firm, by the
  rule below.
- `closed_by_client_courtesy` — how many threads end with a client
  message that does **not** meet the rule (a thank-you, an
  acknowledgement, a confirmation with nothing asked).
- `awaiting_firm` — one entry per awaiting thread, sorted by
  `thread_id`, each with:
  - `thread_id`
  - `message_id` — the client's last message in that thread
  - `client` — the sender's full name
  - `subject` — the subject line of **that message** (the one named in
    `message_id`), with any `Re:`/`RE:`/`Fwd:` prefix removed. Subjects
    drift as a thread runs, so take it from the message you are
    reporting, not from the message that opened the thread.
  - `messages_in_thread` — total messages in the thread

## The rule (apply it exactly)

A thread is **awaiting the firm** when both hold:

1. The **last** message in the thread was sent by someone outside the
   firm (a client contact), and
2. that message **asks for something** — it contains a question mark, or
   any of these phrases (case-insensitive):
   `please send`, `please provide`, `please confirm`, `could you`,
   `can you`, `would you`, `we need`, `i need`, `when will`,
   `let me know`, `waiting on`, `waiting for`.

**The phrase test is textual, not editorial.** A phrase counts wherever
it occurs, including inside a longer clause and including when the client
is describing their *own* obligations rather than asking anything of you.
*"I want to confirm we're aligned on what we need to deliver"* contains
`we need`, so the thread is awaiting the firm — do not weigh up who
actually owes whom. Read the words, not the intent.

A thread whose last message is from a client but matches none of those
is a courtesy close, not an open item. A thread whose last message came
from inside the firm is not awaiting the firm at all, however unresolved
it may read.

Completeness is the point: every thread in the record must be
considered, and the awaiting set must be exactly right — a thread missed
and a thread wrongly included both count against you.
