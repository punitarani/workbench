"""The episode loop: one chat model against one workspace.

The model sees the workspace's MCP tools plus two builtins — ``write_file``
(the only way a deliverable reaches disk, confined to the workspace) and
``finish`` (the only clean stop). Every tool call in an assistant message
executes, in order, before the next model call.
"""

import json
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from workbench.adapters.harness.mcp_workspace import McpWorkspace, open_workspace

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
    stop_reason: Literal["finish", "max_turns"]
    transcript: list[dict[str, Any]]


def write_workspace_file(workspace_dir: Path, path: str, content: str) -> str:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise WorkspaceEscapeError(f"path escapes the workspace: {path!r}")
    root = workspace_dir.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise WorkspaceEscapeError(f"path escapes the workspace: {path!r}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} characters to {path}"


async def run_episode(
    workspace_dir: Path,
    instruction: str,
    chat_client: ChatClient,
    *,
    max_turns: int = 30,
    max_tokens_per_call: int = 2000,
) -> EpisodeResult:
    async with open_workspace(workspace_dir) as workspace:
        tools = workspace.tool_specs() + BUILTIN_TOOL_SPECS
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ]
        turns = 0
        tool_call_count = 0
        stop_reason: Literal["finish", "max_turns"] = "max_turns"
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
            for call in calls:
                tool_call_count += 1
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": await _execute(workspace, workspace_dir, call),
                    }
                )
                finished = finished or call["function"]["name"] == "finish"
            if finished:
                stop_reason = "finish"
                break
        return EpisodeResult(
            turns=turns,
            tool_calls=tool_call_count,
            stop_reason=stop_reason,
            transcript=messages,
        )


async def _execute(
    workspace: McpWorkspace, workspace_dir: Path, call: dict[str, Any]
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
        try:
            return write_workspace_file(
                workspace_dir,
                str(arguments.get("path", "")),
                str(arguments.get("content", "")),
            )
        except WorkspaceEscapeError as error:
            return f"ERROR: {error}"
    return await workspace.call(name, arguments)
