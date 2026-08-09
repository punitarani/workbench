"""Harness contract tests. Fully offline: the workspace is materialized
from fixture events, the LM is a scripted client, and the OpenRouter
client runs against an httpx mock transport."""

import json
import textwrap
from pathlib import Path
from typing import Any

import httpx
import pytest
from workspace_fixtures import coherent_events

from workbench.adapters.harness.agent_loop import (
    WorkspaceEscapeError,
    run_episode,
    write_workspace_file,
)
from workbench.adapters.harness.grade import GraderError, grade_episode
from workbench.adapters.harness.mcp_workspace import open_workspace
from workbench.adapters.harness.openrouter_client import (
    OpenRouterChatClient,
    OpenRouterError,
)
from workbench.core.worldlog import WorldLogWriter
from workbench.environment import materialize

DELIVERABLE = "clause triage: two-year cap accepted per Daniel's redline\n"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    log_path = tmp_path / "world.jsonl"
    with WorldLogWriter(log_path) as writer:
        for event in coherent_events():
            writer.append(event)
    out = tmp_path / "workspace"
    materialize(log_path, out)
    return out


class ScriptedChatClient:
    """Plays canned assistant messages and records what it was shown."""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self.script = list(script)
        self.seen_tools: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        self.seen_tools = tools
        if not self.script:
            return {"role": "assistant", "content": "thinking out loud"}
        return self.script.pop(0)


def tool_call(name: str, arguments: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def episode_script() -> list[dict[str, Any]]:
    return [
        tool_call("gmail__get_thread", {"threadId": "thr-000001"}, "call-1"),
        tool_call(
            "write_file", {"path": "deliverable.md", "content": DELIVERABLE}, "call-2"
        ),
        tool_call("finish", {"summary": "deliverable written"}, "call-3"),
    ]


async def test_workspace_specs_and_call_roundtrip(workspace: Path) -> None:
    async with open_workspace(workspace) as ws:
        names = {spec["function"]["name"] for spec in ws.tool_specs()}
        assert {
            "gmail__search_threads",
            "gmail__get_thread",
            "slack__slack_search_public",
            "slack__slack_read_channel",
            "imanage__search",
            "clio__list_matters",
        } <= names
        for spec in ws.tool_specs():
            assert spec["type"] == "function"
            assert spec["function"]["parameters"].get("type") == "object"

        text = await ws.call("gmail__get_thread", {"threadId": "thr-000001"})
        assert "msg-000001" in text and "NDA review" in text
        assert json.loads(text)

        missing = await ws.call("gmail__get_thread", {"threadId": "thr-999999"})
        assert missing.startswith("ERROR:")
        unknown = await ws.call("nosuch__tool", {})
        assert unknown.startswith("ERROR:")


async def test_episode_stops_on_finish(workspace: Path) -> None:
    client = ScriptedChatClient(episode_script())
    result = await run_episode(workspace, "Reconstruct the triage memo.", client)

    assert result.stop_reason == "finish"
    assert result.turns == 3
    assert result.tool_calls == 3
    assert (workspace / "deliverable.md").read_text() == DELIVERABLE

    shown = {spec["function"]["name"] for spec in client.seen_tools}
    assert {"write_file", "finish", "gmail__get_thread", "clio__list_matters"} <= shown

    assert result.transcript[0]["role"] == "system"
    assert result.transcript[1] == {
        "role": "user",
        "content": "Reconstruct the triage memo.",
    }
    by_call = {
        m["tool_call_id"]: m["content"]
        for m in result.transcript
        if m.get("role") == "tool"
    }
    assert "msg-000001" in by_call["call-1"]
    assert by_call["call-2"].startswith("wrote ")
    assert by_call["call-3"] == "episode finished"


async def test_episode_hits_max_turns(workspace: Path) -> None:
    client = ScriptedChatClient([])
    result = await run_episode(workspace, "Do nothing.", client, max_turns=2)
    assert result.stop_reason == "max_turns"
    assert result.turns == 2
    assert result.tool_calls == 0


async def test_write_file_serializes_structured_content(workspace: Path) -> None:
    """A model passing JSON for ``content`` must land as JSON, not repr()."""

    payload = {"cutoff_date": "2026-04-03", "entries": [1, 2]}
    script = [
        tool_call("write_file", {"path": "out.json", "content": payload}, "call-1"),
        tool_call("finish", {"summary": "done"}, "call-2"),
    ]
    result = await run_episode(
        workspace, "Write the deliverable.", ScriptedChatClient(script)
    )
    assert result.stop_reason == "finish"
    assert json.loads((workspace / "out.json").read_text()) == payload


def test_write_file_confined_to_workspace(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    assert write_workspace_file(root, "sub/dir/out.md", "x").startswith("wrote 1")
    assert (root / "sub" / "dir" / "out.md").read_text() == "x"
    for path in ("../escape.md", "/etc/passwd", "a/../../escape.md"):
        with pytest.raises(WorkspaceEscapeError):
            write_workspace_file(root, path, "x")


def fake_task(tmp_path: Path) -> Path:
    task_dir = tmp_path / "task"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "grade.py").write_text(
        textwrap.dedent(
            """
            import json, os
            from pathlib import Path

            score = 1.0 if Path("deliverable.md").exists() else 0.0
            log_dir = Path(os.environ["VERIFIER_LOG_DIR"])
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "reward.json").write_text(json.dumps({"score": score}))
            print("reward:", score)
            """
        )
    )
    return task_dir


def test_grade_episode_runs_task_grader(tmp_path: Path) -> None:
    task_dir = fake_task(tmp_path)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert grade_episode(task_dir, workspace) == {"score": 0.0}
    (workspace / "deliverable.md").write_text(DELIVERABLE)
    assert grade_episode(task_dir, workspace) == {"score": 1.0}


def test_grade_episode_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(GraderError):
        grade_episode(tmp_path / "no-task", tmp_path)
    task_dir = fake_task(tmp_path)
    (task_dir / "tests" / "grade.py").write_text("raise SystemExit(3)\n")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    with pytest.raises(GraderError):
        grade_episode(task_dir, workspace)


def openrouter_response(content: str, prompt: int, completion: int) -> dict[str, Any]:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    }


async def test_openrouter_client_accumulates_usage() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=openrouter_response("ok", 100, 10))

    client = OpenRouterChatClient(
        "key", "test/model", transport=httpx.MockTransport(handler)
    )
    tools = [{"type": "function", "function": {"name": "finish", "parameters": {}}}]
    message = await client.complete(
        [{"role": "user", "content": "hi"}], tools, max_tokens=123
    )
    await client.complete([{"role": "user", "content": "again"}], tools)
    await client.aclose()

    assert message == {"role": "assistant", "content": "ok"}
    assert requests[0]["model"] == "test/model"
    assert requests[0]["tools"] == tools
    assert requests[0]["max_tokens"] == 123
    assert requests[0]["temperature"] == 0.2
    assert (client.prompt_tokens, client.completion_tokens) == (200, 20)
    assert client.usage_cost((0.5, 2.0)) == pytest.approx(
        (200 * 0.5 + 20 * 2.0) / 1_000_000
    )


async def test_openrouter_client_fails_loud() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    client = OpenRouterChatClient(
        "key", "test/model", transport=httpx.MockTransport(refuse)
    )
    with pytest.raises(OpenRouterError, match="429"):
        await client.complete([], [])
    await client.aclose()

    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    client = OpenRouterChatClient(
        "key", "test/model", transport=httpx.MockTransport(malformed)
    )
    with pytest.raises(OpenRouterError, match="malformed"):
        await client.complete([], [])
    await client.aclose()
