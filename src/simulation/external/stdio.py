"""JSONL-over-stdio transport: one ActRequest line out, one ActResponse line back."""

import asyncio

from core.actions import ActRequest, ActResponse
from simulation.errors import TransportError


class StdioTransport:
    def __init__(self, *, command: tuple[str, ...]) -> None:
        self._command = command
        self._process: asyncio.subprocess.Process | None = None

    async def _ensure_started(self) -> asyncio.subprocess.Process:
        if self._process is None:
            self._process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
        return self._process

    async def act(self, request: ActRequest) -> ActResponse:
        process = await self._ensure_started()
        if process.stdin is None or process.stdout is None:
            raise TransportError("stdio transport has no pipes")
        process.stdin.write(request.model_dump_json().encode("utf-8") + b"\n")
        await process.stdin.drain()
        line = await process.stdout.readline()
        if not line:
            raise TransportError(
                f"external process closed stdout (exit {process.returncode})"
            )
        return ActResponse.model_validate_json(line)

    async def close(self) -> None:
        if self._process is not None:
            if self._process.stdin is not None:
                self._process.stdin.close()
            await self._process.wait()
            self._process = None
