"""Record/replay cassette store: the single mechanism behind hermetic runs.

Keys are content-derived from the full request, so replay is independent of
call order and concurrency schedule. A replay miss is a hard error.
"""

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from workbench.core.hashing import canonical_json_bytes
from workbench.simulation.errors import CassetteMissError
from workbench.simulation.lm.protocol import LanguageModel, LMRequest, LMResponse

_DOMAIN = b"workbench.cassette.v1"


def cassette_key(request: LMRequest) -> str:
    digest = hashlib.blake2b(_DOMAIN, digest_size=32)
    digest.update(canonical_json_bytes(request))
    return digest.hexdigest()


class CallSite(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: str
    program: str
    predictor: str


class CassetteEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request: LMRequest
    response: LMResponse
    site: CallSite | None = None


class CassetteStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _path(self, key: str) -> Path:
        return self._directory / f"{key}.json"

    def get(self, key: str) -> LMResponse | None:
        path = self._path(key)
        if not path.exists():
            return None
        return self.read_entry(key).response

    def read_entry(self, key: str) -> CassetteEntry:
        return CassetteEntry.model_validate_json(
            self._path(key).read_text(encoding="utf-8")
        )

    def put(
        self, key: str, request: LMRequest, response: LMResponse, site: CallSite | None
    ) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        entry = CassetteEntry(request=request, response=response, site=site)
        self._path(key).write_text(entry.model_dump_json(indent=2), encoding="utf-8")


class RecordingLM:
    """Get-or-call-and-record. Cassette hits short-circuit the inner backend."""

    def __init__(
        self,
        inner: LanguageModel,
        store: CassetteStore,
        site: CallSite | None = None,
    ) -> None:
        self._inner = inner
        self._store = store
        self._site = site

    async def complete(self, request: LMRequest) -> LMResponse:
        key = cassette_key(request)
        cached = self._store.get(key)
        if cached is not None:
            return cached.model_copy(update={"cache_hit": True})
        response = await self._inner.complete(request)
        self._store.put(key, request, response, self._site)
        return response


class ReplayLM:
    """Cassette only. A miss means the recording is stale — fail loud."""

    def __init__(self, store: CassetteStore) -> None:
        self._store = store

    async def complete(self, request: LMRequest) -> LMResponse:
        key = cassette_key(request)
        cached = self._store.get(key)
        if cached is None:
            preview = request.messages[-1].content[:120]
            raise CassetteMissError(
                f"no recording for key {key} (model={request.model}, "
                f"seed={request.seed}, last message: {preview!r})"
            )
        return cached.model_copy(update={"cache_hit": True})
