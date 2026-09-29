# M4 Bounded Real-Model Extraction Trial — Fallback Second Pass

## Why this review exists

The maintainer first-pass was completed and frozen before Codex invocation, and the first Codex review was reconciled in separate records.

A fresh Codex review was then requested on exact head `f28d08a6ffc61f86c3abf3ba7b8158385fd3421e`. Codex did not perform that review because the repository/account had reached its code-review usage limit. The bot returned a quota-limit notice instead of review findings or a clean-review signal.

Under the project review protocol, a Codex quota failure is not approval. The maintainer therefore performed an explicit fallback second review of the current implementation rather than stopping at the first Codex pass.

## Review basis

The fallback review rechecked the current PR surface with emphasis on areas changed during first-Codex reconciliation:

- live prompt semantics and whether the model is given enough structure to produce the SDA candidate contract;
- strict JSON parsing and parser-differential edge cases;
- workflow dispatch / credential isolation;
- candidate-only authority and provenance closure;
- exact Evidence / Entity / Claim / Event quality semantics;
- rejected-output isolation;
- trace integrity and versioning;
- failure reporting and claim ceiling;
- regression coverage and repository-wide compatibility.

The implementation head after fallback remediations and before this review record was added is:

- `a2eefe4100cbeafd28e6e28b2669538f1c8ce73a`.

## Fallback findings

### FR-01 — HIGH — live prompt under-specified the required candidate record contract

**Observed:** the live prompt named the four top-level arrays and several authority/safety rules, but did not tell the real model the actual Evidence, Entity, Claim, and Event field shapes required by the downstream `AIExtractionRun` schema.

**Risk:** a live trial could primarily measure whether the model guessed SDA's internal JSON representation rather than whether it could extract the synthetic source correctly. Structural rejection would therefore be difficult to interpret as model-quality evidence.

**Remediation:** the prompt contract now explicitly describes the bounded record fields and reference conventions for:

- candidate Evidence, including source Document identity, locator, excerpt hash behavior, and capture assessment;
- candidate Entity, including type, localized names, aliases, subtype, and evidence references;
- candidate Claim, including subject, allowlisted predicate, typed value, evidence, extraction assessment, and the rule to omit unsupported validity;
- candidate Event, including type, explicit temporal value, end semantics, participants/roles, related entities, evidence, and extraction assessment.

The prompt also states that a date attached to one Event must not silently become the validity date of a neighboring Claim.

Because this changes the model-facing contract, the adapter version was bumped to `m4-model-trial-v0.2` and the prompt template version to `v0.2` rather than silently changing a v0.1 trace.

**Regression:** `scripts/validate_m4_model_extraction_trial_fallback_review.py` asserts the live prompt contains the bounded record contract, unsupported-temporal-scope rule, case-specific Document/Claim/Event inputs, and the bumped version identifiers.

**Status:** CLOSED.

### FR-02 — MEDIUM — strict JSON still accepted duplicate object keys

**Observed:** Python `json.loads` rejects malformed syntax and was already hardened against non-finite numbers, but by default it accepts duplicate JSON member names and keeps the last value.

**Risk:** duplicate member names create parser-differential ambiguity. The exact raw response hash would be retained, but the typed candidate projection could depend on last-key-wins behavior that another JSON consumer may interpret differently. That is inconsistent with an auditable strict-envelope claim.

**Remediation:** JSON parsing now uses an `object_pairs_hook` that rejects duplicate keys at every object nesting level before any candidate record can enter review.

**Regression:** the fallback validator proves both a duplicate top-level key and a duplicate nested numeric-value key fail `strict-json-envelope` with zero candidate leakage, while a normal deterministic quantity extraction remains accepted.

**Status:** CLOSED.

## Re-review of previously reconciled areas

No new authority expansion was found after the fallback changes:

- the adapter still accepts only synthetic `public_non_operational` trial cases;
- queue work must still be claimed `candidate_extraction` with AI extraction explicitly allowed and canonical mutation authority false;
- restricted work remains blocked before model invocation;
- model output still uses local `CAND-*` identities and cannot resolve itself to canonical SDA identity;
- candidate output still passes strict envelope, case allowlists, existing candidate/reference closure, and downstream JSON Schema before being counted as integrity-valid;
- rejected runs expose empty candidate arrays;
- quality scoring remains report/evaluation semantics only and grants no truth, approval, mutation, or publication authority;
- the Copilot CLI remains a manual trial driver, not a production model-platform adoption;
- no scheduler, autonomous worker, canonical backend credential, second truth store, or distributed writer coordinator was introduced.

The prior Codex remediations remain intact: workflow-dispatch values stay out of Bash source text; non-finite JSON fails closed; insufficient-evidence structured rejection remains distinct from malformed JSON; and quality scoring compares exact bounded Evidence/Entity/Claim/Event semantics and counts.

## Deterministic verification

On implementation head `a2eefe4100cbeafd28e6e28b2669538f1c8ce73a`:

- schema-validation run `36559565090` — **PASS**;
- original model-trial harness validator — **PASS**;
- first-Codex reconciliation validator — **PASS**;
- fallback second-review validator — **PASS**;
- all prior M1–M4 schema/governance regression validators in the same job — **PASS**.

The Wikibase regression on that implementation head was still running when this record was drafted. This review-record commit changes HEAD in any event, so both schema-validation and Wikibase verification must be green again on the final exact head before merge.

## Remaining claim ceiling

The fallback review does not promote live evidence that does not exist. The following remain unverified:

- no live Copilot trial report has yet been produced and reviewed;
- configuration of `COPILOT_GITHUB_TOKEN` is not established by code review;
- actual model extraction quality, latency, and bounded-run throughput remain unknown until execution;
- monetary cost remains unknown/unmeasured by the harness;
- the provider checkpoint/version behind the requested model remains unknown;
- representative batch-volume / extraction "at scale" remains unqualified;
- real-model candidates have not yet been demonstrated through Resolver/Verifier and the human review packet/decision path;
- no production model provider/platform, scheduler/orchestrator, or distributed writer coordinator is selected or qualified;
- no truth, approval, canonical-mutation, or publication authority is added.

## Final gate after this record

Because this review record moves HEAD, merge requires a new exact-head check of:

1. schema-validation, including all three model-trial validator layers;
2. repository-wide Wikibase verification;
3. PR mergeability and unresolved review-thread state;
4. final net-diff review confirming no temporary/staging files or authority drift.

The attempted second Codex review remains documented as quota-blocked; the fallback second pass above fulfills the project rule for that condition rather than misrepresenting the quota response as a clean Codex review.
