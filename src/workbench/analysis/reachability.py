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
        token = next(
            (
                payload[key]
                for key in ("nextPageToken", "nextCursor", "next_cursor")
                if payload.get(key)
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
            if tool.name.startswith(_READ_VERBS)
        ]
        discovered: set[str] = set()
        for tool in tools:
            if (tool.input_schema or {}).get("required"):
                continue
            await _collect(server, tool.name, {}, discovered)
        reachable |= discovered

        # Step two: open what step one named.
        candidates = sorted(
            value
            for value in discovered
            if value and len(value) < 64 and " " not in value
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
    """Every string an agent can obtain from the tools without knowing an id."""

    return asyncio.run(_served(state_dir))


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


def _is_identifier(value: str) -> bool:
    """Something the world minted, as opposed to a word the task defined.

    `tkt-000005` and `Nora Behrens` have to be copied from a tool. `clear`
    and `awaiting_firm_reply` are vocabulary the instruction hands the agent,
    so their absence from the surfaces says nothing.
    """

    value = value.strip()
    if not value or len(value) > 120:
        return False
    if any(character.isdigit() for character in value):
        return True
    # A person or organisation name: capitalised words the agent must match.
    words = value.split()
    return 1 < len(words) < 6 and all(word[:1].isupper() for word in words)
