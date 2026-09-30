# M4 Benchmark Annotation Policy — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the benchmark annotation-policy increment (the benchmark-semantics follow-on the v0.7 evidence review sequenced), performed before any independent second review.

## Baseline and review surface

Base branch / merge base:

- `main` at `e37b9e47fa8770603a43e60bb190a17a403177c4` (squash merge of PR #35), verified via `git rev-parse main`.

Implementation baseline reviewed before this review record was added:

- `m4/benchmark-annotation-policy` at the implementation commit recorded with this branch's push (the commit preceding this record).

Net surface:

1. `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md` (typing-convention section, conducted fallback, provenance updates)
2. `docs/M4_MODEL_EXTRACTION_TRIAL.md`
3. `docs/ROADMAP.md`
4. `scripts/validate_m4_model_extraction_trial.py` (fragment checks)
5. `scripts/validate_m4_model_extraction_trial_fallback_review.py` (pin and fragments)
6. `services/intelligence/model_extraction_trial.py` (prompt rules 13 and 17, version bump)

Not changed: the corpus fixture and gold (byte-identical), the preserved v0.7 evidence, the candidate/canonical schemas, the Resolver/Verifier, the boundary's enforcement logic, and all frozen review records.

## What this increment resolves

### RRV7-01 — Falcon-X typing ambiguity

The v0.7 review found the `equipment`/`equipment_variant` gold expectation under-grounded: the source calls Falcon-X an aircraft without saying "model" or "variant", while the prompt both required the distinction and forbade inferring unstated facts.

The new **designation rule** in the semantics contract: a named discrete equipment product — a specific designation the source uses for a countable, deliverable, or operable item — is annotated `equipment_variant`, whether or not the source uses the word "variant"; generic class or family references are `equipment`. The rule-1 tension is resolved by the **classification-not-inference** distinction: typing places the named thing in SDA's ontology without asserting anything the source did not state. Provenance: canonical data distinguishes named discrete products as variants by designation, never by the literal word — F-15SA carries `variant_of` the F-15 family; PAC-3 MSE's designation itself names a segment enhancement. Gold expected `equipment_variant` before any live run; the convention justifies that expectation independently.

### RRV7-02 — conducted-role fallback

The registry supplies the strongest grounding available here: `exercise.participant.organization` is the **only** canonical relation for exercise involvement. The convention therefore annotates an organization that conducts or leads an exercise or training event as `participant`; `host` is reserved for a source-stated hosting or venue relation, which "conducted" does not state. No conductor role is invented. This is a direct registry consequence — the strongest-grounded convention in the contract — and it aligns with the pre-existing gold (`participant`).

## Deliberate non-choices

- Gold and the preserved v0.7 evidence are untouched: both conventions were fixed against canonical precedent and pre-existing gold, not against the v0.7 outputs (`equipment`, `host`).
- Both conventions are **evaluated, not enforced**: typing would require an ontology-external designation classifier; role choice is semantic. Mechanical enforcement remains out of scope.
- Prompt bumped v0.6 → v0.7 (rules 13 and 17 carry the clarified conventions); adapter stays `m4-model-trial-v0.3`; report version unchanged (no metric-surface change).

## Findings during implementation

1. A helper script failed on a typo (`encode=` for `encode()`) before applying the contract edit; nothing was written in that attempt and the edit was applied cleanly afterward. Caught immediately, never committed.
2. The fallback validator's version pin refused prompt v0.7 until bumped, and one stale fragment from the earlier typing wording had to be replaced — both guards working as designed.

## Deterministic validation evidence

- Complete repository suite at the implementation head: all 38 `scripts/validate_*.py` validators — **PASS**, including the new prompt-fragment checks for both conventions and the v0.7 template pin.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` and `wikibase-verification` on the same tip.

## Explicitly unverified / unresolved

- Whether GLM-5.3 follows the clarified rules is unknown until a future reviewed live run; per the agreed sequence, fixed-configuration repeated trials become eligible only after this increment merges and passes review.
- The delivery-role miss (`seller` vs `manufacturer`) needs no convention work — it is already a clean bounded-contract miss under the existing rule — but its remediation is likewise observational until a rerun.
- The downstream-preservation replay (the other agreed no-live-call increment) is untouched by this PR and remains separate.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review.
