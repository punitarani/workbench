# Triage memo: Vantage Data Services NDA

You are **Priya Nair**, Counsel (Privacy) at Argent Systems. It is the end
of Thursday. Daniel handled the inbound Vantage NDA today, but the matter
file is missing its structured triage memo — and you are on matter-hygiene
duty this week.

Using the firm's systems in this workspace (mail, chat, the document
repository, and the matter tracker — wired via `.mcp.json`, with the
underlying SQLite databases under `state/`), reconstruct the
clause-by-clause triage of the **inbound Vantage draft** and write it to
**`triage.json`** in the workspace root:

```json
{
  "clauses": {
    "definition":      {"decision": "...", "basis": "..."},
    "term":            {"decision": "...", "basis": "..."},
    "mutuality":       {"decision": "...", "basis": "..."},
    "non_solicit":     {"decision": "...", "basis": "..."},
    "injunctive_relief": {"decision": "...", "basis": "..."}
  }
}
```

`decision` is one of `accept`, `negotiate`, `reject`. `basis` is one or two
sentences stating the firm's actual position and where it comes from.

Be precise: the memo must reflect the positions the firm actually took
today, not generic best practice. The playbook in the repository covers
some of it; the rest is in today's record.
