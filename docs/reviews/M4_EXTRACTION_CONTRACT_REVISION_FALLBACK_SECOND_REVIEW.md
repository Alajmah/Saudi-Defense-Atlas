# M4 Extraction Contract Revision — Fallback Second Review

## Protocol status

This record is the repository's documented fallback second review for PR #31 after the requested fresh Codex review could not start because the Codex connector reported code-review quota exhaustion.

The fallback is intentionally labeled as such. It does **not** claim independent Codex review and does not erase the reduced reviewer-independence limitation. The repository already carries deterministic regression coverage from an earlier maintainer fallback second review after Codex quota exhaustion; this record applies that same bounded fallback protocol to the exact current PR #31 head.

Codex quota evidence on PR #31: issue comment `5905124150` states, "You have reached your Codex usage limits for code reviews."

## Frozen review baseline

Second-review implementation head reviewed:

- `ef1ac8f24e8a057207a397a161a7300b13fd853e`

Base / merge base:

- `main` at `3ad0709b9fefe7f673ee445868955815df71b928`

PR state at review start:

- PR #31 open and mergeable;
- all prior inline Codex threads resolved;
- exact-head push `schema-validation` run `36675390248` — success;
- exact-head PR `schema-validation` run `36675393971` — success;
- exact-head PR `wikibase-verification` run `36675394056` — success;
- no live model rerun in this increment;
- corpus/gold unchanged from `main`.

The final implementation cleanup between `699b0045f9cf95b178ea24b9361e15f65eec3f6b` and `ef1ac8f24e8a057207a397a161a7300b13fd853e` changes only `docs/ROADMAP.md` and the `_enforce_candidate_conventions()` docstring; it contains no logic, schema, corpus, gold, or frozen-review-record change.

## Review surface and method

The fallback pass re-read the complete PR #31 change surface rather than reviewing only the final cleanup commit:

- `services/intelligence/model_extraction_trial.py`;
- `schemas/v0.1/ai-extraction-run.schema.json`;
- `scripts/run_m4_model_extraction_trial.py`;
- `scripts/validate_m4_model_extraction_trial.py`;
- `scripts/validate_m4_model_extraction_trial_fallback_review.py`;
- `scripts/validate_m4_model_extraction_trial_zai_provider.py`;
- `docs/M4_AI_EXTRACTION_CONTRACT.md`;
- `docs/M4_MODEL_EXTRACTION_TRIAL.md`;
- `docs/ROADMAP.md`;
- the frozen first-pass record and both additive remediation records;
- PR review-thread state and exact-head workflow evidence.

The review concentrated on correctness, fail-closed behavior, schema/contract consistency, authority preservation, evaluator-metric semantics, diagnostics, provenance, and documentation/version consistency.

## Verification results

### Candidate authority and rejection isolation — PASS

The revision does not move truth, canonical-resolution, canonical-mutation, publication, Resolver/Verifier, or human-review authority into the model boundary. Accepted output remains `candidate_only`; rejected output is cleared before downstream use.

Malformed or convention-violating candidates fail closed:

- non-list or non-object Event participants reject as `event-participants-shape` rather than raising;
- participant roles outside the canonical eleven-role vocabulary reject as `event-role-vocabulary`;
- Evidence locator must equal exactly `{"fragment": "source-text"}`;
- substantive extraction must carry exactly one document-level Evidence record under the bounded trial normalization;
- exact numeric values with non-null bounds reject as `exact-quantity-bounds`;
- allowlist, candidate-boundary, convention, and downstream schema rejection paths preserve empty candidate output.

No new exception path or candidate-leak path was found in the remediated surface.

### Rejection diagnostics lifecycle — PASS

Rejected runs can carry only counts-only `rejection_diagnostics.pre_clear_candidate_counts`; candidate content and raw model output are not added to diagnostics.

The path that motivated LTR-05 is covered: `candidate-boundary` rejections now receive `_candidate_counts(candidates)`. Schema-isolated rejections also derive counts only when a candidate mapping is available. The shared schema explicitly forbids `rejection_diagnostics` on `accepted_for_candidate_review` runs.

### Abstention semantics — PASS

Prompt template `v0.4` resolves the earlier contradiction:

- substantive Entity/Claim/Event output requires exactly one trial Evidence record;
- complete abstention returns all four arrays empty, including Evidence.

The code still checks complete all-array emptiness before convention enforcement, preserving the intended `no-substantive-candidates` path. An evidence-only envelope is safely rejected later and remains diagnosable by counts.

### Canonical role vocabulary parity — PASS

The candidate Event schema and trial constant use the canonical eleven-role vocabulary, and deterministic validation asserts equality with both the canonical Event schema enum and Resolver/Verifier `_EVENT_ROLES`. The revision therefore closes the first live run's unsupported-role downstream incompatibility at the candidate boundary.

### Metrics split — PASS

Report version `m4-model-extraction-live-trial-v0.6` preserves the whole-corpus quality metric while separately reporting:

- invoked-case count and invoked-model pass count/rate;
- non-invoked policy/preflight-gate count and pass count/rate.

Execution failures that occur after invocation remain classified as invoked results and therefore cannot be hidden in the policy-gate denominator. No new model-quality claim is made by this change.

### Contract and documentation consistency — PASS

The final reviewed surface consistently distinguishes:

- canonical Event-role vocabulary;
- bounded-trial exact-bounds and single-document Evidence normalizations;
- prompt/evaluator-only equipment-vs-`equipment_variant` typing and permissions-not-obligations guidance.

Versions are consistent at the reviewed head:

- prompt template: `v0.4`;
- adapter: `m4-model-trial-v0.3`;
- report: `m4-model-extraction-live-trial-v0.6`;
- corpus/gold: unchanged.

The final ROADMAP sequence correctly treats PR #30 as already merged and identifies PR #31 as the current merge gate.

## Findings register

**No new blocking or non-blocking findings were identified on `ef1ac8f24e8a057207a397a161a7300b13fd853e`.**

All previously accepted PR #31 findings are represented by the frozen first-pass/remediation chain and have deterministic regression coverage or documentation correction on the reviewed head.

## Explicit limitation of this fallback

This pass is a maintainer fallback necessitated by Codex code-review quota exhaustion. It is not independent in reviewer identity to the same degree as the requested Codex pass. That limitation is accepted only because:

1. the independent first-pass baseline was frozen before second-review reconciliation;
2. two prior Codex reviews on the original frozen head supplied external findings that were independently verified and remediated;
3. all Codex inline findings are resolved with explicit remediation SHAs;
4. the remaining post-remediation changes are narrowly scoped and were re-read against the complete PR surface;
5. deterministic regressions are retained in CI; and
6. exact-head workflow evidence is green.

If Codex review capacity later becomes available, a post-merge audit may still be useful, but it is not represented here as having occurred.

## Qualification ceiling remains unchanged

This fallback review does **not** qualify:

- extraction quality of any live model;
- served-model/checkpoint identity;
- representative scale or throughput;
- cost qualification;
- production provider/platform selection;
- production scheduling/orchestration;
- autonomous canonical mutation or publication.

Equipment-vs-variant typing and permissions-not-obligations remain prompt/evaluator guidance rather than mechanically enforced candidate-boundary rules.

The next live Z.ai run remains blocked until after this PR merges and a fresh run-specific operator entitlement attestation is recorded.

## Decision

Fallback second review result for implementation head `ef1ac8f24e8a057207a397a161a7300b13fd853e`: **PASS — no remaining review finding identified.**

This record is documentation-only and introduces no implementation or qualification expansion. PR #31 may proceed to merge only after the commit containing this record receives successful exact-head CI and the PR head has not moved unexpectedly.