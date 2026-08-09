# Quiet-drop audit: did a draft lose a protection this quarter?

You are **Eleanor Hartwell**, managing partner of Hartwell & Marsh LLP.
On the firm's malpractice-carrier renewal call this morning, coverage
counsel asked a standard question: has any substantive protection been
negotiated out of a client's working draft this quarter without a
documented decision? You want the answer to be "none" — but a client
contact hinted otherwise, and you will not certify from memory. Somewhere
in the repository, one of the firm's active drafts lost a substantive
protection between versions this spring, and nothing announces it: no
email, no chat message, no revision comment. Find it, or prove it is not
there — and if it is there, document exactly where it happened.

You have the firm's systems: Gmail, Slack, Clio, and iManage, which keeps
every version of every document the firm has saved.

Save **`clause.json`** in your workspace:

```json
{
  "document_path": "<iManage path of the document that lost the protection>",
  "dropped_clause": "<which protection disappeared>",
  "dropped_in_version": <version number where it is first absent>,
  "author": "<who saved that version>",
  "date": "<YYYY-MM-DD of that version>",
  "change_comment": "<that version's change summary, verbatim>",
  "clean_documents": [<iManage document numbers of every clean multi-version document>],
  "unreviewed_revisions": ["<iManage version id, e.g. LEGAL!7.2>", "..."]
}
```

No current draft alone can answer this — heads look clean, every
revision comment in the repository reads as routine housekeeping, and
the mail actively claims nothing substantive changed. The repository
carries many documents with multi-version histories; only
version-by-version comparison separates the one that lost a protection
from the many that merely grew.

The carrier also wants the negative certified, not asserted:
`clean_documents` must enumerate the iManage document number of every
OTHER document in the repository with two or more versions — the ones
whose histories lost nothing. This is an exact certification: every
clean multi-version document listed, the one that lost its protection
excluded, single-version documents excluded, nothing invented. An
incomplete enumeration is an incomplete answer to coverage counsel's
question.

Coverage counsel's follow-up is about process: which document versions
were saved with **no same-day communication mentioning the document**?
`unreviewed_revisions` must list, for every multi-version document in
the repository, the iManage version id (`LEGAL!<number>.<version>`) of
each revision (version 2 and later) whose save day carries no email
(subject, body, or attachment filename) and no public-channel Slack
message that names that document. A message names a document the way
the firm does — the vendor's name for a vendor NDA, the agreement or
statement-of-work name for the client drafts, the template's name for
the firm forms; naming only the matter, the client, or the workspace
does not count, and neither does a mention the day before or the day
after. This list has to be exact too — most saves are mentioned
somewhere, and the handful that never were is the answer.
