"""A persona that sets no artifact conventions renders as it always did.

The shared authoring prompt describes document *form* in the abstract,
but which artifact is a workbook and which is an issued PDF is a fact
about a profession. A firm whose filings become final by being filed and
a firm whose deliverable is a signed opinion do not name the same things,
and a single hardcoded list serves one of them at the other's expense.

The field carrying that vocabulary is therefore per-persona and optional
— and it has to be *invisibly* optional. Every recorded run in this tree
keys its cassettes on the exact request bytes, so a line appended to the
identity block unconditionally would miss every entry in a 2,300-file
cassette and take the replayed suite down with it.

This test is the compatibility claim, stated so it can fail. The first
assertion pins the unset rendering; the second proves the field is not
inert when it is set, because a flag that changes nothing would pass the
first assertion forever.
"""

from simulation.persona.params import ChannelStyle, ProfessionalWorkerParams
from simulation.persona.rendering import render_identity

_BASE = ProfessionalWorkerParams(
    person_id="per-test",
    name="Test Person",
    title="Associate",
    seniority="mid",
    role_description="Does the work.",
    personality="Steady.",
    channel_style=ChannelStyle(email_register="Plain.", chat_register="Short."),
    working_hours="09:00-17:00",
    manager=None,
)


def test_unset_conventions_render_exactly_the_recorded_block() -> None:
    assert render_identity(_BASE) == (
        "You are Test Person, Associate (mid).\n"
        "Does the work.\n"
        "Personality: Steady.\n"
        "Email register: Plain.\n"
        "Chat register: Short.\n"
        "Working hours: 09:00-17:00"
    )


def test_empty_string_is_the_same_as_unset() -> None:
    """The default is "", so the two paths must not diverge."""

    assert render_identity(
        _BASE.model_copy(update={"artifact_conventions": ""})
    ) == render_identity(_BASE)


def test_set_conventions_reach_the_prompt() -> None:
    """Guard the guard: a field nothing renders would pass the test above
    forever while silently doing nothing."""

    rendered = render_identity(
        _BASE.model_copy(update={"artifact_conventions": "Anything filed is a PDF."})
    )
    assert rendered.endswith("\nWork product: Anything filed is a PDF.")
    assert render_identity(_BASE) in rendered
