# M4 Z.ai Trial Provider Edge — Independent First-Pass Review

## Protocol

This review is the independent maintainer-side first pass over the pushed branch `m4/zai-model-trial-driver` before any Codex review. Codex has not been invoked for this increment.

Reviewed base: `main` at `3d95b461e8c226fdf0eef69dccbd66e4e256c9f1`.

Reviewed branch tip before this review record: `dd15d31f5c7c9024eaf16fe9b0f0bfbe93a261b0`.

The branch is four commits ahead of the reviewed base and changes exactly five implementation/documentation files before this review record. GitHub Actions `schema-validation` run `36577427010` completed successfully on the exact reviewed tip, including the Z.ai provider-edge validator.

## Review surface

The review covered:

- the provider-selection and CLI contract in `scripts/run_m4_model_extraction_trial.py`;
- Z.ai credential ingestion and redaction;
- base-URL selection and trust boundaries;
- redirect behavior;
- request serialization and exact-prompt handoff;
- HTTP transport and response parsing;
- strict model-output boundary reuse;
- report trace, qualification flags, and local evidence provenance;
- deterministic validator coverage;
- schema-validation workflow integration;
- trial documentation and the prior maintainer first-pass record;
- the unchanged `services/intelligence/model_extraction_trial.py` boundary to verify that the new edge does not create a second extraction pipeline or new canonical authority;
- current official ZCode/Z.ai documentation for the Coding Plan versus general OpenAI-compatible endpoints and current GLM-5.3 reasoning defaults.

## Findings register

### IRZ-01 — HIGH — environment credential control characters can defeat exact-secret redaction

**Area:** secret handling / failure diagnostics.

**Finding:** `require_zai_api_key()` checks `api_key.strip()` for emptiness but returns the original string verbatim. A copied environment value containing a trailing newline or another control character therefore reaches the HTTP Authorization header. Python's HTTP stack can reject such a header and render the value in an escaped representation (for example, a literal newline becomes `\\n`). The generic exception path formats `exc!r` and then calls `redact_secret()` with the original secret containing the literal control character. Exact string replacement no longer matches the escaped representation, so credential material can survive into the raised `RuntimeError`; the runner can persist that message as `execution_error` in the trial report.

**Evidence:** the branch explicitly documents verbatim credential handling as an accepted limitation, while the implementation uses exact `str.replace(secret, ...)` redaction after `repr(exc)` in the generic transport-exception path.

**Why it matters:** the principal security requirement for this edge is that `ZAI_API_KEY` never appears in logs or reports. This path violates that invariant for plausible copy/paste whitespace/control-character input.

**Severity:** HIGH.

**Confidence:** HIGH.

**Required remediation before live trial:** normalize or reject leading/trailing whitespace, reject all HTTP-illegal control characters before constructing any request, and regression-test a credential containing newline/tab/control characters through the real failure-formatting path. Redaction must always operate on the exact credential actually sent.

### IRZ-02 — HIGH — current endpoint default assumes Coding Plan scope for a non-coding extraction workload and permits arbitrary credential destinations

**Area:** provider entitlement / secret destination trust boundary.

**Finding:** the runner defaults Z.ai to `https://api.z.ai/api/coding/paas/v4`, with an implementation comment asserting that the trial credentials are Coding Plan keys. That account fact was not established by the reviewed repository. Current official ZCode documentation states that the Coding Plan endpoint is for coding scenarios only and that the general OpenAI endpoint `https://api.z.ai/api/paas/v4` is for resource-package/prepaid general API usage. This M4 workload is a structured extraction evaluation rather than a coding task. Separately, `validate_zai_base_url()` accepts any HTTPS host/path without query/fragment/userinfo, so an override can send the bearer credential to an arbitrary HTTPS origin even though this increment only needs the two documented Z.ai routes.

**Evidence:** `ZAI_DEFAULT_BASE_URL` is the Coding Plan route; `resolve_zai_base_url()` silently selects it when no override is supplied; base-URL validation does not constrain hostname or path. Official provider documentation: `https://zcode.z.ai/en/docs/configuration` (Coding Plan OpenAI URL `/api/coding/paas/v4`, coding scenarios only; general OpenAI URL `/api/paas/v4` for resource packages/prepaid balance).

**Why it matters:** a live evaluation should not rely on an unverified entitlement assumption, and a bearer credential should not be sent to an arbitrary host absent a forcing function for custom provider proxies. Either issue can invalidate or unnecessarily expand the live-trial trust boundary.

**Severity:** HIGH.

**Confidence:** HIGH on the implementation facts; HIGH that the workload is non-coding; account entitlement itself remains UNKNOWN.

**Required remediation before live trial:** do not silently default to the Coding Plan route. Require an explicit provider route/account mode or use the general API route only when the operator confirms an appropriate general-API key/balance. Narrow the accepted endpoints to the documented `api.z.ai` routes needed by this trial; do not accept arbitrary hosts unless a separate, explicit custom-endpoint requirement is introduced and reviewed.

### IRZ-03 — MEDIUM — provider-envelope JSON remains ambiguous while the audit hash covers only selected assistant content

**Area:** response integrity / auditability.

**Finding:** `zai_response_content()` uses plain `json.loads()` for the provider envelope. Duplicate object keys are therefore last-key-wins, and non-finite numeric constants are accepted by Python's default parser. The downstream model-output content is strict, but the transport envelope selecting that content is not. Because `raw_output_sha256` hashes the extracted assistant content rather than the raw HTTP envelope, an ambiguous envelope is not detectable from the persisted trial artifact.

**Evidence:** the prior first-pass record explicitly lists envelope parser leniency as an accepted limitation; the implementation calls `json.loads(body.decode("utf-8"))` without duplicate-key or finite-number guards.

**Why it matters:** the trial's evidence model relies on unambiguous model-output selection and exact traceability. Silent duplicate-key resolution weakens that evidence boundary even if malformed candidate content is later rejected.

**Severity:** MEDIUM.

**Confidence:** HIGH.

**Recommended remediation:** apply duplicate-key and non-finite-number rejection to the provider envelope as well. Extra ordinary provider fields may remain allowed; only ambiguous/invalid JSON semantics need fail closed.

### IRZ-04 — MEDIUM — GLM-5.3 reasoning configuration is implicit and therefore absent from the trace

**Area:** reproducibility / performance evidence.

**Finding:** the Z.ai request carries only `model`, `messages`, and `stream`. Current GLM-5.3 documentation says thinking is enabled and `reasoning_effort` defaults to `max`; disabling thinking is no longer supported. The runner therefore depends on an implicit provider default that materially affects latency, token/credit consumption, and potentially extraction quality, while the report does not record the effective setting.

**Evidence:** the request payload intentionally omits reasoning configuration. Current provider documentation: `https://z.ai/blog/glm-5.3` states `thinking.type=enabled` and `reasoning_effort` values `low|high|max`, with `max` as the default.

**Why it matters:** the bounded trial is intended to produce reviewable quality/performance evidence. A provider-managed default can change independently of the code and prevents a future reviewer from reconstructing the effective inference configuration from the report.

**Severity:** MEDIUM.

**Confidence:** HIGH.

**Recommended remediation:** explicitly pin the supported GLM-5.3 reasoning configuration in the request and record it in `provider_edge`. To preserve current effective behavior without making a new quality judgment, pin `thinking.type=enabled` and `reasoning_effort=max`, or expose a validated CLI option with an explicit default and trace it.

### IRZ-05 — MEDIUM — local live-trial evidence is not bound to the reviewed source revision

**Area:** evidence provenance / operability.

**Finding:** the GitHub Actions Copilot artifact is naturally associated with a workflow `head_sha`. The new Z.ai path is intentionally local, but report v0.4 contains no Git revision or workspace-state evidence, and the local-execution documentation does not require a sidecar recording them. A report can therefore be generated from a modified working tree while looking indistinguishable from one produced at the reviewed branch tip.

**Evidence:** the report includes corpus/provider/model/adapter/provider-edge trace but no source revision; the local execution instructions only set credentials/endpoint and run the script.

**Why it matters:** live model evidence should be attributable to the exact reviewed implementation before it is used to qualify M4 claims.

**Severity:** MEDIUM.

**Confidence:** HIGH.

**Required remediation before live evidence is accepted:** bind the run to the reviewed source. Prefer a report field or deterministic sidecar containing at minimum `git_head`, tracked-worktree cleanliness, tool/runtime versions, and the final report SHA-256. The live run must be executed from the exact independently reviewed tip with no tracked modifications.

### IRZ-06 — MEDIUM — HTTP response body is unbounded despite the trial's bounded design

**Area:** resource exhaustion / failure containment.

**Finding:** `zai_http_post_json()` calls `response.read()` and `HTTPError.read()` without a byte limit. A malfunctioning or compromised endpoint can therefore cause unbounded memory consumption before any JSON or output-boundary validation runs.

**Evidence:** both success and HTTP-error paths read the entire response body.

**Why it matters:** this trial is explicitly bounded. Network response size should be bounded before parsing, especially because the expected assistant JSON is small and provider failures may return arbitrary diagnostic bodies.

**Severity:** MEDIUM.

**Confidence:** HIGH.

**Recommended remediation:** define a conservative maximum response size, read at most `limit + 1`, and fail closed when exceeded. Apply the same bound to non-2xx diagnostic bodies.

### IRZ-07 — LOW — review/documentation claims drift from the actual provider-neutral implementation

**Area:** documentation / review provenance.

**Finding:** the prior first-pass record says the response path performs `content-type validation`, but the transport returns only status/body and never inspects response headers. The trial document also still describes `input_sha256` as the exact prompt passed to Copilot CLI rather than the selected provider edge, and its general cost paragraph attributes the unmeasured-cost rationale only to the CLI even though the Z.ai report has a separate rationale.

**Why it matters:** these do not create runtime authority or candidate leakage, but the review record and trial contract should describe exactly what is implemented.

**Severity:** LOW.

**Confidence:** HIGH.

**Recommended remediation:** remove the unsupported content-type claim unless header validation is actually added; make prompt-hash and cost wording provider-neutral.

## Open questions / missing evidence

1. The user's API key account type and permitted workload scope are not established in repository evidence. No live call should be made until the endpoint/account mode is explicit.
2. No live Z.ai response has been observed, so served model identifier, response `finish_reason`, token usage, latency, and actual quality remain UNKNOWN.
3. Socket timeout versus total wall-clock timeout remains an accepted bounded-trial limitation; a slow-drip response can exceed the configured duration.
4. The provider may expose served-model and token-usage metadata in the response envelope, but this increment intentionally does not persist it; whether that is needed for later M4 observability remains a separate decision.

## Areas reviewed with no blocking issue found

- The branch is exactly four commits ahead of the verified base before this review record; no unrelated implementation files are changed.
- `services/intelligence/model_extraction_trial.py` remains unchanged and continues to own the synthetic/public-only preflight, exact prompt construction, strict candidate JSON parsing, allowlists, candidate-only authority, and blocked-before-invocation behavior.
- The Z.ai edge returns only assistant text through the existing invoker seam; it does not create a second truth store or new canonical mutation/publication path.
- The request exposes no tools, function calling, MCPs, repository/file/shell access, retrieval, or agent actions.
- Redirect refusal is materially improved: the dedicated opener installs only the refusing redirect handler, and 3xx becomes a fail-closed provider error rather than a credential-forwarding redirect.
- Non-2xx status, timeout, URL errors, malformed response shapes, missing content, and non-text content fail closed into trial integrity failures.
- The exact assistant text is passed untrimmed to the existing extraction boundary, preserving the intended model-output hash semantics at that boundary.
- Copilot remains the default provider and its established invocation/credential behavior is preserved.
- The new deterministic validator is included in `schema-validation`, and GitHub Actions run `36577427010` succeeded on the reviewed exact tip.
- Qualification flags still deny canonical mutation/publication authority and keep production/representative-scale qualification false.

## First-pass freeze

**FIRST-PASS REVIEW COMPLETE.**

Known findings: IRZ-01 through IRZ-07 above.

Blocking before live Z.ai trial: IRZ-01, IRZ-02, IRZ-05. IRZ-03, IRZ-04, and IRZ-06 should also be remediated before the independent second review because each is narrow, testable, and directly affects auditability or failure containment. IRZ-07 is documentation/review-record cleanup.

Codex has not been invoked. This document freezes the independent first-pass view before any Codex findings can influence discovery. After remediation, use a separate reconciliation/remediation record rather than rewriting this frozen first-pass baseline.