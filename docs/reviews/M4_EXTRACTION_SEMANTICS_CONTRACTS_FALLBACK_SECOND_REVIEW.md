# M4 Extraction Semantics Contracts — Fallback Second Review

## Protocol status

This record is the repository's documented fallback second review for PR #33 after Codex code-review quota exhaustion prevented an independent Codex review. The fallback is intentionally labeled as such and does **not** claim equivalent reviewer independence.

Codex quota evidence on PR #33: issue comment `5909409935` states that the code-review usage limit has been reached.

Fresh fallback review submission on the remediated implementation head: review `5366500873`.

## Frozen review baseline

Reviewed implementation head:

- `133765626108be2f2c567ee59ab34986d19dd826`

Base / merge base:

- `main` at `1493d5ffd2c087c2b2c008a532ecd317bfb338e8`

PR state at review time:

- PR #33 open and mergeable;
- no live model call in this contract-semantics increment;
- corpus/gold unchanged from `main`;
- prompt template `v0.6`;
- adapter `m4-model-trial-v0.3`;
- report definition `m4-model-extraction-live-trial-v0.7`;
- exact-head push `schema-validation` run `36711877077` — success;
- exact-head PR `schema-validation` run `36711881295` — success;
- exact-head PR `wikibase-verification` run `36711881302` — success.

The uploaded second-remediation record is byte-identical to the committed record: Git blob `47fc62db4c90060fa7e93c89e7198be3f264f871`, size 4,487 bytes.

## Review surface and method

The fallback pass re-read the complete PR #33 surface and the two-commit remediation delta from `ee018a179a17628fe50185b5ff28f0abcd503023` to `133765626108be2f2c567ee59ab34986d19dd826`, including:

- `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md`;
- `docs/M4_MODEL_EXTRACTION_TRIAL.md`;
- `docs/ROADMAP.md`;
- `services/intelligence/model_extraction_trial.py`;
- `scripts/run_m4_model_extraction_trial.py`;
- `scripts/validate_m4_model_extraction_trial.py`;
- `scripts/validate_m4_model_extraction_trial_fallback_review.py`;
- `scripts/validate_m4_model_extraction_trial_zai_provider.py`;
- the frozen first-pass record and both additive remediation records;
- PR metadata and exact-head workflow evidence.

The review concentrated on metric integrity, fail-closed preflight behavior, prompt/evaluator consistency, authority preservation, annotation-contract provenance, version consistency, and status-document accuracy.

## Verification results

### Metric-contract preflight — PASS

`load_cases()` now calls `validate_metric_contract(cases)` before provider setup or any invocation. The preflight requires:

- non-empty string case IDs;
- unique case IDs;
- object-valued `gold`;
- `gold.expected_status` equal to exactly one of `accepted_for_candidate_review`, `rejected`, or `blocked_before_invocation`.

Malformed metric inputs therefore fail before model-credit consumption and before denominator construction. Deterministic regression coverage includes blank/non-string IDs, duplicate IDs, non-object gold, missing status, unknown status, and a malformed fixture exercised through `load_cases()` itself.

### Gold-defined quality buckets — PASS

Substantive, expected-abstention, and policy-gate membership is derived solely from gold expectation. An unexpectedly blocked substantive case remains in the substantive denominator as a failure rather than moving into the policy bucket.

The symmetric failure path is also covered: an unexpectedly invoked policy-gate case remains in the policy denominator and fails it; it does not enter substantive or abstention buckets.

### Observed-invocation quality metric — PASS

`invoked_quality_case_pass_count` is now computed directly over all observed invoked results. An unexpectedly invoked policy-gate case therefore contributes a failure to the invoked outcome rate as well as to the gold-defined policy-gate denominator.

The metric remains an observed-invocation outcome measure and is explicitly not semantic extraction accuracy. `substantive_quality_case_pass_rate` remains the only first-class report metric defined as extraction performance against substantive gold.

### Role/unit annotation semantics — PASS at the stated claim ceiling

The role and unit rules are explicitly bounded-trial annotation conventions, not claimed canonical ontology implications:

- role vocabulary remains canonical and mechanically enforced;
- role selection within that vocabulary is evaluated against the pre-existing trial annotation convention;
- numeric unit normalization is limited to lexical head-noun normalization of a counted-class phrase explicitly present in the source;
- designation-only counts retain the source designation;
- semantic class-to-unit mapping remains undefined.

No gold change is included in PR #33, and the corpus fixture remains unchanged from `main`.

### Prompt/report/version consistency — PASS

The reviewed surface is internally consistent at:

- prompt template `v0.6`;
- adapter `m4-model-trial-v0.3`;
- report definition `v0.7`;
- corpus/gold unchanged.

The adapter version correctly remains unchanged because candidate-boundary mechanics are not expanded by the semantics conventions. The report version is corrected in place within this unmerged increment; no merged live artifact previously carried v0.7.

### Authority and qualification boundary — PASS

PR #33 changes evaluation semantics and prompt guidance only. It does not grant truth, canonical-resolution, canonical-mutation, publication, Resolver/Verifier, or human-review authority to model output. No production provider/platform adoption, scheduling/orchestration, scale, cost, served-checkpoint, or model-quality qualification is introduced.

### Documentation and PR metadata — PASS

The ROADMAP and trial document reflect the merged v0.6 rerun evidence, distinguish the future v0.7 semantics rerun, and correctly leave downstream Resolver/Verifier/human-review preservation unqualified because the complete downstream path has not yet been executed on live candidates.

The PR description now accurately describes bounded-trial conventions, prompt v0.6 / adapter v0.3 / report v0.7, the FSR/FSR2 remediation chain, and validation at implementation head `133765626108be2f2c567ee59ab34986d19dd826`.

## Findings register

**No new blocking or non-blocking finding was identified on implementation head `133765626108be2f2c567ee59ab34986d19dd826`.**

FSR-01 through FSR-04 and FSR2-01 through FSR2-03 are remediated on that head. Their regression or documentation corrections remain present in the reviewed surface.

## Explicit limitation of this fallback

This review is a maintainer fallback necessitated by Codex code-review quota exhaustion. Reviewer independence is therefore lower than the requested Codex second-review path. The limitation is accepted here because:

1. the maintainer first-pass baseline was frozen before fallback reconciliation;
2. each discovered finding was recorded before remediation;
3. both remediation rounds are additive and preserve earlier review records;
4. the final remediation is narrowly scoped and has explicit adversarial regressions;
5. exact-head workflow evidence is green; and
6. no live model call or authority expansion occurs in this increment.

If independent review capacity later becomes available, a post-merge audit can still be useful; this record does not represent one as having occurred.

## Qualification ceiling remains unchanged

This fallback review does **not** qualify:

- live-model extraction quality;
- served-model/checkpoint identity;
- representative scale or throughput;
- cost;
- production provider/model selection;
- production scheduling/orchestration;
- downstream Resolver/Verifier or human-review preservation for live candidates;
- autonomous canonical mutation or publication.

Any subsequent live rerun remains blocked until PR #33 merges and a fresh run-specific operator entitlement attestation is recorded.

## Decision

Fallback second review result for implementation head `133765626108be2f2c567ee59ab34986d19dd826`: **PASS — no remaining review finding identified.**

This record is documentation-only. PR #33 may proceed to merge only after the commit containing this record receives successful exact-head CI and the PR head has not moved unexpectedly.
