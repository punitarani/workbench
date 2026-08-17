"""What the tool surfaces actually serve, and what an oracle demands of them.

An oracle extracted from world state is not automatically answerable. The
reference solvers open ``state/*.db`` directly, so a task rule can name a
column no tool returns — and the resulting score measures whether the
agent guessed an internal vocabulary, not whether it did the work.

That is not hypothetical. ``tkt-000005`` is the world's own ticket id; the
clio surface identifies a matter by ``id`` and ``display_number``
(``00005-Mensah``) and never emits the ``tkt-`` form, which leaked instead
into 26 of 65 Slack messages. Two rollouts of one model on one task scored
1.000 and 0.273 on which vocabulary each happened to find.

So: collect every string the servers hand back through their discovery
tools, and require an oracle's identifiers to appear in that set. A task
whose answer key cannot be spelled in the language of its own tools is a
broken task, and this is the gate that says so before it is ever run.
"""

import asyncio
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from workbench.tools.framework import build_server
from workbench.tools.registry import REGISTRY

# Discovery tools take no required argument: they are how an agent with no
# prior knowledge finds anything at all. If a value cannot be reached from
# them (directly or through the ids they hand out), it is not discoverable.
_MAX_FOLLOW = 400

# Pagination is navigation, not a special case: a message on page nine is
# every bit as reachable as one on page one.
_MAX_PAGES = 60

# Read verbs only. The write half of these surfaces is real — `create_draft`
# takes no required argument and will happily file a draft — and a gate that
# measures a world must not change it.
_READ_VERBS = ("get_", "list_", "search_", "read_", "find_", "who_", "describe_")


def _is_read(name: str) -> bool:
    """A read verb, with or without its system's prefix.

    Slack names every tool ``slack_search_channels``, ``slack_read_thread``
    and so on, so matching the verb at the start of the string excluded that
    whole surface from the crawl -- and the gate then reported 272 message
    timestamps as unservable when the tools serve them plainly.
    """

    return name.startswith(_READ_VERBS) or name.split("_", 1)[-1].startswith(
        _READ_VERBS
    )

# An ISO calendar date, with or without a time on it.
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:.+\-]*)?")


def _strings(value: Any, into: set[str]) -> None:
    if isinstance(value, str):
        into.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            into.add(key)
            _strings(item, into)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _strings(item, into)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        into.add(str(value))


async def _call(server, name: str, arguments: dict) -> Any:
    try:
        result = await server.call_tool(name, arguments)
    except Exception:  # a tool needing a seat or a different id shape
        return None
    if result.is_error:
        return None
    for chunk in result.content:
        text = getattr(chunk, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except ValueError:
            return text
    return None


async def _collect(server, name: str, arguments: dict, into: set[str]) -> None:
    """Call a tool and read every page of it.

    Reachability is not "appears on page one". A message on the ninth page
    of a search is still something the agent can find, and a gate that
    stopped at the first page would condemn perfectly good tasks.
    """

    properties = set()
    for tool in await server.list_tools():
        if tool.name == name:
            properties = set((tool.input_schema or {}).get("properties") or {})
            break
    token_arg = next(
        (p for p in ("pageToken", "cursor", "page") if p in properties), None
    )

    arguments = dict(arguments)
    for _ in range(_MAX_PAGES):
        payload = await _call(server, name, arguments)
        if payload is None:
            return
        _strings(payload, into)
        if token_arg is None or not isinstance(payload, dict):
            return
        # Slack tucks its cursor inside `response_metadata`, so looking only
        # at the top level stopped every channel at page one and left most
        # of the firm's chat unreached — which the gate then reported as
        # unservable rather than as its own blind spot.
        nested = payload.get("response_metadata")
        places = (payload, nested if isinstance(nested, dict) else {})
        token = next(
            (
                where[key]
                for where in places
                for key in ("nextPageToken", "nextCursor", "next_cursor")
                if where.get(key)
            ),
            None,
        )
        if token_arg == "page":
            token = (arguments.get("page") or 1) + 1
            if not payload.get("hasMore") and not payload.get("has_more"):
                return
        if not token:
            return
        arguments[token_arg] = token


async def _served(state_dir: Path) -> set[str]:
    """Everything two steps of honest navigation can reach.

    An agent starts with no ids: it lists and searches, then opens what
    those results named. Gmail is the reason the second step matters —
    `search_threads` returns threads, and a message id only appears once
    you open one.
    """

    reachable: set[str] = set()
    for system in REGISTRY:
        db_path = state_dir / f"{system.name}.db"
        if not db_path.is_file():
            continue
        server = build_server(system, db_path)
        tools = [
            tool
            for tool in await server.list_tools()
            if _is_read(tool.name)
        ]
        discovered: set[str] = set()
        for tool in tools:
            required = (tool.input_schema or {}).get("required") or []
            if not required:
                await _collect(server, tool.name, {}, discovered)
            elif required == ["query"]:
                # A search that insists on a query is still discovery: an
                # agent with no ids types an empty one, and so does this.
                # Slack is the case that matters -- `search_channels`
                # requires a query, so skipping it left the whole surface
                # unreached, and 272 message timestamps the tools plainly
                # do serve were reported as unservable.
                await _collect(server, tool.name, {"query": ""}, discovered)
        reachable |= discovered

        # Step two: open what step one named.
        # Shortest first, then alphabetical. The cap bounds a crawl that is
        # otherwise quadratic, but truncating it alphabetically sorted
        # seventeen-character timestamps ahead of nine-character channel ids
        # and cut every channel out of the follow -- so two messages in a
        # 543-message room were reported as unservable while the tool
        # returned them happily when asked.
        candidates = sorted(
            (
                value
                for value in discovered
                if value and len(value) < 64 and " " not in value
            ),
            key=lambda value: (len(value), value),
        )[:_MAX_FOLLOW]
        for tool in tools:
            schema = tool.input_schema or {}
            required = schema.get("required") or []
            if len(required) != 1:
                continue
            for value in candidates:
                await _collect(server, tool.name, {required[0]: value}, reachable)
    return reachable


def served_vocabulary(state_dir: Path) -> set[str]:
    """Every string an agent can obtain from the tools without knowing an id.

    Cached per state directory and per state mtime. The crawl follows four
    hundred candidates through every read tool on five surfaces, sixty pages
    deep, and a build asks the same question once per task — ten identical
    crawls of one unchanging bundle. The mtime is in the key so a rebuilt
    bundle is never answered from a stale one.
    """

    fingerprint = (
        str(state_dir.resolve()),
        tuple(
            sorted(
                (path.name, path.stat().st_mtime_ns)
                for path in state_dir.glob("*.db")
            )
        ),
    )
    if fingerprint not in _VOCABULARY:
        _VOCABULARY.clear()
        # Crawled on a copy, because reading this world writes to it.
        # iManage keeps an access log and every tool call appends a row to
        # it -- a real feature of the product, and the reason the staged
        # bundle carried 2,280 file accesses that no person at the firm
        # ever made. The gate's own contract is that measuring a world must
        # not change it, and on the original it was breaking that contract
        # and defeating this cache in the same stroke.
        with tempfile.TemporaryDirectory() as scratch:
            mirror = Path(scratch) / "state"
            shutil.copytree(state_dir, mirror)
            _VOCABULARY[fingerprint] = asyncio.run(_served(mirror))
    return _VOCABULARY[fingerprint]


_VOCABULARY: dict[tuple, set[str]] = {}


def _identifiers(oracle: Any, into: set[str]) -> None:
    """The values an answer must name, as opposed to the numbers it computes.

    Counts, hours, and dollars are derived — an agent produces them by
    arithmetic, and they need not appear anywhere. Identifiers are the
    opposite: they can only be copied from something the tools said.
    """

    if isinstance(oracle, str):
        into.add(oracle)
    elif isinstance(oracle, dict):
        for item in oracle.values():
            _identifiers(item, into)
    elif isinstance(oracle, (list, tuple)):
        for item in oracle[:_MAX_FOLLOW]:
            _identifiers(item, into)


def unreachable(oracle: Any, state_dir: Path) -> list[str]:
    """Identifiers the oracle requires that no discovery tool ever serves."""

    reachable = served_vocabulary(state_dir)
    wanted: set[str] = set()
    _identifiers(oracle, wanted)
    return sorted(
        value for value in wanted if _is_identifier(value) and value not in reachable
    )


def solver_columns(solver: Path) -> dict[str, set[str]]:
    """What the reference solver reads, table by column.

    This is documentation, not a gate, and the distinction was expensive
    to learn. ``unreachable`` checks the answer's nouns and deliberately
    ignores derived numbers, which leaves a gap: a task can name only
    reachable engagements while resting on a table nobody can read. The
    regression task counted backward transitions out of ``matter_history``
    when no clio tool returned a status change; Opus 5 scored 0.067 on an
    unobtainable answer.

    Two static gates for it were written and both were vacuous. A table's
    values (``Open``, ``in-progress``, a person's name) all appear
    elsewhere, so "some value is served" passes always; and every surface
    renames columns on the way out (``quantity_seconds`` is served as
    ``quantity``), so "the column name is served" fails always. What
    actually caught the defect was a rollout and a reading of the score.

    So this returns the solver's read set for a human to check against the
    tool list, and the real gate stays where it belongs: any criterion
    below 1.0 is a defect until the transcript says otherwise.
    """

    text = solver.read_text()
    reads: dict[str, set[str]] = {}
    for columns, table in re.findall(
        r"SELECT\s+(.*?)\s+FROM\s+([a-z_][a-z0-9_]*)", text, re.IGNORECASE | re.DOTALL
    ):
        names = {
            part.strip().split()[-1].strip('"')
            for part in columns.split(",")
            if part.strip() and "(" not in part
        }
        reads.setdefault(table.lower(), set()).update(names)
    return reads


def _is_identifier(value: str) -> bool:
    """Something the world minted, as opposed to a word the task defined.

    `tkt-000005` and `Nora Behrens` have to be copied from a tool. `clear`
    and `awaiting_firm_reply` are vocabulary the instruction hands the agent,
    so their absence from the surfaces says nothing.
    """

    value = value.strip()
    if not value or len(value) > 120:
        return False
    if _DATE.fullmatch(value):
        # A calendar date is arithmetic, not vocabulary. Nobody guesses
        # `2026-01-31`; it is what "the end of the month this was sent in"
        # comes to, and the commitment register's due dates land on
        # weekends, on month ends, and past the last day the world ran --
        # so most of them appear in no payload and never could. Treating
        # them as identifiers condemned a task whose every date is derived
        # from a served one by a rule the instruction states in full.
        #
        # This costs the gate nothing it was built for: `tkt-000005` still
        # has digits and is still an identifier, and a date an agent must
        # *copy* is served anyway, so excluding it loses no coverage.
        return False
    if any(character.isdigit() for character in value):
        return True
    # A person or organisation name: capitalised words the agent must match.
    words = value.split()
    return 1 < len(words) < 6 and all(word[:1].isupper() for word in words)
