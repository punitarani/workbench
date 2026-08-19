"""The episode loop: one chat model against one environment bundle.

The model sees the bundle's MCP tools plus two builtins — ``write_file``
(the only way a deliverable reaches disk, confined to the agent's own
workspace) and ``finish`` (the only clean stop). Every tool call in an
assistant message executes, in order, before the next model call.

The episode is handed ``bundle/workspace``: the agent works there, and the
bundle root beside it — holding ``state/`` and the server wiring — is
never reachable from a tool call.
"""

import json
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from adapters.harness.mcp_workspace import McpWorkspace, open_workspace

SYSTEM_PROMPT = (
    "You are a professional completing a task in a digital workspace. "
    "Read the workspace record through the available tools. You MUST write "
    "every final deliverable file with the write_file tool - files you do "
    "not write do not exist. Call finish once the deliverables are written."
)

NUDGE = (
    "Continue with tool calls: write deliverables with write_file and call "
    "finish when done."
)

BUILTIN_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write a file inside the workspace; parent directories are "
                "created. This is the only way to produce a deliverable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative path.",
                    },
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "End the episode once every deliverable is written.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
]


class ChatClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        max_tokens: int,
    ) -> dict[str, Any]: ...


class WorkspaceEscapeError(ValueError):
    """A write_file path pointed outside the workspace."""


class EpisodeResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    turns: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    stop_reason: Literal["finish", "max_turns", "call_budget"]
    transcript: list[dict[str, Any]]


def write_workspace_file(agent_root: Path, path: str, content: str) -> str:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise WorkspaceEscapeError(f"path escapes the workspace: {path!r}")
    root = agent_root.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise WorkspaceEscapeError(f"path escapes the workspace: {path!r}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} characters to {path}"


async def run_episode(
    agent_root: Path,
    instruction: str,
    chat_client: ChatClient,
    *,
    max_turns: int = 30,
    max_tokens_per_call: int = 2000,
    max_tool_calls: int | None = None,
) -> EpisodeResult:
    """``agent_root`` is the agent's own workspace — ``bundle/workspace``,
    whose parent is the bundle root the servers are launched from.

    ``max_tool_calls`` caps executed tool calls across the whole episode
    (the task-anchored call budget); calls past the cap are answered with an
    error and the episode stops with ``stop_reason="call_budget"``."""
    async with open_workspace(agent_root.parent) as workspace:
        tools = workspace.tool_specs() + BUILTIN_TOOL_SPECS
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ]
        turns = 0
        tool_call_count = 0
        stop_reason: Literal["finish", "max_turns", "call_budget"] = "max_turns"
        while turns < max_turns:
            turns += 1
            message = await chat_client.complete(
                messages, tools, max_tokens=max_tokens_per_call
            )
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                messages.append({"role": "user", "content": NUDGE})
                continue
            finished = False
            exhausted = False
            for call in calls:
                if max_tool_calls is not None and tool_call_count >= max_tool_calls:
                    exhausted = True
                    content = (
                        f"ERROR: tool-call budget exhausted "
                        f"({max_tool_calls} calls); the episode is over."
                    )
                else:
                    tool_call_count += 1
                    content = await _execute(workspace, agent_root, call)
                    finished = finished or call["function"]["name"] == "finish"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": content,
                    }
                )
            if finished:
                stop_reason = "finish"
                break
            if exhausted or (
                max_tool_calls is not None and tool_call_count >= max_tool_calls
            ):
                # Nothing can execute past the cap, so a full budget with no
                # finish ends the episode rather than burning model turns.
                stop_reason = "call_budget"
                break
        return EpisodeResult(
            turns=turns,
            tool_calls=tool_call_count,
            stop_reason=stop_reason,
            transcript=messages,
        )


async def _execute(
    workspace: McpWorkspace, agent_root: Path, call: dict[str, Any]
) -> str:
    name = call["function"]["name"]
    raw = call["function"].get("arguments") or "{}"
    try:
        arguments = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except json.JSONDecodeError as error:
        return f"ERROR: malformed tool arguments: {error}"
    if name == "finish":
        return "episode finished"
    if name == "write_file":
        # Models occasionally pass structured JSON for ``content``; str()
        # would write Python repr and silently corrupt the deliverable.
        content = arguments.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, indent=2)
        try:
            return write_workspace_file(
                agent_root, str(arguments.get("path", "")), content
            )
        except WorkspaceEscapeError as error:
            return f"ERROR: {error}"
    return await workspace.call(name, arguments)
