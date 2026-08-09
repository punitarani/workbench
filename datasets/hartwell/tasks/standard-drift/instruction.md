# Playbook drift audit: vendor NDAs

You are **Diane Okonkwo**, of counsel at Hartwell & Marsh LLP. It is late
June 2026 and a vendor-NDA playbook review is going on next quarter's
calendar. Before that meeting you need the drift documented precisely —
and completely. The review will certify every vendor NDA on file, so the
audit must say, for each one, whether its history conforms to the
written playbook or departs from it, and for the departures, exactly
which document, which version, and which clause.

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
  "ndas": {
    "<iManage path of a vendor NDA>": "conforms" | "deviates"
  },
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

`ndas` is the certification: one entry for **every** vendor NDA in the
repository, keyed by its exact iManage path, valued `"conforms"` when
every version of that NDA holds the playbook's standard positions and
`"deviates"` when any version departs from them. The certification is
graded as a whole — a missing NDA, an invented one, or a single wrong
call forfeits it — so do not sample, and do not trust the email trail
to tell you which files moved: the record discusses some departures and
never mentions others.

For the two clause blocks, be precise: cite the specific NDA document
and the specific version whose content first departed from the
playbook's standard on each clause, not the emails that talk about it.
The playbook states the standards; the divergence lives in the redline
history.
