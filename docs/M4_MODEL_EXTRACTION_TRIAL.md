# M4 Bounded Real-Model Extraction Trial

## Status

Trial harness implemented with two reviewed provider edges (a pinned Copilot CLI driver and a local Z.ai OpenAI-compatible HTTP driver). The first bounded live Z.ai trial was executed on 2026-09-29 from clean `main` and reviewed; the report and SHA-256 sidecar are preserved as immutable evidence under `docs/evidence/m4/2026-09-29/`. Live provider mechanics and pre-invocation sensitivity gating are evidenced. Extraction quality remains unqualified. A second live rerun under the revised contract was executed on 2026-09-30 and is merged as reviewed evidence (PR #32; report v0.6 under prompt v0.4): role vocabulary, locator/cardinality, exact-number bounds, and structured abstention all behaved as intended, invoked-case exact-gold 2/5 with a derived substantive rate of 1/4. Downstream Resolver/Verifier and human-review preservation remains unqualified — not because of role vocabulary, which the rerun satisfied, but because the complete downstream path was never executed on the live candidates. The served model checkpoint is unknown (the requested model `glm-5.3` is what the evidence traces). The next rerun, under the semantics contract (prompt v0.6, report v0.7), is pending and requires a fresh run-specific operator entitlement attestation.

## Purpose

The M4 roadmap requires a bounded real-model extraction trial before the milestone can claim operating model-backed extraction. This increment satisfies the implementation forcing function without expanding model authority or selecting a production orchestration platform.

The trial reuses the accepted `AIExtractionRun` contract. It does **not** introduce a second truth store, canonical write path, scheduler, publication engine, or autonomous editorial worker.

## Scope

The trial is intentionally narrow:

- synthetic evaluation fixtures only;
- only queue items already shaped as claimed `candidate_extraction` work may reach the model;
- cases marked anything other than `public_non_operational` fail closed before model invocation;
- model output is candidate-only and must use local `CAND-*` identities;
- canonical SDA entity resolution remains the separate Resolver/Verifier step;
- JSON Schema plus the existing semantic extraction boundary must pass before candidates may be treated as accepted for candidate review;
- malformed, provenance-escaping, non-allowlisted, canonical-ID-producing, or schema-invalid output is converted into an auditable rejected `AIExtractionRun` with empty candidate arrays;
- no canonical mutation or publication authority is granted.

## Provider edge

`services/intelligence/model_extraction_trial.py` is provider-independent. It receives a caller-supplied text invoker and records provider/model/version/adapter trace in the existing extraction artifact.

The first live driver is GitHub Copilot CLI because the repository already uses GitHub Actions and the M4 roadmap now provides an explicit forcing function for one bounded real-model trial. This is a **trial driver selection**, not a production model-platform adoption.

The manual workflow pins:

- Copilot CLI package: `@github/copilot@1.0.88`;
- default requested model: `gpt-5.4` (overrideable at workflow dispatch);
- automatic CLI updates: disabled for the run.

Copilot exposes the requested model identifier to this harness, but not a stable provider checkpoint identifier. The `AIExtractionRun.model_version` field therefore records `provider-managed-unknown`; the report separately records the requested model and CLI version. Unknown provider checkpoint identity is not invented.

A second local provider edge, `--provider zai`, drives Z.ai's OpenAI-compatible HTTP API:

- default requested model: `glm-5.3` (overrideable with `--model`; the model remains explicit in the report trace);
- the exact rendered SDA trial prompt is sent as one user message and only the exact assistant response text returns to the extraction boundary;
- the request carries `model`, `messages`, `stream: false`, and an explicitly pinned reasoning configuration — thinking enabled, `reasoning_effort` `max`, matching the documented GLM-5.3 default so the effective inference setting is recorded rather than assumed — and nothing else: no tools, function calling, repository/file/shell access, retrieval, MCPs, or autonomous actions;
- the HTTPS call uses the Python standard library; no SDK dependency is added;
- the endpoint must be selected explicitly: `--zai-endpoint coding-plan` (`https://api.z.ai/api/coding/paas/v4`, Coding Plan keys, coding scenarios) or `--zai-endpoint prepaid` (`https://api.z.ai/api/paas/v4`, resource packages / prepaid balance, general API usage); an explicit `--base-url` / `ZAI_BASE_URL` override is accepted only as one of the two exact documented routes, and an explicit endpoint mode that contradicts the resolved URL fails closed; there is no silent default because the two routes are not interchangeable and the account type is the operator's fact to state;
- any single response is bounded to 1 MiB and fails closed above the bound;
- the driver fails closed on a missing `ZAI_API_KEY`, non-2xx responses, timeouts, malformed or ambiguous API responses (duplicate JSON keys and non-finite numbers are rejected at the envelope level too), missing or non-text assistant content, and any transport/provider exception; provider failures become trial integrity failures and never leak candidates or mutate canonical state.

Like the Copilot edge, the Z.ai driver is a **trial provider option**, not a production model-platform adoption. It introduces no second extraction pipeline: prompts, strict JSON parsing, duplicate-key rejection, candidate-only `AIExtractionRun` construction, quality scoring, latency/throughput reporting, and the report format are shared with the Copilot path through the provider-independent boundary.

A future model/provider may replace this edge without changing SDA domain schemas or authority semantics.

## Authentication

The manual workflow expects repository secret `COPILOT_GITHUB_TOKEN` containing a fine-grained personal access token with Copilot Requests permission.

The credential is used only by the Copilot CLI process. The workflow has repository `contents: read` permission and no canonical backend credentials.

The Z.ai edge reads its credential only from the `ZAI_API_KEY` environment variable. The key is never accepted as a command-line argument, never logged, never serialized into the report, and never committed. A credential containing leading/trailing whitespace, control characters, non-ASCII characters, quotes, or backslashes is rejected before any request exists, because header encoding or exception formatting could render such characters in an escaped form that defeats exact-substring redaction; every error message raised by the driver is redacted against the live key value before it is bounded.

## Model isolation

The programmatic Copilot invocation is deliberately narrower than a normal CLI session:

- non-interactive prompt mode with captured stdout;
- `--available-tools=ask_user` limits the model-visible tool set to one non-data/action tool;
- `--no-ask-user` simultaneously disables that remaining tool;
- `read`, `write`, `shell`, `url`, and `memory` permission kinds are denied as defense in depth;
- built-in MCP servers are disabled;
- custom instructions are disabled;
- remote control and remote export are disabled;
- experimental features and automatic CLI updates are disabled;
- an explicit model identifier is supplied.

On the pinned trial command surface, no repository-read, file-write, shell, URL, memory, delegation, or MCP tool is available for the model to use. The intended model input is therefore the runner-supplied trial prompt only. The workflow still depends on GitHub-hosted runner and Copilot service behavior and does not claim a hardware or network air gap.

## Prompt and trace contract

The prompt treats source text as untrusted data and explicitly instructs the model to ignore instructions embedded inside the source. It requires one strict JSON object with exactly:

- `evidence`;
- `entities`;
- `claims`;
- `events`.

The prompt also supplies a case-specific allowlist for Claim predicates and Event types. Output outside those allowlists is rejected before candidate review.

Prompt template `v0.6` additionally fixes the representation conventions that the first live trial showed were under-specified. The role vocabulary is a canonical contract; the remaining rules are **bounded-trial normalizations** — grounded in the canonical model where it speaks, and chosen for this single-document synthetic corpus where it is silent. None were derived from observed model output. Rules noted as enforced fail closed at the candidate boundary with a dedicated check; rules noted as prompt-instructed are guidance the evaluator scores but the boundary does not mechanically police:

- Event participant roles must come from the canonical SDA role vocabulary (`buyer`, `seller`, `contractor`, `operator`, `recipient`, `manufacturer`, `host`, `participant`, `observer`, `supplier`, `other`), supplied to the model as `ALLOWED_EVENT_ROLES` and enforced at the candidate boundary with the dedicated `event-role-vocabulary` rejection check; a malformed `participants` value (scalar, string, or non-object entries) is rejected as `event-participants-shape` rather than aborting the run;
- a specific named model or variant of an equipment family is typed `equipment_variant`, the family or design itself `equipment` (prompt-instructed; both types remain schema-valid, so the boundary does not enforce typing);
- an exact numeric quantity sets `value` and leaves `lower_bound`/`upper_bound` null (`exact-quantity-bounds` rejection) — a trial normalization consistent with the ontology's precision-or-bounds concept; the canonical `number_value` schema defines nullable bounds and does not by itself encode this rule;
- when any substantive Entity, Claim, or Event is emitted, exactly one document-level Evidence record with the locator object exactly `{"fragment": "source-text"}` and no additional keys (`evidence-cardinality` and `evidence-locator` rejections); complete abstention returns all four arrays empty, including evidence, and reaches the intended `no-substantive-candidates` path — a trial normalization for this bounded single-document corpus; the canonical ontology and Evidence schema do not impose one record per Document and permit multiple Evidence records and one-or-more evidence links;
- allowlisted predicates and event types are permissions, not requirements: when a proposition cannot be represented without changing its subject, value, or meaning, the model must omit the record (prompt-instructed; scored by the evaluator, not mechanically enforced).
- Event participant-role selection follows the bounded-trial annotation conventions of `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md` (stated manufacture → `manufacturer`, including in delivery events; contract-signature company party → `contractor`; `supplier` only when supply is all the source states; exercise/training attendance → `participant`) — evaluated, not enforced;
- a numeric unit is the head noun of the counted-class phrase the source states, with modifiers removed ("12 trainer aircraft" → `aircraft`); designation-only counts keep the designation as stated — evaluated, not enforced.

Trace semantics are exact at the adapter boundary:

- `prompt_trace.template_sha256` hashes the immutable prompt template;
- `input_sha256` hashes the exact rendered prompt string passed to the selected provider edge (the Copilot CLI process input or the Z.ai HTTP request body);
- `raw_output_sha256` hashes the exact assistant response text returned by the selected provider edge (captured CLI stdout or HTTP response content), including surrounding whitespace;
- the run identity includes invocation timestamps so separate invocations do not collapse merely because their input and output hashes match.

Raw model output is not persisted in the report; only its hash and the validated/rejected typed candidate projection are retained.

## Evaluation corpus

`tests/fixtures/m4-model-extraction-eval.json` is synthetic and non-canonical. It includes bounded cases for:

- English manufacturer/delivery extraction;
- Arabic contract/event extraction;
- procurement quantity versus delivered/operational ambiguity;
- prompt-injection text embedded in a source;
- insufficient evidence / refusal to force a substantive extraction;
- restricted operational-style content that must be blocked before model invocation.

The fixtures exist only to evaluate extraction mechanics and do not assert facts about real forces, units, locations, readiness, or stock levels.

## Deterministic CI

`scripts/validate_m4_model_extraction_trial.py` uses a deterministic fake invoker. CI therefore proves the harness invariants without network access or model-credit consumption:

1. restricted or non-candidate work never reaches the invoker;
2. prompt framing preserves the source while treating it as untrusted data;
3. exact prompt and raw-response hashes are retained;
4. distinct invocations receive distinct run identities;
5. the live CLI command exposes no usable data/action tool and grants no broad tool authority;
6. strict JSON envelope is required;
7. case predicate/Event allowlists are enforced;
8. out-of-scope Document provenance is rejected;
9. model-produced canonical entity references are rejected;
10. existing `AIExtractionRun` candidate/reference closure remains authoritative;
11. downstream JSON-Schema failure is isolated into a rejected run with zero candidate leakage;
12. accepted and rejected runs retain zero canonical-mutation and publication authority;
13. non-canonical participant roles, malformed `participants` values (including scalars), mirrored exact-quantity bounds, extra Evidence records, quoted or extended locators, and candidate-boundary rejections each fail closed with a dedicated check id, empty candidates, and bounded pre-clear count diagnostics, and an accepted run carrying `rejection_diagnostics` is schema-invalid;
14. the canonical Event-role vocabulary, the Resolver/Verifier role set, the candidate schema enum, and the trial's `CANONICAL_EVENT_ROLES` are asserted identical, so vocabulary drift fails CI;
15. a fully abstaining envelope still reaches the `no-substantive-candidates` path with all-zero pre-clear diagnostics, never a convention rejection.

`scripts/validate_m4_model_extraction_trial_zai_provider.py` adds deterministic coverage for the Z.ai provider edge, again with no network access and no model-credit consumption. It injects a fake HTTP transport and verifies: the exact rendered prompt is the request payload input; the request carries no tool surface and pins the reasoning configuration; the environment-only credential is character-rejected and redacted from errors, stdout, report, and sidecar; explicit coding-plan/prepaid endpoint selection with no silent default and base-URL validation restricted to official `api.z.ai` routes; strict duplicate-key/non-finite provider-envelope parsing; the bounded response size; git-bound report provenance with a matching SHA-256 sidecar; fail-closed HTTP/timeout/malformed-response behavior; the identical strict JSON/candidate boundary as the Copilot path; backward compatibility of the Copilot path; and the absence of any governance/mutation import in the runner.

## Live trial report

`scripts/run_m4_model_extraction_trial.py` writes one JSON report containing:

- corpus/provider/requested-model/CLI/adapter trace;
- a `provider_edge` trace recording the driver, resolved base URL and its source (`flag` / `env` / `endpoint:coding-plan` / `endpoint:prepaid`), endpoint mode, credential source, transport, tool exposure, response-size bound, and pinned reasoning configuration for the selected provider;
- a `trial_context` object binding the report to the exact source revision: git HEAD SHA and ref, tracked-worktree cleanliness, Python/platform versions, and SHA-256 hashes of the runner, the provider-independent boundary module, and the evaluation corpus;
- a `<report>.sha256` sidecar with the final report's SHA-256 digest, also printed in the stdout summary;
- explicit unknown provider checkpoint version;
- invocation and schema/boundary-validated-run counts;
- accepted/rejected/blocked counts only for integrity-valid typed runs;
- per-case `AIExtractionRun` artifacts or preflight block reasons;
- deterministic quality checks against the synthetic gold expectations, reported across separate denominators (report version v0.7, per `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md`; bucket membership comes solely from each case's gold expectation, so an unexpectedly blocked substantive case stays in the substantive denominator as a failure): the substantive-extraction rate over cases whose gold expects accepted extraction (the only figure that measures extraction against substantive gold), the expected-abstention rate over cases whose gold expects safe rejection, the invoked-case outcome rate over all observed invocations (never to be described as semantic accuracy), the policy-gate rate over pre-invocation-blocked cases, and the whole-corpus rate;
- bounded rejection diagnostics on rejected runs (`rejection_diagnostics.pre_clear_candidate_counts`): per-array candidate record counts before clearing, with no candidate content and no raw model text;
- observed per-case latency and aggregate throughput for the bounded run;
- integrity failure count;
- explicit qualification flags.

`candidate_only_boundary_exercised` becomes true only after at least one run actually passes JSON Schema plus the semantic candidate boundary; mere invocation is insufficient. `trial_integrity_clean` is reported separately.

The report does **not** claim representative production scale. `representative_batch_scale_qualified` remains `false`.

Cost is recorded as unmeasured/unknown per provider (each report carries its own rationale) because neither exposed edge provides a stable per-invocation monetary-cost field to this harness. No cost claim is inferred.

## Manual execution

Use the GitHub Actions workflow **M4 bounded real-model extraction trial** after configuring `COPILOT_GITHUB_TOKEN`.

The workflow:

1. runs the deterministic harness validator first;
2. verifies the dedicated credential exists;
3. invokes the synthetic corpus through the pinned Copilot CLI;
4. uploads the JSON report as a 30-day workflow artifact;
5. propagates any integrity failure after artifact upload.

A model-quality miss may be recorded as evaluation evidence without becoming a canonical change. Any harness/schema/boundary integrity failure is a workflow failure.

### Local Z.ai execution

The Z.ai edge is driven locally, after the deterministic suite is green and the independent reviews are complete:

1. set the credential outside any tracked file: `export ZAI_API_KEY=...` (PowerShell: `$env:ZAI_API_KEY = "..."`);
2. select the endpoint explicitly — Coding Plan key: `--zai-endpoint coding-plan`; prepaid/resource-package key: `--zai-endpoint prepaid`; the two routes are not interchangeable, and the account type is the operator's responsibility to state. An explicit `ZAI_BASE_URL` / `--base-url` is accepted only as one of the two exact documented routes. Entitlement note: this trial is structured extraction, not a coding scenario; Z.ai documents the Coding Plan endpoint for coding scenarios, so the general OpenAI-compatible route (`--zai-endpoint prepaid`) is the clean choice for the live trial unless Z.ai explicitly permits this workload under the Coding Plan;
3. run from a clean checkout of the independently reviewed tip, e.g. `python scripts/run_m4_model_extraction_trial.py --provider zai --zai-endpoint coding-plan --output <report.json>` (with the usual `--model`, `--max-cases`, and `--timeout-seconds` controls available); the report records the exact git HEAD and tracked-worktree cleanliness, and a `<report>.json.sha256` sidecar pins the final report bytes — live evidence is accepted only with `tracked_worktree_clean: true` at the reviewed tip;
4. review the JSON report and its sidecar before drawing any model-quality or scale conclusion.

No GitHub Actions workflow is provided for the Z.ai edge: CI must never call Z.ai or consume model credits.

## Claim ceiling

This increment can establish only that a real model **can be exercised** through the existing candidate-only extraction boundary on a bounded synthetic corpus once a live workflow report exists and is reviewed.

The first live report now exists and is preserved as reviewed evidence. It establishes only that a Z.ai provider request configured with requested model `glm-5.3` was exercised through the existing candidate-only extraction boundary on the bounded synthetic corpus, with zero integrity failures and pre-invocation blocking intact. The served model checkpoint remains unknown.

It does **not** by itself establish:

- acceptable extraction quality for production use;
- representative batch throughput or extraction “at scale”;
- a production provider/model choice — the Z.ai edge is a trial provider option alongside Copilot, not a production model-platform selection;
- downstream Resolver/Verifier preservation — three accepted live candidates carry participant roles outside the canonical Event vocabulary and would fail that boundary until the candidate contract enforces it;
- served model/checkpoint identity — the artifact traces the requested model only;
- a scheduler or autonomous worker;
- multi-process writer coordination;
- truth, approval, canonical-mutation, or publication authority;
- safe processing of RED/restricted material;
- automatic progression from model output to canonical knowledge;
- end-to-end real-model passage through Resolver/Verifier and human review.

M4 closure still requires revision of the candidate/prompt/evaluator contract from existing SDA ontology and a corpus rerun under the revised contract, explicit quality/performance evaluation, evidence that real-model candidates preserve the downstream Resolver/Verifier and human-review boundaries, representative batch-volume/throughput evidence for any scale claim, bilingual drafting, and evaluation/observability outcomes.
