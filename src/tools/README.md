# tools

The agent-facing tool systems: projections from the recorded world log
into per-tool SQLite databases, and MCP servers over them that emulate
each product's official surface — reads and writes both.

Each system is a plugin — a subpackage implementing one typed contract
(`ToolSystem`): the world-log tags it observes, its tables, a projector,
and a server registrar. A single registry (`registry.py`, one line per
system) drives everything downstream: projection, cross-database
coherence checking, server assembly, the environment bundle's `mcp.json`
specs, and the stdio serve entry point.

| System | Database | Tools | Mirrors | Write half |
|---|---|---|---|---|
| `gmail` | `gmail.db` | 19 | Google's official Gmail MCP | drafts, labels, trash, spam — no send tool, matching the official server |
| `calendar` | `calendar.db` | 9 | Google's official Calendar MCP | `create_event`, `update_event`, `delete_event`, `respond_to_event` |
| `slack` | `slack.db` | 19 | Slack's official MCP | messages, drafts, scheduled sends, conversations, reactions, canvases |
| `imanage` | `imanage.db` | 15 | official iManage Work MCP | recents and actions recorded server-side |
| `clio` | `clio.db` | 8 | Clio Manage API v4 grammar (no official MCP exists) | read-only |
| `compliance` | `compliance.db` | 11 | in-house write surface | the template: reference tables seeded at build time, action tables written by the agent |

Reads open through `connect_readonly`; writes go through
`connect_readwrite` into action/sent tables that grading reads — nothing
an agent writes ever feeds back into the simulation. `compliance` is the
one system not projected from the world log: its reference tables are
seeded from a task scenario and its action tables start empty.

Parity with the official vendors is pinned to dated `tools/list`
snapshots under `tests/parity/snapshots/` and enforced by
`tests/parity/` (implemented-or-waived, no invented tools, required
parameters, provenance); the living implemented/waived matrix is
[`docs/epochs/v2/PARITY-MATRIX.md`](../../../docs/epochs/v2/PARITY-MATRIX.md).
Divergences are declared as snapshot waivers, never silent — e.g.
iManage `search` spans every document version, so each hit reports
`matched_versions` and `in_head` rather than passing stale text off as
current.

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

Write tools that need an identity (`slack_send_message`,
`create_draft`, …) require the seat and raise `SeatUnsetError` rather
than defaulting to some person.

Schemas are typed end to end: `db.py` derives DDL, inserts, and reads
from Pydantic row models, so the schema cannot drift from the types, and
`Id`/`Ref` column markers make cross-database references
machine-checkable.

Serve one system over stdio, from the bundle root (the container wraps
this with `run-as-environment`, so the database is readable only by the
`environment` user and the tools are the sole aperture onto it):

```bash
python -m tools.serve gmail --db state/gmail.db
```

Projection and bundle assembly are usually reached through
`environment.materialize`, which validates the world log
first. It keeps `state/` out of the agent's own `workspace/` by
construction.
