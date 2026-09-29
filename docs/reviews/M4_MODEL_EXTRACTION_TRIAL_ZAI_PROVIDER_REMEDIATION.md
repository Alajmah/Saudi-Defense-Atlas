# M4 Z.ai Trial Provider Edge — IRZ Remediation Record

## Protocol

This is the remediation record for the seven findings of the frozen independent first-pass review (`docs/reviews/M4_MODEL_EXTRACTION_TRIAL_ZAI_PROVIDER_INDEPENDENT_FIRST_PASS.md`, commit `4cf2656dc14d9b544d8f5b472e2a441d7d35c896`). It follows that record's closing instruction to use a separate remediation record rather than rewriting the frozen baseline. Neither frozen record is modified by this remediation.

Codex has not been invoked. No live Z.ai request has been made. No model credits were consumed.

## Baselines

- Frozen independent first pass: `4cf2656dc14d9b544d8f5b472e2a441d7d35c896` (verified by fast-forward pull and `git rev-parse HEAD`).
- Remediation implementation commit: `78a83d3661aaf0f4548083ec444bb7e494a181a4` ("M4: remediate IRZ-01..07 in the Z.ai trial provider edge").
- This record's commit is the branch tip at freeze; the post-record SHA is reported out-of-band with the push, per the established exact-head protocol.

Remediation surface: `scripts/run_m4_model_extraction_trial.py`, `scripts/validate_m4_model_extraction_trial_zai_provider.py`, `docs/M4_MODEL_EXTRACTION_TRIAL.md`. `services/intelligence/model_extraction_trial.py` remains byte-identical to `main`; no second extraction pipeline and no authority change exists in this remediation.

## Finding-by-finding remediation

### IRZ-01 — credential control characters — REMEDIATED

`require_zai_api_key()` now rejects, before any request can exist, credentials with leading/trailing whitespace, any control character (below 0x20 or DEL), or embedded quote/backslash characters. Rationale: the credential is redacted by exact substring replacement, so any character that HTTP rejects or that exception `repr()` formatting could escape (a literal newline rendered as `\n`) would let credential material survive into `execution_error`. With these characters rejected at ingestion, every credential that can actually be sent is one exact-substring redaction can always match. The prior redact-then-truncate ordering (FPZ-01) remains, and the straddling-boundary regression test still holds. New regression coverage: seven malformed-credential shapes (trailing newline, leading/trailing space, embedded tab, NUL, quote, backslash) each fail closed at ingestion; a clean credential is accepted.

### IRZ-02 — endpoint default and arbitrary credential destinations — REMEDIATED

The silent Coding Plan default is removed. The endpoint must now be selected explicitly: `--zai-endpoint coding-plan` or `--zai-endpoint prepaid` maps to the two documented official routes, or an explicit `--base-url` / `ZAI_BASE_URL` is used. Reaching none of these fails closed with a message naming the required selection. `validate_zai_base_url()` now accepts only the official `api.z.ai` host (no embedded credentials, no non-default port, `/api/` path prefix, no query/fragment); arbitrary HTTPS hosts and proxies are rejected, and custom endpoints are documented as requiring a separate reviewed forcing function. The resolved route and its source (`flag` / `env` / `endpoint:coding-plan` / `endpoint:prepaid`) plus the endpoint mode are recorded in `provider_edge`. The account type remains the operator's fact: the live trial operator must state it by selecting the route. Regression coverage: resolution precedence for all three sources, fail-closed on no selection, acceptance of both official routes, and rejection of ten invalid URLs including arbitrary hosts and ports.

### IRZ-03 — lenient provider-envelope parsing — REMEDIATED

`zai_response_content()` parses the provider envelope with the same strict semantics as the candidate boundary: duplicate object keys are rejected (no last-key-wins selection of `choices` or `message`), non-finite JSON constants (`NaN`/`Infinity`) are rejected, and non-finite numeric tokens such as `1e999` are rejected via a finite-float parser hook. Extra ordinary provider fields remain allowed, per the finding's remediation note. Regression coverage: duplicate `choices` keys, duplicate nested `message` keys, `NaN` constant, and `1e999` all fail closed.

### IRZ-04 — implicit reasoning configuration — REMEDIATED

The request payload now pins `thinking: {"type": "enabled"}` and `reasoning_effort: "max"` explicitly, matching the documented GLM-5.3 default (thinking enabled, `reasoning_effort` max, values `low|high|max`), so the pin records the effective inference configuration without making a new model-quality choice. The pinned configuration and an `explicitly_pinned` marker are recorded in `provider_edge.reasoning_configuration`. Regression coverage: the request payload key set is asserted to be exactly `model`, `messages`, `stream`, `thinking`, `reasoning_effort`, with the pinned values asserted. Wire-level acceptance of these two fields by the live service remains unverified until the live trial (fail-closed if rejected).

### IRZ-05 — report not bound to reviewed source — REMEDIATED

The report (now `report_version` `m4-model-extraction-live-trial-v0.5`) carries a `trial_context` object: git HEAD SHA and ref resolved from `.git` plumbing without a subprocess, tracked-worktree cleanliness via `git status --porcelain` (recorded as `null` with an explicit `git-unavailable` source only when git cannot run), Python/platform versions, and SHA-256 digests of the runner script, the provider-independent boundary module, and the evaluation corpus. A `<report>.sha256` sidecar pins the final report bytes (a report cannot contain its own digest), and the digest plus git HEAD are printed in the stdout summary. A dirty tracked worktree produces a loud stderr warning; the live-evidence acceptance rule is documented in the trial document: live evidence is accepted only with `tracked_worktree_clean: true` at the independently reviewed tip. Regression coverage: the validator compares `trial_context.git_head` against `git rev-parse HEAD`, cross-checks the plumbing reader, asserts boolean cleanliness, matches `runner_sha256`/`corpus_sha256` against the actual files, verifies the sidecar digest against the report bytes, and checks the stdout summary fields; the sentinel credential is asserted absent from the sidecar.

### IRZ-06 — unbounded response body — REMEDIATED

Any single provider response is bounded to 1 MiB (`MAX_RESPONSE_BYTES`). The real transport reads at most `limit + 1` bytes on both the success and HTTP-error paths through a shared capped-read helper, and `zai_response_content()` independently enforces the same bound so injected transports cannot bypass it. Above the bound the driver fails closed into a trial integrity failure; oversized non-2xx diagnostic bodies are replaced by a bounded marker rather than buffered. The bound is recorded in `provider_edge.max_response_bytes`. Regression coverage: an over-limit body fails closed through the invoker, and the capped-read helper is unit-tested at and above the limit.

### IRZ-07 — documentation/review wording drift — REMEDIATED

The trial document now describes `input_sha256`/`raw_output_sha256` provider-neutrally (the selected provider edge's process input / response content rather than "Copilot CLI" specifically) and states the unmeasured-cost rationale per provider. Correction to the frozen maintainer first-pass record, recorded here rather than by rewriting frozen history: that record's phrase `fail-closed status/shape/content-type validation` overstated the implementation — the response path validates status, response shape, and content type-of-text, but never inspects HTTP response headers. No response-header validation exists or is claimed by the remediated documentation.

## Deterministic validation evidence

- Complete repository suite at the remediation implementation commit `78a83d3661aaf0f4548083ec444bb7e494a181a4`: all 38 `scripts/validate_*.py` validators — **PASS**, including the extended Z.ai provider-edge validator (credential rejection, endpoint selection and host restriction, strict envelope parsing, response bound, git-bound provenance with sidecar).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` on the same exact tip on GitHub Actions.
- No network call and no model credit was consumed by any validation run. The dirty-worktree warnings emitted during local validation runs are the IRZ-05 warning operating as designed on the pre-commit working tree.

## Explicitly unverified / unresolved

- The account type and permitted workload scope of the operator's key remain unestablished in repository evidence; the live-trial operator resolves this by selecting the endpoint explicitly, and a mismatch fails closed at the provider.
- Wire acceptance of the pinned `thinking` / `reasoning_effort` request fields by the live service is unverified until the live trial; a rejection fails closed.
- Served model identifier, `finish_reason`, token usage, latency, cost behavior, and extraction quality remain UNKNOWN until the reviewed live trial runs.
- Socket-level versus wall-clock timeout asymmetry remains an accepted bounded-trial limitation (frozen record open question 3); the 1 MiB response bound now caps the slow-drip blast radius on body size but not on total elapsed time.
- Envelope-level provider metadata (usage, served model) is intentionally not persisted; whether M4 observability needs it is a separate decision (frozen record open question 4).

## Freeze

This record completes the remediation of IRZ-01 through IRZ-07 against the frozen independent first pass. The branch tip (this record's commit) plus the out-of-band post-record SHA and both exact-head validation results constitute the remediation baseline for the independent second reviewer. The live GLM-5.3 trial remains blocked until that second review completes.
