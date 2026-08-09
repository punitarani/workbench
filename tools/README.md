# tools

The agent-facing tool systems: projections from the recorded world log into
per-tool SQLite databases, and read-only MCP servers over them. This is the
`workbench-tools` distribution, importable as `workbench.tools`.

Each system is a plugin — a subpackage implementing one typed contract
(`ToolSystem`): the world-log tags it observes, its tables, a projector,
and a server registrar. A single registry (`registry.py`, one line per
system) drives everything downstream: projection, cross-database coherence
checking, server assembly, workspace `.mcp.json` specs, and the stdio
serve entry point.

| System | Database | Read tools |
|---|---|---|
| `mail` | `mail.db` | `list_threads`, `read_thread`, `search_mail` |
| `chat` | `chat.db` | `list_conversations`, `read_conversation`, `search_chat` |
| `dms` | `dms.db` | `list_documents`, `read_document`, `document_history` |
| `matters` | `matters.db` | `list_tickets`, `read_ticket` |

Every server also carries `directory` — the organization's people, projected
into every database so each tool answers "who works here" the same way.

Schemas are typed end to end: `db.py` derives DDL, inserts, and reads from
Pydantic row models, so the schema cannot drift from the types, and `Id`/
`Ref` column markers make cross-database references machine-checkable.

Serve one system over stdio (the container wraps this with
`run-as-environment`):

```bash
python -m workbench.tools.serve mail --db state/mail.db
```

Projection and workspace assembly are usually reached through
`workbench.environment.materialize`, which validates the world log first.
