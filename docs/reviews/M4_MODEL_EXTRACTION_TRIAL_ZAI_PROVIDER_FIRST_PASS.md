# M4 Z.ai Trial Provider Edge — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review. It was performed before any Codex review request for this increment.

The review follows the repository rule that discovery and first-pass defect finding belong to the maintainer review; Codex is an independent second reviewer only after this baseline is frozen.

## Baseline and review surface

Base branch / merge base:

- `main` at `3d95b461e8c226fdf0eef69dccbd66e4e256c9f1` ("M4: add bounded real-model extraction trial harness (#28)"), verified against `origin/main` before push.

Provenance correction: the first version of this record cited the base as `3d95b462e6a5d5c1c74c2a9e5e2f0d21ab55a1e0`. That full SHA was erroneous — only the seven-character prefix `3d95b46` had been obtained from command output and the remaining digits were not verified before writing. The SHA above is the verified value from `git rev-parse main` and `git ls-remote origin main`.

Branch commit chain on `m4/zai-model-trial-driver` (all versus the base above):

1. `88e3e66c1d03cc8bf0699961af3783a58ef626e8` — Z.ai provider edge implementation, deterministic validator, CI step, and trial documentation (the originally reviewed implementation baseline);
2. `31ae08df171e821947aecf6e755df1571914965e` — first version of this review record (superseded by this revision);
3. `23d6d2f6bc7942479775956444260e079ac9294b` — remediation of FPZ-04 (fail-closed redirect refusal in the transport) with regression tests;
4. this commit — corrected provenance, FPZ-04 register entry, and the exact-head freeze below.

Net implementation/documentation surface at the frozen tip:

1. `.github/workflows/schema-validation.yml`
2. `docs/M4_MODEL_EXTRACTION_TRIAL.md`
3. `docs/reviews/M4_MODEL_EXTRACTION_TRIAL_ZAI_PROVIDER_FIRST_PASS.md`
4. `scripts/run_m4_model_extraction_trial.py`
5. `scripts/validate_m4_model_extraction_trial_zai_provider.py`

`services/intelligence/model_extraction_trial.py` and every other validator, service, schema, and fixture are byte-identical to `main`. The increment deliberately touches only the provider edge of the existing trial runner, one new deterministic validator, the CI workflow step that runs it, the trial document, and this record.

## Intent and authority boundary

The forcing function is the M4 requirement to execute a bounded real-model extraction trial, now with a second local provider edge beside the pinned Copilot CLI driver.

The increment is correctly narrow:

- one provider-independent SDA trial boundary, unchanged;
- a Z.ai OpenAI-compatible HTTP driver selected only for trial use, not as a production model-platform adoption;
- no second extraction pipeline: prompt construction, strict finite/duplicate-key JSON parsing, candidate-only `AIExtractionRun` construction, case allowlists, quality scoring, latency/throughput reporting, and the report shape are shared with the Copilot path;
- the credential is read only from the `ZAI_API_KEY` environment variable, never accepted as a command-line argument, never logged, never serialized, never committed;
- the request body carries `model`, `messages` (exactly one user message containing the rendered SDA trial prompt), and `stream: false` — no tools, function calling, repository/file/shell access, retrieval, MCPs, or autonomous actions;
- only the exact assistant response text returns to the extraction boundary, unmodified;
- canonical mutation, publication, Resolver/Verifier, and human-review authority remain untouched.

No canonical mutation or publication authority was found in the modified runner, the new validator, the workflow step, or the documentation.

## Multi-pass review

### Intent / architecture

PASS.

The provider-specific choice is confined to the live runner edge, exactly as the Copilot driver was. The Z.ai driver plugs into the same `execute_trial_case` invoker seam; the domain boundary in `services/intelligence/model_extraction_trial.py` was not modified. The documentation explicitly frames the driver as a trial provider option, and the claim-ceiling section now states that neither provider edge constitutes a production model-platform selection.

### Structure / data flow

PASS.

Request path: rendered prompt → `zai_request_payload` (stdlib JSON, no extra keys) → `zai_http_post_json` (stdlib urllib, Authorization header from the environment) → `zai_response_content` (fail-closed status/shape/content-type validation) → exact assistant text → unchanged strict extraction boundary. Response text is never trimmed, re-encoded, or otherwise altered before hashing. Failures raise `RuntimeError`, which the existing runner loop already converts into per-case integrity failures with no candidate leakage; the run exit code remains nonzero when integrity fails.

The provider trace is explicit: report `provider` (`zai-openai-compatible-api`), `requested_model` (default `glm-5.3`, overrideable), and a new `provider_edge` object recording driver, resolved base URL and its source (`flag` / `env` / `default`), credential source, transport, and tool exposure. `model_version` remains `provider-managed-unknown` for the same reason as the Copilot edge: the served checkpoint identity is not exposed and is not invented.

### Correctness / integrity

PASS after remediation.

The exact prompt reaches the wire as the only model input, verified by the fake transport in the new validator; `input_sha256` in the resulting runs therefore continues to hash the true model input. The endpoint resolution order (flag → `ZAI_BASE_URL` → Coding Plan default) is explicit and reported, and the two documented routes (`/api/coding/paas/v4` versus `/api/paas/v4`) are asserted distinct rather than treated as interchangeable. Backward compatibility holds: the default provider is still `copilot`, its default model still resolves to `gpt-5.4`, its credential gate is unchanged, and `--base-url` is rejected for the copilot provider.

### Failure modes

PASS after remediation.

Fail-closed coverage is deterministic and tested for: missing `ZAI_API_KEY`; HTTP 401/500/300; transport timeout; `URLError`; arbitrary transport exceptions; malformed and undecodable response bodies; root-not-object; missing/empty `choices`; non-object choice; missing message; null content; non-text content. Every failure surfaces as a bounded `RuntimeError` and becomes a trial integrity failure; candidates never leak and canonical state is never touched.

One truncation-vs-redaction ordering defect was found and is recorded as FPZ-01 below; it is remediated and regression-tested.

### Security / operational sensitivity

PASS after remediation.

The credential exists only in the environment and the Authorization header. All raised messages are redacted against the live key value before bounding, including the straddling case where an echoed key crosses a truncation boundary (FPZ-01). The report, stdout summary, and `provider_edge` trace are asserted free of the credential by the validator. Base-URL validation rejects non-HTTPS schemes, embedded userinfo, missing hosts, and query/fragment components. The synthetic corpus and the operational-sensitivity preflight of the shared boundary are unchanged, so restricted operational-style content still fails before any provider invocation.

### Operability

PASS.

The runner reuses the existing `--fixture`, `--output`, `--max-cases`, and `--timeout-seconds` controls, adds `--provider`, `--model` (now provider-aware), and `--base-url`, and prints the same JSON summary shape (plus `provider`). The report version is bumped to `m4-model-extraction-live-trial-v0.4` because `provider_edge` is a new field; no existing field was renamed or removed. Local execution instructions, including the Coding Plan versus prepaid endpoint distinction, are documented.

### Maintainability / provider independence

PASS.

The driver lives entirely in the runner, beside the Copilot driver; the service boundary remains provider-independent and byte-identical to `main`. The HTTP transport is an injectable parameter, so all new tests run against a fake transport with zero network access and zero model-credit consumption; CI never calls Z.ai by design, and no Z.ai GitHub Actions workflow is added. The new validator imports the shared fake corpus output rather than duplicating it.

### Evidence / claim ceiling

PASS.

The documentation frames the driver as a trial provider option, keeps `representative_batch_scale_qualified` and `production_model_pipeline_qualified` false, records cost as unmeasured for both providers, and adds no model-quality or scale claim. This increment establishes only that the Z.ai edge is implemented and deterministically validated; it does not qualify extraction quality, latency, throughput, or cost on the live service.

## First-pass findings register

### FPZ-01 — HIGH — error-message truncation ran before credential redaction

The HTTP error excerpt was truncated to 300 bytes before redaction was applied by the invoker. A provider or proxy that echoed the Authorization value back across that byte boundary would have leaked a partial credential into an error message (and potentially into a report's `execution_error` field).

Remediated before freeze: the excerpt bound was raised to 4096 bytes, redaction now runs on the full message, and the 512-character bound is applied only after redaction. Regression-tested with a sentinel key straddling the old 300-byte boundary (`validate_m4_model_extraction_trial_zai_provider.py`, "excerpt boundary" case).

### FPZ-02 — MEDIUM — expected argparse failure printed usage text to stderr

The `--base-url` + copilot rejection test emitted the argparse usage banner into CI logs, obscuring real failures. Remediated: the test wraps the expected failure in `redirect_stderr`.

### FPZ-03 — MEDIUM — quality-parity fixture initially used the un-reconciled fake output

The first version of the main()-level test answered `TRIAL-EN-DELIVERY` with the raw shared fake output, which includes a manufacturer-claim validity block that the reconciled gold expectation for that case rejects. The assertion failed, correctly. Remediated: the test applies the same `without_manufacturer_validity` transformation the reconciliation review established, with the rationale documented at the point of use. No production code was affected.

### FPZ-04 — HIGH (severity per independent-review direction) — automatic redirect following could forward the bearer credential

`urllib.request.urlopen` follows 3xx responses automatically and may re-POST the request — including the `Authorization` header — to the redirect target, on any origin. The first version of this record classified that as an accepted limitation because the endpoint is operator-controlled; the independent review direction rejected that classification, since a compromised, hijacked, or misconfigured endpoint could redirect the credentialed request elsewhere.

Remediated in `23d6d2f6bc7942479775956444260e079ac9294b`: the transport now uses a dedicated opener whose redirect handler refuses every redirect (`redirect_request` returns `None`, so urllib raises `HTTPError` with the 3xx status), which the existing fail-closed status handling turns into a trial integrity failure. The credential can therefore never be re-sent to any origin. Regression-tested: the handler is asserted to refuse 301/302/303/307/308, the transport opener is asserted to contain no redirect-following handler, and the fail-closed matrix already covers non-2xx statuses including 300.

### Documented limitations (accepted, not remediated)

- **Timeout semantics.** The stdlib timeout bounds socket connect/read operations, not total request wall-clock; a slow-drip response could exceed `--timeout-seconds` across reads. The Copilot subprocess timeout is a process wall-clock kill, so the two edges differ here. Accepted for the bounded trial; a wall-clock watchdog is future work if the driver is promoted.
- **Envelope parser leniency.** The transport envelope is parsed with plain `json.loads`, tolerating non-finite constants and duplicate keys at the envelope level. Only the assistant content string becomes data, and it passes through the strict finite/duplicate-key boundary unchanged, so envelope leniency cannot produce candidate records.
- **Verbatim credential.** `ZAI_API_KEY` is used exactly as provided, including surrounding whitespace; a mis-scoped value fails closed as HTTP 401 at the provider.
- **Base URL in the report.** `provider_edge.base_url` records operator configuration. It is not a credential, but a proxy URL could reveal internal topology; this is the operator's disclosure decision.

## Deterministic validation evidence

- The complete repository suite (all 38 `scripts/validate_*.py` validators: 37 baseline validators unchanged-green plus the Z.ai provider-edge validator) passed locally at implementation head `88e3e66c1d03cc8bf0699961af3783a58ef626e8`, again after the FPZ-04 remediation at `23d6d2f6bc7942479775956444260e079ac9294b`, and is re-run at the exact frozen tip (this record's commit) immediately before push, per the exact-head freeze protocol below.
- The `schema-validation` workflow triggers on every push to `m4/**`; the push of this exact tip therefore provides independent exact-head CI evidence on GitHub Actions.
- The new validator exercises: request fidelity and tool-free payload; environment-only credential with redaction including the truncation-straddle case; endpoint resolution precedence and URL validation; refusal of all redirect classes at the transport handler; a fifteen-case fail-closed matrix; identical strict JSON/candidate boundary outcomes; Copilot backward compatibility including credential gating; main()-level report trace, key non-leakage, and unchanged qualification flags; absence of governance imports in the runner.

No network call, no Z.ai request, and no model credit was consumed by any validation run.

## Explicitly unverified / unresolved

- No live Z.ai invocation has been made by this increment. Extraction quality, latency, throughput, cost behavior, and served-model identity on the live service remain unqualified until the bounded live trial is executed after this review and independently reviewed.
- The Coding Plan and prepaid endpoint routes were taken from current Z.ai documentation as relayed by the operator; only the route resolution logic is tested deterministically, and neither route has been exercised live by this increment.
- The default requested model is recorded as `glm-5.3`; whether the live service reports that exact identifier is unverified, and provider checkpoint identity remains `provider-managed-unknown`.
- Socket-level versus wall-clock timeout asymmetry with the Copilot edge remains open (see documented limitations).
- CI coverage is deterministic only; there is intentionally no Z.ai GitHub Actions workflow.

## Frozen maintainer baseline

Exact-head freeze protocol: a record cannot contain its own commit SHA, so the frozen baseline is defined structurally. The frozen tip is the branch tip containing this record — implementation commits `88e3e66c1d03cc8bf0699961af3783a58ef626e8` (edge) and `23d6d2f6bc7942479775956444260e079ac9294b` (FPZ-04 remediation), plus this record commit as the tip. The complete 38-validator suite is executed locally at that exact tip immediately before push, and the push itself triggers the `schema-validation` workflow on the same exact tip; both results constitute the exact-head evidence for the independent reviewer. The post-record tip SHA is reported out-of-band with the push and recorded in the eventual merge/second-review documentation.

This frozen baseline is the maintainer first pass for independent review. The live Z.ai trial must not be executed before that independent review completes.
