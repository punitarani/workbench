# Working in tools

Root rules in [`../AGENTS.md`](../AGENTS.md) apply. Package-specific:

## Invariants

* **Import `core` only.** Never simulation or workplaces; the
  world log is the sole input. The metadata cycle with the `workbench`
  member (environment depends on tools, tools depends on workbench for
  core) is deliberate — uv resolves it, and imports stay acyclic.
* **Reads are read-only; writes are confined.** Read tools open through
  `db.connect_readonly` (SQLite read-only URI mode). Write tools open
  through `db.connect_readwrite` and touch only action/sent tables that
  grading reads — nothing an agent writes feeds back into the projected
  record or the simulation. A write surface must match its official
  product's boundary (gmail has no send tool) or be a declared waiver in
  the parity snapshot.
* **The offstage boundary is structural.** Only tags a system declares in
  `handled_tags` may reach its database; `ToolSystem.__post_init__`
  refuses `sim.*` tags outright. Every agent-facing tool keeps a test
  asserting it leaks no offstage markers.
* **Unknown ids raise `UnknownRefError`** carrying the id — never a guess.
* **Never invent an identity or a currency.** A tool that needs the seat
  reads it through `framework.seat()` (or `require_seat`, which raises
  `SeatUnsetError` naming the fix) rather than defaulting to some person.
  A result that reflects superseded state says so in the payload — see
  iManage `search`'s `matched_versions`/`in_head` — instead of presenting
  it as current.

## The plugin contract

A tool system is a subpackage with four files, assembled into a
`ToolSystem` in its `__init__.py`:

* `tables.py` — Pydantic row models plus their `Table` bindings. Mark id
  columns `Annotated[str, Id("kind")]` and reference columns
  `Annotated[str, Ref("kind")]`; the coherence walk needs no other code.
* `project.py` — `project(events, connection)`: fold state in memory,
  insert validated rows once. No UPDATE statements.
* `server.py` — `register(server, db_path)`: read tools returning
  `model_dump()` of declared view models. Aggregates and joins go through
  `Query` with a declared result model.
* `__init__.py` — the `SYSTEM = ToolSystem(...)` assembly.

Adding a system means adding that subpackage and one line to
`registry.REGISTRY`. Nothing else changes: projection, coherence,
`mcp.json`, and `serve` pick it up from the registry — tests that name the
databases should derive them from `REGISTRY` rather than freeze a list.
Declare `person.record` in `handled_tags` — every database carries the
shared people table and `directory` tool.

## Data layer

`db.py` is the data layer: `Table[M]` derives DDL, inserts, and reads from
one Pydantic row model; `Query[M]` covers aggregate reads with a declared
result shape. Every row crossing a database edge is validated. Do not add
an ORM; the decision record:

* **Hand-rolled over stdlib sqlite3 (chosen)** — zero new dependencies,
  ~40ms import already paid via pydantic, single source of schema truth,
  right-sized for read-mostly databases rebuilt from the world log.
* **SQLAlchemy Core (rejected)** — works on 3.14 (2.0.51) but 119ms import
  per server spawn and schema declared twice (Core `Table` + Pydantic
  model), which is the drift risk this layer exists to remove.
* **SQLModel (rejected)** — fixes the dual declaration but brings ORM
  sessions, lazy loading, and 7 packages; these databases need none of it.
* **peewee (rejected)** — single file but its own metaclass field system;
  not Pydantic-compatible, so types would be declared twice anyway.

Supported column types: `str`, `int`, `float`, `bytes`, `X | None`, and
string `Literal` (becomes a CHECK constraint). If a model needs more than
that, reconsider the model before extending the layer.

## Tests

`tests/tools/projection_fixtures.py` mirrors
`tests/fixtures/worldlog_fixtures.py`; each suite is self-contained, so
keep edits in both. Behavior tests live at the MCP
surface (call the tools, parse the JSON) — schema details are free to
change; tool names, arguments, and JSON shapes are contracts.
