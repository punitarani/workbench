# The state of the file room

You are the quality-control partner at **Ashgrove Reid LLP**, an audit and
assurance practice. Peer review is coming, and the reviewers will ask two
questions of every piece of work product the firm holds: who checked it,
and who outside the firm has seen it. Nobody here can answer either
question today.

The firm's systems are available through tools: **imanage** (the document
repository and its version history), **gmail** (mail, including what was
attached to it), **clio**, **slack**, and **calendar**.

## What to produce

One file in your workspace: **`work_product_review.json`**, with exactly
these fields:

- `documents_total` — how many documents the repository holds.
- `reviewed_count` — how many were reviewed, by the rule below.
- `unreviewed_count` — how many were not.
- `reached_client_count` — how many reached someone outside the firm.
- `never_attached_count` — how many were never attached to any message at
  all, inside the firm or out.
- `documents` — **one entry for every document in the repository**, sorted
  by `document`, each with:
  - `document` — the document's name, as the repository shows it
  - `workspace` — the workspace it lives in
  - `author` — the full name of the person who wrote **version 1**
  - `versions` — its highest version number
  - `reviewed` — `true` if any version after version 1 has a different
    author from version 1's
  - `reached_client` — `true` if any message carrying it as an attachment
    had at least one recipient outside the firm

## The rules

**Review.** A document is reviewed when a second pair of hands has been
through it. Concretely: some version after the first was written by
somebody other than whoever wrote version 1. An author revising their own
draft ten times has still not been reviewed, however many versions that
makes.

**Reaching a client.** A document reached a client when a message it was
attached to had any recipient — `to` or `cc` — who does not work at
Ashgrove Reid. A workpaper circulated among colleagues for review has been
attached to mail and has still not reached anyone outside; it counts as
attached, not as reaching a client.

Decide who is inside the firm from the record's own account of people
rather than by reading email addresses: the directory says who is
internal, and that is the answer even when someone writes from an address
that looks unfamiliar.

**Every document.** The `documents` list covers the whole repository, not
only the interesting rows. A document nobody reviewed and nobody sent
still gets an entry, with `reviewed` and `reached_client` both `false`.
