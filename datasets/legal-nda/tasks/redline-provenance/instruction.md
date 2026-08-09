# Redline provenance

You are Priya Shah, junior counsel. Before you sign off for the day, the
records team needs a provenance note for today's work on the Vantage Data
Services NDA: where the redline edits actually live in the document
repository, who made them, and whether the inbound draft itself was ever
modified.

You have the usual systems in front of you — Gmail, Slack, the iManage
document repository, and Clio. Do not guess from file names: the note has
to match what iManage's revision history actually shows, and records will
check it against the repository.

Save `provenance.json` in your workspace:

```json
{
  "redline_document_path": "<repository path of the document that carries today's redline edits>",
  "author": "<who made the edits>",
  "revisions": [<the revision numbers that contain the redline edits>],
  "inbound_draft_revised": <true|false — was the inbound Vantage draft attachment itself revised today?>
}
```

Answer all four fields, and answer each from the repository rather than
from what today's mail says happened.
