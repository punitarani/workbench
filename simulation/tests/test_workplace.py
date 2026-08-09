from pathlib import Path

import pytest
from persona_fixtures import DANIEL

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, read_manifest, validate_events
from workbench.simulation.errors import ConfigError
from workbench.simulation.gm.grounded import TicketVocabulary
from workbench.simulation.lm.protocol import LMRequest, LMResponse, TokenUsage
from workbench.simulation.run import run_workplace
from workbench.simulation.workplace.compile import compile_workplace, config_hash
from workbench.simulation.workplace.spec import (
    ChannelSpec,
    ExogenousEmail,
    PersonSpec,
    WorkplaceSpec,
)

VOCAB = TicketVocabulary(
    statuses=("open", "closed"),
    priorities=("normal",),
    ticket_types=("general",),
)


def ann_params():
    return DANIEL.model_copy(update={"person_id": "per-ann-liu", "name": "Ann Liu"})


def make_spec(**overrides) -> WorkplaceSpec:
    defaults = dict(
        workplace_id="mini",
        display_name="Mini Co",
        timezone="UTC",
        epoch="2026-03-12T00:00:00+00:00",
        ticket_vocabulary=VOCAB,
        people=(
            PersonSpec(
                person_id="per-ann-liu",
                name="Ann Liu",
                email_address="ann@mini.example",
                title="Counsel",
                department="Legal",
                manager=None,
                affiliation="internal",
                persona=ann_params(),
            ),
            PersonSpec(
                person_id="per-ravi-dee",
                name="Ravi Dee",
                email_address="ravi@outside.example",
                title="Outside Counsel",
                department="External",
                manager=None,
                affiliation="external",
                persona=None,
            ),
        ),
        channels=(ChannelSpec(name="#general", members=("per-ann-liu",)),),
        seed_documents=(),
        day_script=(
            ExogenousEmail(
                at="09:40",
                sender="per-ravi-dee",
                to=("per-ann-liu",),
                cc=(),
                subject="Quick question",
                body="Can you confirm receipt?",
            ),
        ),
        end_of_day="17:30",
    )
    defaults.update(overrides)
    return WorkplaceSpec(**defaults)


def test_compile_is_deterministic() -> None:
    seed = Seed(root=42)
    first = compile_workplace(make_spec(), seed)
    second = compile_workplace(make_spec(), seed)
    assert config_hash(make_spec(), seed) == config_hash(make_spec(), seed)
    assert [e.model_dump_json() for e in first.genesis] == [
        e.model_dump_json() for e in second.genesis
    ]
    assert first.scheduled == second.scheduled


def test_genesis_validates_and_day_script_is_scheduled() -> None:
    compiled = compile_workplace(make_spec(), Seed(root=42))
    assert compiled.genesis[0].payload.kind == "sim.run.started"
    report = validate_events(compiled.genesis)
    assert report.ok, report.findings
    day_script = [s for s in compiled.scheduled if s.draft.tag != "sim.wake"]
    assert len(day_script) == 1
    assert day_script[0].time == 9 * 3600 + 40 * 60


def test_unknown_channel_member_is_rejected_at_compile() -> None:
    spec = make_spec(channels=(ChannelSpec(name="#ghost", members=("per-nobody",)),))
    with pytest.raises(ConfigError) as excinfo:
        compile_workplace(spec, Seed(root=42))
    assert "per-nobody" in str(excinfo.value)


def test_unknown_day_script_sender_rejected() -> None:
    spec = make_spec(
        day_script=(
            ExogenousEmail(
                at="10:00",
                sender="per-ghost",
                to=("per-ann-liu",),
                cc=(),
                subject="boo",
                body="?",
            ),
        )
    )
    with pytest.raises(ConfigError):
        compile_workplace(spec, Seed(root=42))


DECIDE_REPLY = (
    "[[ ## choice ## ]]\n"
    '{"action": "reply_email", "target_ref": "thr-000001", '
    '"intent": "Confirm receipt", "reason": "Direct question"}\n\n'
    "[[ ## completed ## ]]"
)

DRAFT_REPLY = (
    "[[ ## draft ## ]]\n"
    '{"to": ["Ravi Dee"], "cc": [], "subject": "Re: Quick question", '
    '"body": "Confirmed, thanks.", "summary": "Confirmed receipt to Ravi."}\n\n'
    "[[ ## completed ## ]]"
)

DECIDE_IDLE_FALLBACK = (
    "[[ ## choice ## ]]\n"
    '{"action": "idle", "target_ref": null, '
    '"intent": "Nothing pending", "reason": "Quiet"}\n\n'
    "[[ ## completed ## ]]"
)


class SequenceLM:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.calls = 0

    async def complete(self, request: LMRequest) -> LMResponse:
        text = self._texts[min(self.calls, len(self._texts) - 1)]
        self.calls += 1
        return LMResponse(
            text=text, usage=TokenUsage(prompt_tokens=1, completion_tokens=1)
        )


async def test_end_to_end_mini_run(tmp_path: Path) -> None:
    out_dir = tmp_path / "run"
    result = await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        # ann wakes at 09:03 and 09:33 (two idle decides) before the 09:40
        # email grants her the reply turn; later wakes hit the idle fallback.
        inner_lm=SequenceLM(
            [
                DECIDE_IDLE_FALLBACK,
                DECIDE_IDLE_FALLBACK,
                DECIDE_REPLY,
                DRAFT_REPLY,
                DECIDE_IDLE_FALLBACK,
            ]
        ),
        model="test/model",
    )
    assert result.reason == "quiescent"

    events = read_events(out_dir / "world.jsonl")
    report = validate_events(events)
    assert report.ok, report.findings

    emails = [e for e in events if e.payload.kind == "email.message"]
    assert len(emails) == 2, "exogenous email plus ann's reply"
    assert emails[1].payload.sender == "per-ann-liu"
    assert emails[1].payload.in_reply_to == emails[0].payload.message_id
    assert emails[1].caused_by == emails[0].event_id

    manifest = read_manifest(out_dir / "manifest.json")
    assert manifest.event_count == len(events)
    assert manifest.matches_log(out_dir / "world.jsonl")


def test_wakes_are_scheduled_for_each_persona() -> None:
    compiled = compile_workplace(make_spec(), Seed(root=42))
    wakes = [s for s in compiled.scheduled if s.draft.tag == "sim.wake"]
    assert wakes, "personas need periodic check-in turns"
    entities = {w.draft.payload.entity for w in wakes}
    assert entities == {"ann-liu"}, "only simulated personas wake"
    times = [w.time for w in wakes if w.draft.payload.entity == "ann-liu"]
    assert times == sorted(times)
    assert times[0] >= 9 * 3600
    assert times[-1] < compiled.end_time


async def test_gm_mints_never_collide_with_future_scripted_ids(
    tmp_path: Path,
) -> None:
    """A persona reply minted before a later scripted email must not reuse
    the compile-time id that email already owns."""
    spec = make_spec(
        day_script=(
            ExogenousEmail(
                at="09:40",
                sender="per-ravi-dee",
                to=("per-ann-liu",),
                cc=(),
                subject="Quick question",
                body="Can you confirm receipt?",
            ),
            ExogenousEmail(
                at="15:00",
                sender="per-ravi-dee",
                to=("per-ann-liu",),
                cc=(),
                subject="Afternoon follow-up",
                body="One more thing entirely.",
            ),
        )
    )
    out_dir = tmp_path / "run"
    await run_workplace(
        spec,
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=SequenceLM(
            [
                DECIDE_IDLE_FALLBACK,
                DECIDE_IDLE_FALLBACK,
                DECIDE_REPLY,
                DRAFT_REPLY,
                DECIDE_IDLE_FALLBACK,
            ]
        ),
        model="test/model",
    )
    events = read_events(out_dir / "world.jsonl")
    report = validate_events(events)
    assert report.ok, report.findings
