"""Content store contract: cache hits skip the backend, keys separate
prompt/model/seed, and a warmed directory reproduces without any LM."""

from pathlib import Path

from workbench.simulation.chronicle.content import ContentStore, content_key
from workbench.simulation.lm.fake import FakeLM
from workbench.simulation.lm.protocol import LMRequest, LMResponse


class CountingLM:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = FakeLM()

    async def complete(self, request: LMRequest) -> LMResponse:
        self.calls += 1
        return await self._inner.complete(request)


MODEL = "deepseek/deepseek-v4-flash-0731"


async def test_author_caches_and_replays(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    lm = CountingLM()

    first = await store.author("Draft a note.", lm=lm, model=MODEL, seed=7)
    second = await store.author("Draft a note.", lm=lm, model=MODEL, seed=7)

    assert first == second
    assert lm.calls == 1, "the second author call must hit the cache"
    assert store.get("Draft a note.", model=MODEL, seed=7) == first


async def test_warmed_directory_reproduces_without_lm(tmp_path: Path) -> None:
    warm = CountingLM()
    text = await ContentStore(tmp_path).author(
        "Draft a note.", lm=warm, model=MODEL, seed=7
    )

    cold = CountingLM()
    replayed = await ContentStore(tmp_path).author(
        "Draft a note.", lm=cold, model=MODEL, seed=7
    )
    assert replayed == text
    assert cold.calls == 0


async def test_key_separates_prompt_model_and_seed(tmp_path: Path) -> None:
    base = content_key("p", "m", 1)
    assert content_key("q", "m", 1) != base
    assert content_key("p", "n", 1) != base
    assert content_key("p", "m", 2) != base

    store = ContentStore(tmp_path)
    lm = CountingLM()
    await store.author("p", lm=lm, model="m", seed=1)
    await store.author("p", lm=lm, model="m", seed=2)
    assert lm.calls == 2, "a different seed is a different completion"


async def test_author_strips_whitespace_before_storing(tmp_path: Path) -> None:
    class PaddedLM:
        async def complete(self, request: LMRequest) -> LMResponse:
            response = await FakeLM().complete(request)
            return response.model_copy(update={"text": f"\n {response.text} \n"})

    store = ContentStore(tmp_path)
    text = await store.author("p", lm=PaddedLM(), model="m", seed=1)
    assert text == text.strip()
    assert store.get("p", model="m", seed=1) == text
