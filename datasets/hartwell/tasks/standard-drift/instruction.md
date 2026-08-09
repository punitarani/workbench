# Playbook drift audit: vendor NDAs

You are **Diane Okonkwo**, of counsel at Hartwell & Marsh LLP. It is late
June 2026 and a vendor-NDA playbook review is going on next quarter's
calendar. Before that meeting you need the drift documented precisely:
where the firm's actual redline practice this spring diverged from the
written playbook, with citations to the exact documents and versions.

Use the firm's systems in this workspace (Gmail, Slack, the iManage
document repository, and Clio matters — wired via `.mcp.json`, with the
underlying SQLite databases under `state/` and repository files under
`files/`). Timestamps in the databases count seconds from the firm's
epoch, Monday 2026-03-02 (day 0): a timestamp's date is 2026-03-02 plus
`time // 86400` days.

Write **`drift.json`** to the workspace root:

```json
{
  "playbook_path": "<iManage path of the vendor NDA playbook>",
  "term": {
    "playbook_standard": "<what the playbook requires for the confidentiality term>",
    "practice": "<what the firm actually agreed to>",
    "document_path": "<iManage path of the vendor NDA whose redline diverged>",
    "version": <version number that introduced the divergence>,
    "date": "<YYYY-MM-DD of that version>"
  },
  "residuals": {
    "playbook_standard": "<the playbook's position on residual-knowledge clauses>",
    "practice": "<what the firm actually agreed to>",
    "document_path": "<iManage path of the vendor NDA whose redline diverged>",
    "version": <version number that introduced the divergence>,
    "date": "<YYYY-MM-DD of that version>"
  }
}
```

Be precise: cite the specific NDA document and the specific version whose
content first departed from the playbook's standard on each clause, not
the emails that talk about it. The playbook states the standards; the
divergence lives in the redline history.
