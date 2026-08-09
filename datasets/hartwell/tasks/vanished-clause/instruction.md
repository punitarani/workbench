# Pre-signing check: the Lumen license agreement

You are **June Akana**, general counsel of Lumen Software. Your board
approved the Fathom Systems license in June 2026 and outside counsel says
the draft in the workspace is the signing version, with only
"cross-reference and formatting cleanup" since your April comments. Your
April comments said the indemnification article was exactly what you
wanted. Before signature packets go out, verify that — and if any
substantive protection quietly disappeared from the draft, document
exactly where it happened.

Use the firm's systems in this workspace (Gmail, Slack, the iManage
document repository, and Clio matters — wired via `.mcp.json`, with the
underlying SQLite databases under `state/` and repository files under
`files/`). Timestamps in the databases count seconds from the firm's
epoch, Monday 2026-03-02 (day 0): a timestamp's date is 2026-03-02 plus
`time // 86400` days.

Write **`clause.json`** to the workspace root:

```json
{
  "document_path": "<iManage path of the agreement>",
  "dropped_clause": "<which protection disappeared>",
  "dropped_in_version": <version number where it is first absent>,
  "author": "<who saved that version>",
  "date": "<YYYY-MM-DD of that version>",
  "change_comment": "<that version's change summary, verbatim>"
}
```

The current draft alone cannot answer this — nothing in it is marked as
removed, and no email announces the change. Compare the version history.
