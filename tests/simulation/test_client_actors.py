"""R3: the outside world drives itself — seeded cue schedules, client
actors authoring inbound mail, reply turns through the standard brakes."""

from pathlib import Path

from mini_workplace import make_spec
from test_workplace import DECIDE_IDLE_FALLBACK, SequenceLM

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.actors.client import ClientActorParams
from workbench.simulation.director import PoissonCueSchedule
from workbench.simulation.director.schedule import ClientProfile
from workbench.simulation.run import run_workplace

CLIENT_WRITE = (
    "[[ ## draft ## ]]\n"
    '{"to": ["Ann Liu"], "cc": [], "subject": "Statements question", '
    '"body": "One line item looks off; can you check?", '
    '"summary": "Asked Ann about a statement line."}\n\n'
    "[[ ## completed ## ]]"
)


class WorldLM:
    def __init__(self) -> None:
        self._client = SequenceLM([CLIENT_WRITE])
        self._idle = SequenceLM([DECIDE_IDLE_FALLBACK])

    async def complete(self, request):
        prompt = request.messages[-1].content
        if "[[ ## contacts ## ]]" in prompt:
            return await self._client.complete(request)
        return await self._idle.complete(request)


def _client_spec():
    spec = make_spec()
    people = []
    for person in spec.people:
        if person.person_id == "per-ravi-dee":
            person = person.model_copy(
                update={
                    "client_persona": ClientActorParams(
                        person_id="per-ravi-dee",
                        name="Ravi Dee",
                        organization="Dee Imports",
                        role="Owner",
                        temperament="Brisk, friendly, allergic to jargon.",
                        contacts=("Ann Liu",),
                        concerns=("cash flow", "the bank line renewal"),
                    )
                }
            )
        people.append(person)
    return spec.model_copy(update={"people": tuple(people), "day_script": ()})


def _schedule(seed: Seed) -> PoissonCueSchedule:
    return PoissonCueSchedule(
        seed=seed,
        clients=(
            ClientProfile(
                entity="ravi-dee",
                rate_millis=1000,
                situations=(
                    ("The monthly statements arrived and one line looks odd.", "close"),
                ),
            ),
        ),
    )


def test_cue_schedule_is_seeded_and_capped() -> None:
    seed = Seed(root=42)
    schedule = _schedule(seed)
    first = schedule.cues_for("2026-03-12")
    second = _schedule(seed).cues_for("2026-03-12")
    assert first == second, "same seed, same day, same cues"
    assert len(first) == 1, "rate 1.0/day yields exactly one cue"
    other_day = schedule.cues_for("2026-03-13")
    assert first != other_day or first[0].at != other_day[0].at

    flood = PoissonCueSchedule(
        seed=seed,
        clients=tuple(
            ClientProfile(
                entity=f"c{i}",
                rate_millis=3000,
                situations=(("Busy day.", "general"),),
            )
            for i in range(10)
        ),
        max_cues_per_day=8,
    )
    assert len(flood.cues_for("2026-03-12")) == 8, "the damper caps the day"


async def test_client_cue_becomes_inbound_email(tmp_path: Path) -> None:
    seed = Seed(root=42)
    result = await run_workplace(
        _client_spec(),
        seed=seed,
        out_dir=tmp_path / "run",
        inner_lm=WorldLM(),
        model="test/model",
        director=_schedule(seed),
    )
    assert result.reason in ("quiescent", "end_time")
    events = read_events(tmp_path / "run" / "world.jsonl")
    assert validate_events(events).ok

    cues = [e for e in events if e.tag == "sim.cue"]
    emails = [e for e in events if e.tag == "email.message"]
    assert cues, "the director stirred the client"
    inbound = [e for e in emails if e.payload.sender == "per-ravi-dee"]
    assert inbound, "the cue became a real inbound email"
    assert inbound[0].payload.to == ("per-ann-liu",)
    assert inbound[0].payload.subject == "Statements question"


async def test_client_runs_are_byte_deterministic(tmp_path: Path) -> None:
    seed = Seed(root=42)

    async def run(name: str) -> bytes:
        await run_workplace(
            _client_spec(),
            seed=seed,
            out_dir=tmp_path / name,
            inner_lm=WorldLM(),
            model="test/model",
            director=_schedule(seed),
        )
        return (tmp_path / name / "world.jsonl").read_bytes()

    assert await run("a") == await run("b")
