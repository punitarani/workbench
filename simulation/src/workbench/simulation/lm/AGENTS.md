# The LM layer

* `LMRequest.seed` is required and every call site threads a derived seed.
  Cassette keys are content hashes of the full request — replay is
  independent of call order and concurrency schedule. Do not add
  nondeterministic fields (timestamps, uuids) to requests.
* `ReplayLM` raises on a miss; `BudgetedLM` raises past budget. Keep it
  that way — a silent fallback turns a stale cassette into a corrupted run.
* Backends do **no prompt engineering**: no injected few-shots, no format
  coercion, no retries-with-rewording. Prompts belong to personas and
  adapters; a backend transports them. (`OpenRouterLM` disables provider
  reasoning mode because empty-content completions are transport concerns.)
* `WorkbenchLM` is the only DSPy touchpoint: typed_lm contract, litellm
  bypassed, dspy caching off. The cassette is the single replay mechanism.
* Empty or malformed provider responses raise `LMResponseError` with the
  body excerpt. Never fabricate a response.
