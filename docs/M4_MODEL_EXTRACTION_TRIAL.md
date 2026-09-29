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
- default model: `gpt-5.4` (overrideable at workflow dispatch);
- automatic CLI updates: disabled for the run.

A future model/provider may replace this edge without changing SDA domain schemas or authority semantics.

## Authentication

The manual workflow expects repository secret `COPILOT_GITHUB_TOKEN` containing a fine-grained personal access token with Copilot Requests permission.

The credential is used only by the Copilot CLI process. The workflow has repository `contents: read` permission and no canonical backend credentials.

## Model isolation

The programmatic Copilot invocation uses:

- non-interactive prompt mode;
- silent output capture;
- `--no-ask-user`;
- `--no-custom-instructions`;
- `--disable-builtin-mcps`;
- explicit denial of `read`, `write`, `shell`, `url`, and `memory` tools;
- an explicit model identifier.

The model therefore receives only the trial prompt text supplied by the runner. It is not authorized to inspect the repository, call the network, mutate files, invoke GitHub tools, or take canonical actions.

## Prompt contract

The prompt treats source text as untrusted data and explicitly instructs the model to ignore instructions embedded inside the source. It requires one strict JSON object with exactly:

- `evidence`;
- `entities`;
- `claims`;
- `events`.

The prompt also supplies a case-specific allowlist for Claim predicates and Event types. Output outside those allowlists is rejected before candidate review.

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
3. strict JSON envelope is required;
4. case predicate/Event allowlists are enforced;
5. out-of-scope Document provenance is rejected;
6. model-produced canonical entity references are rejected;
7. existing `AIExtractionRun` candidate/reference closure remains authoritative;
8. downstream JSON-Schema failure is isolated into a rejected run with zero candidate leakage;
9. accepted and rejected runs retain zero canonical-mutation and publication authority.

## Live trial report

`scripts/run_m4_model_extraction_trial.py` writes one JSON report containing:

- corpus/provider/model/CLI/adapter trace;
- accepted/rejected/blocked counts;
- per-case `AIExtractionRun` artifacts or preflight block reasons;
- deterministic quality checks against the synthetic gold expectations;
- observed per-case latency and aggregate throughput for the bounded run;
- integrity failure count;
- explicit qualification flags.

The report does **not** claim representative production scale. `representative_batch_scale_qualified` remains `false`.

The runner also records cost as unmeasured/unknown because the CLI does not provide a stable per-invocation monetary-cost field to this harness. No cost claim is inferred.

Raw model output is not persisted in the report; the `AIExtractionRun` retains its SHA-256 hash as required by the existing contract.

## Manual execution

Use the GitHub Actions workflow **M4 bounded real-model extraction trial** after configuring `COPILOT_GITHUB_TOKEN`.

The workflow:

1. runs the deterministic harness validator first;
2. verifies the dedicated credential exists;
3. invokes the synthetic corpus through Copilot CLI;
4. uploads the JSON report as a 30-day workflow artifact;
5. propagates any integrity failure after artifact upload.

A model-quality miss may be recorded as evaluation evidence without becoming a canonical change. Any integrity failure is a workflow failure.

## Claim ceiling

This increment can establish only that a real model can be exercised through the existing candidate-only extraction boundary on a bounded synthetic corpus.

It does **not** by itself establish:

- acceptable extraction quality for production use;
- representative batch throughput or extraction “at scale”;
- a production provider/model choice;
- a scheduler or autonomous worker;
- multi-process writer coordination;
- truth, approval, canonical-mutation, or publication authority;
- safe processing of RED/restricted material;
- automatic progression from model output to canonical knowledge.

M4 closure still requires review of live trial evidence, explicit quality/performance evaluation, representative batch-volume/throughput evidence for any scale claim, bilingual drafting, and evaluation/observability outcomes.
