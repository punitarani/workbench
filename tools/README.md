# tools

The agent-facing tool systems: projections from the recorded world log into
per-tool SQLite databases, and read-only MCP servers over them. This is the
`workbench-tools` distribution, importable as `workbench.tools`.

Each system is a plugin — a subpackage implementing one typed contract
(`ToolSystem`): the world-log tags it observes, its tables, a projector,
and a server registrar. A single registry (`registry.py`, one line per
system) drives everything downstream: projection, cross-database coherence
checking, server assembly, the environment bundle's `mcp.json` specs, and
the stdio
serve entry point.

| System | Database | Mirrors | Read tools |
|---|---|---|---|
| `gmail` | `gmail.db` | Google's official Gmail MCP | `search_threads`, `get_thread`, `get_message`, `list_labels` |
| `slack` | `slack.db` | Slack's official MCP | `slack_search_public`, `slack_search_public_and_private`, `slack_read_channel`, `slack_read_thread`, `slack_search_channels`, `slack_search_users`, `slack_read_user_profile`, `slack_list_channel_members`, `slack_get_reactions` |
| `imanage` | `imanage.db` | official iManage MCP | `search`, `search_workspaces`, `get_workspace_profile`, `get_container_children`, `get_document_profile`, `get_document_versions`, `download_document`, `get_libraries`, `get_user_information` |
| `clio` | `clio.db` | Clio Manage API v4 (no official MCP exists) | `list_matters`, `get_matter`, `list_matter_contacts`, `list_contacts`, `list_activities`, `list_notes`, `list_users`, `who_am_i` |
| `calendar` | `calendar.db` | Google's official Calendar MCP (read half) | `list_events`, `get_event`, `list_calendars` |

Slack ships two search tools and so does this one: `slack_search_public`
sees channels, `slack_search_public_and_private` also sees the dms the
caller belongs to. iManage `search` spans every document version, so each
hit reports `matched_versions` and `in_head` — a match on text the head
version no longer contains says so rather than passing for current.

People surface through each product's own user tools; the shared people
table stays in every database as their projection source. The seat comes
from `WORKBENCH_SEAT` (`serve --user`), read at call time via
`framework.seat()`, and each system honors it the way its product would:

| System | With a seat | Unset |
|---|---|---|
| `gmail` | one mailbox; `labelIds` are INBOX/SENT per seat | org-wide, no labels |
| `slack` | only conversations the seat joined, dms included | workspace-wide |
| `imanage` | firm-wide documents; `get_user_information("")` is the seat | firm-wide, everyone |
| `clio` | `who_am_i` is the seat | `who_am_i` errors rather than guess |
| `calendar` | `primary` is the seat's calendar | `primary` means every calendar |

Schemas are typed end to end: `db.py` derives DDL, inserts, and reads from
Pydantic row models, so the schema cannot drift from the types, and `Id`/
`Ref` column markers make cross-database references machine-checkable.

Serve one system over stdio, from the bundle root (the container wraps this
with `run-as-environment`, so the database is readable only by the
`environment` user and the tools are the sole aperture onto it):

```bash
python -m workbench.tools.serve gmail --db state/gmail.db
```

Projection and bundle assembly are usually reached through
`workbench.environment.materialize`, which validates the world log first.
It keeps `state/` out of the agent's own `workspace/` by construction.
