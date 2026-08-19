"""The interactive seat: an ActTransport the engine parks on while an agent
decides.

The engine side calls ``act`` and blocks; the agent side alternates
``next_turn`` / ``submit``. When the day ends the driver calls ``end`` and
``next_turn`` returns None. Everything runs on one event loop — the engine
and the agent are peer tasks, which is what keeps the run deterministic.
"""

import asyncio

from core.actions import ActRequest, ActResponse, EntityAction
from simulation.errors import SeatProtocolError

_DAY_OVER = None


class SeatSession:
    def __init__(self) -> None:
        self._turns: asyncio.Queue[ActRequest | None] = asyncio.Queue()
        self._pending: asyncio.Future[ActResponse] | None = None
        self._ended = False

    async def act(self, request: ActRequest) -> ActResponse:
        if self._ended:
            raise SeatProtocolError("the session has ended; no further turns")
        if self._pending is not None and not self._pending.done():
            raise SeatProtocolError("a turn is already awaiting an answer")
        self._pending = asyncio.get_running_loop().create_future()
        await self._turns.put(request)
        return await self._pending

    async def next_turn(self) -> ActRequest | None:
        """The agent's wait for its next turn; None means the day is over."""
        return await self._turns.get()

    def submit(self, action: EntityAction) -> None:
        """Answer the pending turn; the engine resumes immediately."""
        if self._pending is None or self._pending.done():
            raise SeatProtocolError("no pending turn to answer")
        self._pending.set_result(ActResponse(action=action))

    def end(self) -> None:
        """Called by the driver once the run returns; wakes the agent loop."""
        self._ended = True
        self._turns.put_nowait(_DAY_OVER)
