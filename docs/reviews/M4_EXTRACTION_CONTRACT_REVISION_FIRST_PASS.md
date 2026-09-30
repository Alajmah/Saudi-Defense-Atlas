# M4 Extraction Contract Revision — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the candidate/prompt/evaluator contract revision, performed before any independent second review of this increment. It follows the repository rule that first-pass defect finding belongs here; the independent reviewer and any second reviewer come after this baseline is frozen.

## Baseline and review surface

Base branch / merge base:

- `main` at `3ad0709b9fefe7f673ee445868955815df71b928` (squash merge of PR #30), verified via `git rev-parse main` after fast-forward pull.

Implementation baseline reviewed before this review record was added:

- `m4/extraction-contract-revision` at the implementation commit recorded with this branch's push (the commit preceding this record).

Net surface:

1. `docs/M4_MODEL_EXTRACTION_TRIAL.md`
2. `docs/ROADMAP.md`
3. `schemas/v0.1/ai-extraction-run.schema.json`
4. `scripts/run_m4_model_extraction_trial.py`
5. `scripts/validate_m4_model_extraction_trial.py`
6. `scripts/validate_m4_model_extraction_trial_fallback_review.py`
7. `scripts/validate_m4_model_extraction_trial_zai_provider.py`
8. `services/intelligence/model_extraction_trial.py`

Not changed: the evaluation corpus (`tests/fixtures/m4-model-extraction-eval.json` is byte-identical to `main`; its version stays `m4-model-extraction-eval-v0.3` because gold expectations are unchanged), the Resolver/Verifier, the extraction boundary's authority semantics, the evidence artifacts, and every validator outside the model-trial family.

## Intent and authority boundary

The forcing function is the frozen live-trial review chain: LTR-01/LTR-02/LTR-03/LTR-05 and C2R-02 require the candidate contract to expose and enforce conventions that already exist in SDA's canonical contracts, separate model quality from policy-gate quality, and add bounded rejection diagnostics — without fitting gold to the observed GLM output.

The increment does this and nothing more:

- every added convention is derived from an existing canonical source (the Event schema's eleven-role enum, identical to the Resolver's `_EVENT_ROLES`; the canonical `number_value` shape where bounds are optional interval annotations; the ontology's EquipmentVariant definition; the corpus's pre-existing single-document Evidence expectation), none from the first live run's outputs;
- enforcement happens at the candidate boundary as rejected runs with dedicated check ids, preserving candidate-only authority and rejection isolation;
- the report gains metrics and diagnostics only; no truth, mutation, publication, Resolver/Verifier, or human-review authority moved.

## Conventions delivered

1. **Event-role vocabulary (C2R-02, LTR-02 refinement).** The candidate Event schema now enumerates the eleven canonical roles; the prompt supplies them as `ALLOWED_EVENT_ROLES`; the boundary rejects any other role (`event-role-vocabulary`). Unsupported roles now fail at the candidate boundary instead of the downstream Resolver/Verifier.
2. **Exact-quantity bounds (LTR-02).** An exact numeric quantity sets `value` with null bounds; mirroring an exact value into the bounds is rejected (`exact-quantity-bounds`). Derived from the canonical `number_value` shape, where `value` is the quantity and bounds are optional interval annotations.
3. **Entity typing (LTR-02).** The prompt states the ontology-derived rule: a specific named model or variant of a family is `equipment_variant`; the family or design itself is `equipment`.
4. **Evidence cardinality and locator (LTR-02, LTR-03).** Exactly one document-level Evidence record, with the literal locator token `{"fragment": "source-text"}`; violations are rejected (`evidence-cardinality`, `evidence-locator`) and the prompt shows the mechanical literal.
5. **Permissions, not obligations (LTR-04).** The prompt now states that allowlisted predicates and event types are permissions, and that an unrepresentable proposition must be omitted rather than re-subjectified.

## Metrics and diagnostics

- Report v0.6 separates `invoked_quality_case_pass_count/rate` (invoked cases only) from `policy_gate_case_pass_count/rate` (pre-invocation-blocked cases only), alongside the retained whole-corpus metric (LTR-01). The whole-corpus figure remains labeled as such and must never be described as the model's extraction-quality rate.
- Rejected runs carry `rejection_diagnostics.pre_clear_candidate_counts`: per-array record counts captured before candidates are cleared (LTR-05). No candidate content and no raw model text is persisted. A structured abstention shows all-zero counts; the first live run's opaque `TRIAL-INSUFFICIENT` rejection would now be diagnosable from counts alone.

## Ordering decision worth recording

Convention checks run only when the model returned substantive candidates. A fully abstaining envelope still reaches `no-substantive-candidates`, so the expected rejection path for `TRIAL-INSUFFICIENT` is unchanged and gold remains satisfied. The alternative ordering (cardinality before substance) would have mislabeled correct abstention as a convention violation.

## Findings during implementation

1. **Prompt-template brace escaping.** The literal `{"fragment": "source-text"}` inside the template initially broke `str.format` rendering (`KeyError: '"fragment"'`), caught immediately by every deterministic validator; the literal is now escaped as `{{...}}` and renders as intended.
2. **Version pins worked as designed.** The fallback-review validator rejected the change until the adapter/prompt versions were bumped to v0.3, and the Z.ai validator rejected report v0.5 — both guards did exactly what they exist to do.

## Deterministic validation evidence

- Complete repository suite at the implementation head: all 38 `scripts/validate_*.py` validators — PASS, including: the harness validator's four new convention-rejection regressions (each with check id, empty candidates, schema-valid rejection, and count diagnostics), the accepted-run no-diagnostics assertion, the all-zero abstention diagnostics assertion, and the conforming exact-quantity acceptance; the fallback validator's v0.3 version pins and new prompt-fragment checks; the Z.ai validator's split-metric assertions (invoked 5/5, policy gate 1/1 on the deterministic corpus).
- The pre-existing deterministic fake corpus required zero changes — it already conformed to every new convention, which is itself evidence the conventions were derived from SDA contracts rather than from model output.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` on the same tip.

## Explicitly unverified / unresolved

- The synthetic corpus has not been rerun against a live model under the revised contract; all quality statements remain those of the reviewed 2026-09-29 evidence until that rerun exists and is reviewed.
- Whether GLM-5.3 follows the tightened prompt (roles, bounds, cardinality, abstention) is unknown until the rerun; failures now fail closed at the boundary with diagnosable counts.
- Entity typing and permissions-not-obligations are prompt-instructed but not mechanically enforced at the boundary (typing would require ontology-external heuristics; the LTR-04 pattern is observable in output claims). The corpus rerun will show whether stricter enforcement is needed.
- Served model/checkpoint identity, scale, cost, and production-provider selection remain open exactly as recorded in the second-review reconciliation.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review before any corpus rerun with a live model.
