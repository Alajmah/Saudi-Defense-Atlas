# M4 Semantics Adjudication — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the semantics-adjudication increment, performed before any independent second review. It is offline and contract-first: no live model call, no use of R1–R5 outputs as normative evidence, no mutation of the preserved PR #38 evidence.

## Baseline and review surface

Base branch / merge base:

- `main` at `158b79b2ae25eb5b4a23897799ab7ac77fd62d98` (squash merge of PR #38), verified via `git rev-parse main`.

Implementation baseline reviewed before this review record was added:

- `m4/semantics-adjudication` at the implementation commit recorded with this branch's push (the commit preceding this record).

Net surface:

1. `docs/M4_DOWNSTREAM_PRESERVATION_REPLAY.md` (provenance-gate description)
2. `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md` (entity-set rule section; REP-01 adjudication note)
3. `docs/M4_MODEL_EXTRACTION_TRIAL.md` (entity-set bullet; prompt v0.8 reference)
4. `docs/ROADMAP.md`
5. `docs/reviews/M4_SEMANTICS_ADJUDICATION.md` (new — the decision record with migration note)
6. `docs/evidence/m4/2026-09-30/corpus/` (new — frozen generation-time corpus copy plus sidecar; evidence addition, not a mutation of any preserved artifact)
7. `scripts/validate_m4_downstream_replay.py` (reads the frozen corpus copy; its sidecar is gated)
8. `scripts/validate_m4_model_extraction_trial.py` (fake-output typing; prompt fragments)
9. `scripts/validate_m4_model_extraction_trial_fallback_review.py` (pin v0.8; fragments)
10. `scripts/validate_m4_model_extraction_trial_reconciliation.py` (extra-entity evaluator regression)
11. `services/intelligence/model_extraction_trial.py` (prompt rule 19; template v0.8)
12. `tests/fixtures/m4-model-extraction-eval.json` (corpus v0.4: version string + the single adjudicated gold change)

Not changed: any preserved report, sidecar, manifest, or analysis from PR #38 (verified by blob digests below); the boundary's enforcement logic and adapter version; the evaluator; the resolver.

## Decision summaries under review

### REP-01 — Alpha-system typing

Adjudication input: the corpus source itself («…لتوريد منظومة التدريب ألفا», signed a contract to supply the Alpha training system) and the already-merged designation rule. The phrase carries the specific designation "ألفا" in explicit supply context, making it a named discrete deliverable — `equipment_variant`. The gold was updated deliberately with a corpus version bump to v0.4. A structural diff against HEAD confirms the fixture changed in exactly two places: the version string and that one entity_type. No prompt text was needed for this decision and prompt v0.7's rule 13 was left alone until REP-02's rule 19 bumped the template to v0.8.

The R1–R5 outputs were not used as evidence for the adjudication: the reading follows from the source phrase and the merged rule, both of which predate R1. The outputs motivated asking the question; the source answers it.

### REP-02 — claim/event-driven entity set

The rule (entities only when they fill a role in an emitted Claim or Event) is grounded in the ontology (entities as bearers of relationships) and the downstream architecture (the resolver materializes evidence/claim/event mutations and never a standalone entity mutation — verified in `_resolver_verifier_core`'s mutation assembly). Quantity gold already conforms and was not changed; the rule states the basis the evaluator had been enforcing without writing down. Evaluated, not enforced, with the disproportion rationale recorded (an extra source-grounded entity is a scoring miss, not an integrity violation).

## Evidence integrity during a gold change

The one structural risk in editing the corpus was the v0.7 replay's generation-time provenance gate. Resolution: the generation-time corpus bytes are frozen under `docs/evidence/m4/2026-09-30/corpus/` (LF blob digest `fe9217ab…`, own sidecar, gated in the validator), and the replay now reads that copy. The frozen copy's both-representation digests include the recorded `corpus_sha256`, so the gate holds exactly as before; the live fixture evolves independently. The preserved PR #38 evidence blobs were re-verified unchanged after all edits: R1 `75cd9c5f…` through R5 `4839bd50…`, manifest `408f48bb…`, plus the v0.6/v0.7 reports.

## Regressions proving the new semantics

- The reconciliation validator now proves the exact scorer fails an extraction carrying an unused extra entity — the REP-02 penalty grounded in the stated rule.
- The harness validator's deterministic fake corpus types the Alpha system `equipment_variant`, so the entire deterministic chain (harness, zai provider validator's main-level fake run, reconciliation) now scores against the adjudicated gold end to end.
- Prompt-fragment checks pin rule 19's wording, and the fallback version-pin validator forced the v0.7 → v0.8 template bump, as designed.
- The replay validator proves the frozen-corpus rebinding end to end: report digest constant, sidecar equality, frozen-copy sidecar equality, and the recorded corpus binding all gate before any replay.

## Version discipline

Corpus v0.3 → v0.4 (one gold change + version string). Prompt v0.7 → v0.8 (rule 19 only). Adapter unchanged (`m4-model-trial-v0.3`): no boundary-logic change. Evaluator unchanged: no scoring-logic change (the reconciliation regression pins existing behavior). Report version unchanged (v0.7). The migration note in the decision record states exactly which historical scores become non-comparable (all `TRIAL-AR-CONTRACT` exact-gold results across every preserved live artifact, hence all aggregate rates across the fixture boundary; plus prompt-boundary non-comparability for R1–R5 versus any v0.8 series) and includes the counterfactual R1–R5 substantive projection (3/4, 3/4, 2/4, 2/4, 1/4) explicitly labeled as projection, not measurement.

## Deterministic validation evidence

- Complete repository suite at the implementation head: all 39 validators — **PASS**, including the extended reconciliation and replay validators.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- No live run has occurred under corpus v0.4 / prompt v0.8; every future-run claim waits for such a run under the standing entitlement and its review.
- The migration note's projection is arithmetic on preserved outputs, not a re-scored report; no historical artifact was modified to produce it.
- REP-03 needs no action here; the delivery-role variability stands as evidence under an explicit rule.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review.
