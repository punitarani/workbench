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

Use the firm's systems in this workspace (Gmail, Slack, the iManage
document repository, and Clio matters — wired via `.mcp.json`, with the
underlying SQLite databases under `state/` and repository files under
`files/`). Timestamps in the databases count seconds from the firm's
epoch, Monday 2026-03-02 (day 0): a timestamp's date is 2026-03-02 plus
`time // 86400` days.

Write **`clause.json`** to the workspace root:

```json
{
  "document_path": "<iManage path of the document that lost the protection>",
  "dropped_clause": "<which protection disappeared>",
  "dropped_in_version": <version number where it is first absent>,
  "author": "<who saved that version>",
  "date": "<YYYY-MM-DD of that version>",
  "change_comment": "<that version's change summary, verbatim>"
}
```

No current draft alone can answer this — heads look clean, every
revision comment in the repository reads as routine housekeeping, and
the email record actively claims nothing substantive changed. The
repository carries many documents with multi-version histories; only
version-by-version comparison separates the one that lost a protection
from the many that merely grew.
