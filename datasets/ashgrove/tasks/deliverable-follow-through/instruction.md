# Work product the client never received

You are the quality manager at **Ashgrove Reid LLP**, an audit and
assurance practice. Before the partner meeting you need to know what the
firm has actually delivered, as against what it has merely produced. Work
that sits finished in the document repository and never reaches the
client is the failure this review is looking for.

The firm's systems are available through tools: **imanage** (the document
repository), **gmail** (firm-wide mail), **clio** (engagements, time),
**slack**, and **calendar**.

## What to produce

One file in your workspace: **`follow_through.json`**, with exactly these
fields:

- `documents_in_repository` — how many documents the repository holds.
- `delivered_count` — how many of them reached someone outside the firm.
- `internal_only_count` — how many were attached to mail that never left
  the firm.
- `never_attached_count` — how many were never attached to any mail.
- `undelivered` — one entry per document that did **not** reach anyone
  outside the firm, sorted by `document`, each with:
  - `document` — the document's name as the repository shows it
  - `author` — the full name of whoever wrote it
  - `workspace` — the repository workspace it sits in
  - `attached_internally` — `true` if it was attached to firm-internal
    mail, `false` if it was never attached to anything

## How the firm counts delivery

A document is **delivered** when it is attached to a mail message that
has at least one recipient outside Ashgrove. A recipient counts whether
they are on the To or the Cc line.

Two things follow, and both matter:

- Attaching a document to internal mail is not delivery. A workpaper
  circulated among the team for review has not reached the client, and it
  belongs in `undelivered` with `attached_internally` set to `true`.
- A document attached to several messages is delivered if **any** of
  them left the firm.

Every document in the repository counts, including the firm's standing
templates and policies. Some of those are never meant to go out; the
report says what is true, and the partners decide what to do about it.
