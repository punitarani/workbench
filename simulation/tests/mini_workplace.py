"""A two-person mini workplace shared by runner and seat tests: one internal
counsel (Ann Liu) and one external sender whose 09:40 email wants a reply."""

from persona_fixtures import DANIEL

from workbench.simulation.gm.grounded import TicketVocabulary
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
