# Personas

* **The prompt surface is exactly: signature docstrings and field
  descriptions.** That is what GEPA optimizes and what the cassette keys.
  `rendering.py` emits *data* (threads, directories, situations), never
  instructions. Do not hide behavioral text in f-strings.
* **Grounding, not imagination.** Working memory state is the observed
  events themselves; every view is a fold over them, shared with
  `workbench.core.worldlog.views`. The memory stream stores typed
  cognition events, and retrieval scoring is integer-only — floats would
  cost byte-identity. A persona can only reference what actually
  happened. Keep it that way — no free-floating "memory" strings.
* The facts ledger records what a persona has committed to (draft
  summaries). Drafters receive it with a do-not-contradict instruction;
  audit cross-checks it.
* Refs returned by `decide` may be message ids, thread ids, names, or
  emails — the actor and GM resolve generously (`resolve_thread_ref`,
  person resolution) but never invent. If models keep producing a ref shape
  we reject, prefer widening resolution over loosening validation.
* Persona quality is tuned by recording a day, reading the world log, and
  adjusting instructions or structure — each recorded failure becomes a
  unit test with a canned completion before the fix lands.
