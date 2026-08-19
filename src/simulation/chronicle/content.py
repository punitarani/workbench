"""LM-authored content with a persistent on-disk cache.

Completions are keyed by blake2b over (prompt, model, seed), so a warmed
cache makes every rebuild byte-identical without touching the network. The
cache entry stores the prompt alongside the text purely for debuggability;
only the text feeds the world log.
"""

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from simulation.lm.protocol import ChatMessage, LanguageModel, LMRequest

_DOMAIN = b"workbench.content.v1"


def content_key(prompt: str, model: str, seed: int) -> str:
    digest = hashlib.blake2b(_DOMAIN, digest_size=32)
    for part in (prompt.encode("utf-8"), model.encode("utf-8")):
        digest.update(len(part).to_bytes(4, "big"))
        digest.update(part)
    digest.update(seed.to_bytes(8, "big"))
    return digest.hexdigest()


class ContentEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: str
    model: str
    seed: int = Field(ge=0)
    text: str


class ContentStore:
    """Get-or-author: cache hits never construct a request."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _path(self, key: str) -> Path:
        return self._directory / f"{key}.json"

    def get(self, prompt: str, *, model: str, seed: int) -> str | None:
        path = self._path(content_key(prompt, model, seed))
        if not path.exists():
            return None
        return ContentEntry.model_validate_json(path.read_text(encoding="utf-8")).text

    def put(self, prompt: str, *, model: str, seed: int, text: str) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        entry = ContentEntry(prompt=prompt, model=model, seed=seed, text=text)
        self._path(content_key(prompt, model, seed)).write_text(
            entry.model_dump_json(indent=2), encoding="utf-8"
        )

    async def author(
        self,
        prompt: str,
        *,
        lm: LanguageModel,
        model: str,
        seed: int,
        max_tokens: int = 900,
    ) -> str:
        cached = self.get(prompt, model=model, seed=seed)
        if cached is not None:
            return cached
        request = LMRequest(
            model=model,
            messages=(ChatMessage(role="user", content=prompt),),
            temperature=0.3,
            max_tokens=max_tokens,
            seed=seed,
        )
        response = await lm.complete(request)
        text = response.text.strip()
        self.put(prompt, model=model, seed=seed, text=text)
        return text
