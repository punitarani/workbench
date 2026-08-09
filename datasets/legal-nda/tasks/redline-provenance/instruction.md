# Redline provenance

You are Priya Shah, junior counsel. Before signing off for the day, the
records team needs a provenance note for today's work on the Vantage Data
Services NDA: where the redline edits actually live in the document
repository, who made them, and whether the inbound draft itself was ever
modified.

The firm's systems are available as MCP servers (see `.mcp.json`): Gmail,
Slack, the iManage document repository, and Clio matters. Do not guess from
file names — the note must reflect what the repository's revision history
actually records.

Write `provenance.json` in the workspace root:

```json
{
  "redline_document_path": "<repository path of the document that carries today's redline edits>",
  "author": "<who made the edits>",
  "revisions": [<the revision numbers that contain the redline edits>],
  "inbound_draft_revised": <true|false — was the inbound Vantage draft attachment itself revised today?>
}
```

Accuracy against the record is what counts; partial credit is given per
field.
