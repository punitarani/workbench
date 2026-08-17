# Which workpapers were only reviewed on paper

You are the quality partner at **Ashgrove Reid LLP**, an audit and assurance
practice. Before the peer reviewers arrive you want to know where the file
room says work was reviewed and the record does not bear it out.

Self-review is the oldest independence problem there is. Someone prepares a
workpaper, saves a new version, types *"reviewed and approved"* in the
version comment, and no second person ever touches it. The file reads as
reviewed. It was not.

The firm's systems are available through tools: **imanage** (the document
repository), plus **gmail**, **clio**, **slack**, and **calendar**.

## What to produce

One file in your workspace: **`self_review.json`**, with exactly these
fields:

- `documents_total` — how many documents are in the repository.
- `self_review_risk_count` — how many are at self-review risk.
- `at_risk` — the `document_number` of every at-risk document, ascending.
- `documents` — one entry per document, sorted by `document_number`:
  - `document_number` — iManage's own number for it, as an integer. The
    repository shows a document as `LEGAL!52.1`: `52` is the number and `1`
    is the version. Give the number.
  - `document` — its name, as the repository shows it
  - `preparer` — the full name of the author of **version 1**
  - `versions` — the highest version number it has
  - `distinct_authors` — how many different people appear as the author of
    any of its versions
  - `self_review_risk` — true or false

## The three rules, and they are not the same rule

**A review is *claimed*** when the comment on **any** version of the
document contains any of these, matched case-insensitively anywhere in the
text: `review`, `approv`, `sign off`, `sign-off`, `signed off`, `checked`,
`second pair`, `quality control`, `QC`. That is a fact about what somebody
typed.

**A review is *independent*** when some version after the first has a
**different author** from the author of version 1. That is a fact about who
touched the file.

**A document is at *self-review risk*** when a review is claimed and no
independent review happened.

These are three separate questions. `get_document_versions` returns every
version of a document with both its `author_description` and its
`comment`.

Nothing outside the version comments counts as a claim. A review discussed
in an email, minuted in a meeting, or logged as time does not make a
document's review claimed here.

## A warning about completeness

Every document in the repository belongs in the report, including the ones
where nothing happened at all — a workpaper nobody revised and nobody
claimed to review is still a row. The repository hands its documents back a
page at a time, and every count here is computed from all of them.
