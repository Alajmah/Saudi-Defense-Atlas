# M4 Bounded Real-Model Extraction Trial

## Status

Trial harness implemented; live model evidence is not qualified until the manual workflow is executed and its report is reviewed.

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

A future model/provider may replace this edge without changing SDA domain schemas or authority semantics.

## Authentication

The manual workflow expects repository secret `COPILOT_GITHUB_TOKEN` containing a fine-grained personal access token with Copilot Requests permission.

The credential is used only by the Copilot CLI process. The workflow has repository `contents: read` permission and no canonical backend credentials.

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

Trace semantics are exact at the adapter boundary:

- `prompt_trace.template_sha256` hashes the immutable prompt template;
- `input_sha256` hashes the exact rendered prompt string passed to Copilot CLI;
- `raw_output_sha256` hashes the exact stdout string captured from the CLI, including surrounding whitespace;
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
12. accepted and rejected runs retain zero canonical-mutation and publication authority.

## Live trial report

`scripts/run_m4_model_extraction_trial.py` writes one JSON report containing:

- corpus/provider/requested-model/CLI/adapter trace;
- explicit unknown provider checkpoint version;
- invocation and schema/boundary-validated-run counts;
- accepted/rejected/blocked counts only for integrity-valid typed runs;
- per-case `AIExtractionRun` artifacts or preflight block reasons;
- deterministic quality checks against the synthetic gold expectations;
- observed per-case latency and aggregate throughput for the bounded run;
- integrity failure count;
- explicit qualification flags.

`candidate_only_boundary_exercised` becomes true only after at least one run actually passes JSON Schema plus the semantic candidate boundary; mere invocation is insufficient. `trial_integrity_clean` is reported separately.

The report does **not** claim representative production scale. `representative_batch_scale_qualified` remains `false`.

The runner records cost as unmeasured/unknown because the CLI does not provide a stable per-invocation monetary-cost field to this harness. No cost claim is inferred.

## Manual execution

Use the GitHub Actions workflow **M4 bounded real-model extraction trial** after configuring `COPILOT_GITHUB_TOKEN`.

The workflow:

1. runs the deterministic harness validator first;
2. verifies the dedicated credential exists;
3. invokes the synthetic corpus through the pinned Copilot CLI;
4. uploads the JSON report as a 30-day workflow artifact;
5. propagates any integrity failure after artifact upload.

A model-quality miss may be recorded as evaluation evidence without becoming a canonical change. Any harness/schema/boundary integrity failure is a workflow failure.

## Claim ceiling

This increment can establish only that a real model **can be exercised** through the existing candidate-only extraction boundary on a bounded synthetic corpus once a live workflow report exists and is reviewed.

Until that report exists, this PR establishes only the trial harness and deterministic boundary validation.

It does **not** by itself establish:

- acceptable extraction quality for production use;
- representative batch throughput or extraction “at scale”;
- a production provider/model choice;
- a scheduler or autonomous worker;
- multi-process writer coordination;
- truth, approval, canonical-mutation, or publication authority;
- safe processing of RED/restricted material;
- automatic progression from model output to canonical knowledge;
- end-to-end real-model passage through Resolver/Verifier and human review.

M4 closure still requires execution and review of live trial evidence, explicit quality/performance evaluation, evidence that real-model candidates preserve the downstream Resolver/Verifier and human-review boundaries, representative batch-volume/throughput evidence for any scale claim, bilingual drafting, and evaluation/observability outcomes.
