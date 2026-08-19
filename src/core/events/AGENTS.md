# The event vocabulary

* The payload union in `payloads.py` is **closed**: every kind is declared
  there and in `TAG_REGISTRY`, nowhere else. Workplaces never add kinds. A
  test asserts union and registry match exactly — extend both plus the
  sample in `tests/fixtures/payload_samples.py`.
* Within a schema version, evolution is **additive only**: new kinds or new
  optional fields. Anything else bumps `SCHEMA_VERSION` and invalidates
  every recorded run.
* `tag == payload.kind` always; the envelope validator enforces it.
* `sim.*` payloads are offstage: never projected into agent-facing tools,
  never counted by realism metrics.
* Content lives in exactly one place. An email attachment is a
  `document.created` plus a reference; a revision stores full text, not a
  diff. Design fields so a per-tool database projection is lossless.
* The send is the fact: no inbound/outbound distinction in tags — that is a
  per-viewer property computed by views.
* New references (ids pointing at other events) need a matching resolution
  check in `worldlog/validate.py`, with a corruption test.
