"""The engine's own failures must never become facts about the firm.

Three defects, one disease. A persona tried to file a document; the actor
handed the model's `AuthoredDocument` straight into a field declared
`DocumentCreateSpec`; pydantic refused it; and the refusal was written
into the lawyer's memory in pydantic's words, at importance 10 — the
highest this world has, so it outranked everything that person had
actually done and was retrieved for the rest of the run.

Measured over thirty recorded days of Merrick Stanton LLP:

    415 of 417 malformed drafts    one missing `_create_spec` call
    410 create attempts / 71 documents saved
    7.12% of all events            a persona remembering an engine error
    4.8% of time-entry narratives  "reworked malformed sections"

and, because seventeen people all remembered the same impossible thing,
a shared account of an outage that never happened: a Slack thread chasing
"the malformed-input bug" across two colleagues and a ticket number, a
mail chain about a "malformed send", and a matter note opened to document
"the recurring platform action failures".

Nothing failed. Every reference resolved, every count was consistent, and
the firm's own record was the only evidence — which is the point. These
tests drive the real actor, the real referee and the real memory stream;
none of them reimplements the thing it checks.
"""

import ast
import re
from pathlib import Path

from persona_fixtures import DANIEL, observed_events

from core.actions import IntentAction, IntentActionSpec
from core.events import Event
from core.events.control import SimGmNotePayload
from core.intents import DocumentCreateSpec, DocumentEditIntent
from core.seed import Seed
from simulation.gm.grounded import IntentRejection
from simulation.lm.dspy_lm import WorkbenchLM
from simulation.lm.protocol import LMRequest, LMResponse, TokenUsage
from simulation.persona.actor import ProfessionalActorAct, _work_in_hand
from simulation.persona.memory_stream import MemoryStreamComponent
from simulation.persona.working_memory import WorkingMemoryComponent

# Words that belong to the machinery. A persona who has read one of these
# is reading the engine, not the firm. `_ENGINE_WORDS` is deliberately
# about *vocabulary* rather than about any one message: the leak that
# reached production was a string nobody had written by hand at all.
_ENGINE_WORDS = (
    # what a parser says when it refuses
    "pydantic",
    "validation error",
    "field required",
    "input should be",
    "extra inputs",
    "not permitted",
    "traceback",
    "nonetype",
    # the engine's own nouns. `intent` is here because it leaked: the
    # referee refused "ticket intent had no changes and no comment", and
    # 169 time-entry narratives came back talking about rejected ticket
    # intents. It is also ordinary legal English — "legislative intent",
    # "intent to sue" — which is exactly why the boundary matters: this
    # list is checked against what the *engine* writes, never against
    # what a persona writes.
    "intent",
    "payload",
    "schema",
    # `json` was missing, and that is exactly how the last one got out:
    # the reason said "send the structured JSON for that format", the
    # vocabulary list had every type name and action verb in it, and a
    # partner wrote "the underlying content is not actually structured
    # JSON" into her own reflection.
    "json",
    "xml",
    "csv",
    "serialize",
    "serialized",
    "parse",
    "parsed",
    "spec",
    "referee",
    "cassette",
    "malformed",
    # anything that names a parameter or a type rather than a thing
    "ticket_ref",
    "document_ref",
    "create spec",
    "documentcreatespec",
    "spreadsheetcontent",
    "authoreddocument",
    # the action verbs. A firm's staff have no reason to have heard these.
    "create_document",
    "revise_document",
    "send_email",
    "reply_email",
    "post_chat",
    "react_chat",
    "create_ticket",
    "update_ticket",
    "comment_ticket",
    "log_time",
    "schedule_meeting",
)

# Word-boundary, not substring: "spec" must not fire on "specific" and
# "intent" must not fire on "intention". A vocabulary check that flags
# ordinary English gets switched off, and a switched-off check is the
# thing this whole file exists to prevent.
_ENGINE_PATTERN = re.compile(
    r"(?<![a-z0-9_])(?:" + "|".join(re.escape(w) for w in _ENGINE_WORDS) + r")(?![a-z0-9])",
    re.IGNORECASE,
)


def _engine_words_in(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _ENGINE_PATTERN.finditer(text or "")})


class SequenceLM:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.calls = 0

    async def complete(self, request: LMRequest) -> LMResponse:
        text = self._texts[self.calls]
        self.calls += 1
        return LMResponse(
            text=text, usage=TokenUsage(prompt_tokens=1, completion_tokens=1)
        )


DECIDE_CREATE_DOCUMENT = (
    "[[ ## choice ## ]]\n"
    '{"action": "create_document", "target_ref": null, '
    '"intent": "Draft the Vantage NDA review memo", '
    '"reason": "Partner asked for it today"}\n\n'
    "[[ ## completed ## ]]"
)

AUTHOR_MEMO = (
    "[[ ## document ## ]]\n"
    '{"title": "Vantage NDA review", '
    '"path": "engagements/vantage/nda/review-memo.docx", '
    '"document": {"blocks": ['
    '{"kind": "heading", "level": 1, "text": "Scope"}, '
    '{"kind": "paragraph", "text": "The mutual NDA runs three years."}]}}\n\n'
    "[[ ## completed ## ]]"
)


async def _actor(texts: list[str]) -> tuple[ProfessionalActorAct, SequenceLM]:
    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    for event in observed_events():
        await memory.pre_observe(event)
    inner = SequenceLM(texts)
    lm = WorkbenchLM(
        inner,
        model="deepseek/deepseek-v4-flash-0731",
        seed=Seed(root=42),
        path=("entity", "daniel"),
        max_tokens=1024,
    )
    params = DANIEL.model_copy(update={"extra_verbs": ("create_document",)})
    return ProfessionalActorAct(params=params, working_memory=memory, lm=lm), inner


async def test_opportunistic_create_produces_a_grounded_spec() -> None:
    """The defect itself, driven through the real routing path.

    Before the fix this returned an `IntentAction` carrying the malformed
    note instead — the pydantic error was raised inside `_route` and
    swallowed by the handler one frame up, so the run stayed green and the
    firm simply stopped producing work product.
    """

    actor, inner = await _actor([DECIDE_CREATE_DOCUMENT, AUTHOR_MEMO])
    action = await actor.get_action_attempt(
        (), IntentActionSpec(call_to_action="Decide and produce your next action.")
    )
    assert isinstance(action, IntentAction)
    assert isinstance(action.intent, DocumentEditIntent), (
        f"create_document did not route to a document intent: {action.intent!r}"
    )
    assert isinstance(action.intent.create, DocumentCreateSpec)
    assert action.intent.create.content_format == "formatted", (
        "the body that is present decides the format"
    )
    assert action.intent.create.path.endswith(".docx")
    assert inner.calls == 2


def test_both_create_call_sites_convert() -> None:
    """Neither path may hand the model's own object to the referee.

    A behavioural test covers the opportunistic path above; this covers
    the *shape*, because the scheduled path is the one that was already
    correct and the failure mode is a third caller added later. The whole
    defect was a call site that looked right: same predictor, same field,
    one `_create_spec` missing.
    """

    source = Path("src/simulation/persona/actor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", None) != "DocumentEditIntent":
            continue
        for keyword in node.keywords:
            if keyword.arg != "create" or isinstance(keyword.value, ast.Constant):
                continue
            sites.append((node.lineno, ast.unparse(keyword.value)))
    assert sites, "no DocumentEditIntent(create=...) call sites found — test is blind"
    for lineno, expression in sites:
        assert "_create_spec" in expression, (
            f"actor.py:{lineno} passes {expression!r} as `create`; an "
            "AuthoredDocument is not a DocumentCreateSpec and pydantic "
            "refuses it silently — route it through _create_spec"
        )


def test_a_failed_draft_is_remembered_in_workplace_words() -> None:
    """What the person remembers, and what the operator gets, differ."""

    class _Decision:
        class choice:
            action = "create_document"

    class _Spec:
        day = ""

    note = ProfessionalActorAct._malformed_draft_note(
        None,
        _Decision(),
        ValueError("create: Input should be a valid dictionary"),
        _Spec(),
    )
    text = note.bullets[0].text
    assert not _engine_words_in(text), (
        f"engine vocabulary reached a persona's memory: {text!r}"
    )
    assert "document" in text.lower(), f"the person should know what they dropped: {text!r}"
    assert note.engine_detail, "the operator's diagnostic must survive somewhere"


def test_every_action_verb_has_workplace_words() -> None:
    """An unmapped verb must not fall back to printing its own name.

    This is how the leak would return: a new verb added upstream, no test
    failing, and `schedule_meeting` quietly appearing in somebody's diary.
    """

    for verb in (
        "create_document",
        "revise_document",
        "send_email",
        "reply_email",
        "post_chat",
        "react_chat",
        "create_ticket",
        "update_ticket",
        "comment_ticket",
        "log_time",
        "schedule_meeting",
        "a_verb_invented_next_quarter",
    ):
        phrase = _work_in_hand(verb)
        assert verb not in phrase, f"{verb!r} names itself to the persona: {phrase!r}"
        assert not _engine_words_in(phrase), f"{verb!r} -> {phrase!r}"


def test_an_engine_fault_reaches_the_operator_and_nobody_else() -> None:
    rejection = IntentRejection("unsupported intent kind foo", engine_fault=True)
    assert rejection.guidance == ""
    assert "unsupported" in str(rejection)


def test_a_parse_failure_keeps_its_diagnostic_off_the_persona() -> None:
    rejection = IntentRejection(
        "doc-000001 declares spreadsheet but its content is not in that form",
        detail="1 validation error for SpreadsheetContent review_note Extra inputs",
    )
    assert not _engine_words_in(rejection.guidance), (
        f"the persona-visible half still carries engine words: {rejection.guidance!r}"
    )
    assert "validation error" in rejection.detail, "the operator still gets the parser's words"


async def test_a_guidance_free_rejection_makes_no_memory() -> None:
    """The referee may refuse without teaching, and then teaches nothing."""

    stream = MemoryStreamComponent(person_id="per-daniel-reyes", entity_name="daniel")
    event = Event(
        seq=1,
        event_id="evt-000001",
        time=0,
        tag="sim.gm.note",
        source="gm",
        payload=SimGmNotePayload(
            kind="sim.gm.note",
            note="Rejected action from daniel: unsupported intent kind foo",
            guidance="",
            entity="daniel",
        ),
    )
    await stream.pre_observe(event)
    gists = [record.gist for record in stream.records()]
    assert not any("unsupported" in gist for gist in gists), (
        f"an engine fault became a memory: {gists!r}"
    )


async def test_actionable_guidance_is_still_remembered() -> None:
    """The correction loop is the reason this channel exists; keep it."""

    stream = MemoryStreamComponent(person_id="per-daniel-reyes", entity_name="daniel")
    guidance = (
        "an email needs at least one recipient; name them by full name as "
        "they appear in the thread or the directory"
    )
    event = Event(
        seq=1,
        event_id="evt-000001",
        time=0,
        tag="sim.gm.note",
        source="gm",
        payload=SimGmNotePayload(
            kind="sim.gm.note",
            note=f"Rejected action from daniel: {guidance}",
            guidance=guidance,
            entity="daniel",
        ),
    )
    await stream.pre_observe(event)
    gists = [record.gist for record in stream.records()]
    assert any("recipient" in gist for gist in gists), (
        f"a correctable mistake taught the persona nothing: {gists!r}"
    )


def test_no_rejection_reason_speaks_engine() -> None:
    """Every refusal the referee can raise, read as a persona would read it.

    Static, and deliberately so: the behavioural tests above cover the
    paths this world actually walks, and this one covers the ones it has
    not walked yet. A reason that names a class, a field or an action verb
    is either an engine fault — in which case say so and it stays with the
    operator — or it needs rewording into something a colleague would say.
    """

    source = Path("src/simulation/gm/grounded.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", None) != "IntentRejection":
            continue
        if any(
            keyword.arg == "engine_fault"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value
            for keyword in node.keywords
        ):
            continue
        if not node.args:
            continue
        # The reason literal with its interpolations blanked out: `{ref!r}`
        # is a runtime value, and what is being read here is the wording
        # around it.
        reason = ast.unparse(node.args[0])
        prose = "".join(
            "" if index % 2 else part
            for index, part in enumerate(reason.replace("{", "\x00{").split("\x00"))
        )
        found = _engine_words_in(prose)
        if found:
            offenders.append((node.lineno, found, prose[:90]))
    assert not offenders, (
        "these refusals speak engine to a persona at importance 10; reword "
        f"them or mark them engine_fault=True:\n{offenders}"
    )


def test_no_caught_exception_is_interpolated_into_a_reason() -> None:
    """The leak that actually shipped, checked by its own shape.

    `test_no_rejection_reason_speaks_engine` blanks interpolations before
    reading the wording — it has to, because `{ref!r}` is a runtime value
    and the wording around it is the thing being judged. That blanking is
    a hole exactly the size of this defect: the reason read

        f"... does not parse as one ({error}); send the structured JSON"

    whose prose, with the interpolation removed, is unimpeachable. The
    engine words arrived at runtime, from the exception.

    So this reads the other half. Inside `except ... as error`, the name
    bound to the exception may reach `detail=`, which the operator sees,
    and never `reason`, which becomes somebody's most important memory.
    """

    source = Path("src/simulation/gm/grounded.py").read_text(encoding="utf-8")
    offenders = []
    for handler in (
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler) and node.name
    ):
        for call in (n for n in ast.walk(handler) if isinstance(n, ast.Call)):
            if getattr(call.func, "id", None) != "IntentRejection" or not call.args:
                continue
            names = {
                n.id for n in ast.walk(call.args[0]) if isinstance(n, ast.Name)
            }
            if handler.name in names:
                offenders.append((call.lineno, handler.name))
    assert not offenders, (
        "a caught exception is interpolated into a persona-visible reason at "
        f"{offenders}; pass it as detail= instead — the reason becomes a "
        "memory at importance 10 and the exception's words are not the "
        "firm's words"
    )
