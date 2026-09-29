# M4 Extraction Contract Revision — Remediation Record

## Protocol

This record remediates the seven findings of the independent review of PR #31 (maintainer-side register plus Codex auto-review, discovery independence preserved) against frozen head `707afa185d2a716122a12fd4f41d824fd31e85a2`. The frozen maintainer first-pass record (`docs/reviews/M4_EXTRACTION_CONTRACT_REVISION_FIRST_PASS.md`) is preserved unchanged; corrections are additive here.

No live corpus rerun has been performed. Gold and the corpus fixture remain byte-identical to `main`.

## Finding-by-finding remediation

### CRX-01 — P1 — malformed Event participants could abort the whole trial — REMEDIATED

The convention loop iterated `participants` before structural validation, so a truthy non-list value (for example `participants: 1`) raised `TypeError` inside `build_extraction_run_from_model_output` and could terminate the entire corpus run instead of producing a rejected case. The boundary now structurally validates the field first: a non-list `participants`, or any non-object entry, is rejected with the dedicated `event-participants-shape` check id, empty candidates, and pre-clear count diagnostics. Regression coverage: scalar `1`, string `"manufacturer"`, and `["manufacturer"]` (non-object entry) each produce a schema-valid rejected run and never raise.

### CRX-02 — HIGH — candidate-boundary rejections lacked diagnostics — REMEDIATED

The `validate_ai_extraction_run()` exception path called `_rejected_run()` without `rejection_diagnostics`, leaving the exact path that motivated LTR-05 (the first live run's `TRIAL-INSUFFICIENT` `candidate-boundary` rejection with pre-clear content) opaque. The path now records `_candidate_counts(candidates)`. Regression coverage: the canonical-identity rejection (a deterministic `candidate-boundary` failure) is asserted to carry `pre_clear_candidate_counts` of `{"evidence": 1, "entities": 3, "claims": 1, "events": 1}`.

### CRX-03 — MEDIUM — locator enforcement ignored additional keys — REMEDIATED

The canonical Evidence locator permits `page`, `section`, `paragraph`, offsets, and `selector`, and the trial normalization demands the exact token object. The check previously tested only the fragment value, so `{"fragment": "source-text", "page": 1}` passed. The locator must now equal `{"fragment": "source-text"}` exactly (no additional keys); non-object locators are rejected by the same check. Regression coverage: the extended-locator mutation is rejected under `evidence-locator`.

### CRX-04 — MEDIUM — `rejection_diagnostics` underconstrained in the shared schema — REMEDIATED

The shared `ai-extraction-run.schema.json` now forbids `rejection_diagnostics` on accepted runs via an `if/then` conditional on `validation.status`; the field remains optional on rejected runs, where no valid candidate envelope may exist (strict-JSON rejections carry no counts). Regression coverage: an accepted run with the field injected is asserted schema-invalid, and every existing rejected-run assertion already proves schema-validity with the field present.

### CRX-05 — MEDIUM — stale normative contract wording — REMEDIATED

`docs/M4_AI_EXTRACTION_CONTRACT.md` said rejected runs contain "validation errors only." It now records validation errors plus the counts-only `rejection_diagnostics.pre_clear_candidate_counts`, with the accepted-run prohibition stated.

### CRX-06 — MEDIUM — evidence-cardinality framing corrected — REMEDIATED

Exactly-one Evidence record per extraction is a **bounded-trial normalization** for this single-document synthetic corpus, not a canonical ontology invariant: the ontology defines Evidence as a bounded piece of a Document, permits one-or-more evidence links, and the canonical Evidence schema does not impose one record per Document. The trial document now states this distinction explicitly. The maintainer first-pass record's framing ("derived from … the corpus's pre-existing single-document Evidence expectation") is superseded by this correction; the implementation itself is unchanged because the trial normalization is defensible on its own terms.

Wording refinement applied alongside: the exact-quantity null-bounds rule is documented as a trial normalization consistent with the ontology's precision-or-bounds concept. The canonical `number_value` schema defines nullable `lower_bound`/`upper_bound` and does not itself encode `precision == exact ⇒ bounds == null`; the documentation no longer implies otherwise.

### CRX-07 — LOW — role-vocabulary parity guard — REMEDIATED

The eleven-role vocabulary now exists in four normative copies (canonical Event schema enum, Resolver/Verifier `_EVENT_ROLES`, candidate schema enum, trial `CANONICAL_EVENT_ROLES`). The harness validator asserts all four are identical sets, so any future drift fails CI instead of recreating a downstream incompatibility.

## Deterministic validation evidence

- Complete repository suite at the remediation implementation commit: all 38 `scripts/validate_*.py` validators — **PASS**, including the new regressions for participant shape (three malformed shapes), extended locator, candidate-boundary diagnostics, accepted-run schema prohibition, and the four-way role parity assertion.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` on the same tip.

## Explicitly unverified / unresolved

- Everything recorded in the frozen first-pass record remains open: the corpus has not been rerun against a live model under the revised contract; whether GLM-5.3 follows the tightened prompt is unknown until that rerun; entity typing and permissions-not-obligations remain prompt-instructed rather than mechanically enforced; served-model identity, scale, cost, and production-provider selection remain unqualified.
- The next Z.ai live run additionally requires a fresh run-specific operator entitlement attestation per the second-review reconciliation.

## Freeze

This record completes the remediation of the seven PR #31 findings. The remediated head plus this record await a fresh Codex review of the new exact SHA before PR #31 may merge.
