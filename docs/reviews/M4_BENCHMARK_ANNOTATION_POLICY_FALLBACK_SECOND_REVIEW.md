# M4 Benchmark Annotation Policy — Fallback Second Review

## Protocol status

This record is the documented fallback second review for PR #36 after the Codex connector reported code-review quota exhaustion on the PR (`5915980280`: "You have reached your Codex usage limits for code reviews.").

This fallback is intentionally labeled. It does **not** claim Codex reviewer independence and does not erase the reduced reviewer-independence limitation. The review below was performed against the frozen PR head and surrounding repository contracts before reconciling with the maintainer first-pass record.

## Frozen review baseline

Reviewed PR head:

- `f2f0986af53fbc52dd147b0af9c5db80a1de764c`

Base:

- `main` at `e37b9e47fa8770603a43e60bb190a17a403177c4`

The frozen seven-file implementation/review surface is:

1. `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md`
2. `docs/M4_MODEL_EXTRACTION_TRIAL.md`
3. `docs/ROADMAP.md`
4. `docs/reviews/M4_BENCHMARK_ANNOTATION_POLICY_FIRST_PASS.md`
5. `scripts/validate_m4_model_extraction_trial.py`
6. `scripts/validate_m4_model_extraction_trial_fallback_review.py`
7. `services/intelligence/model_extraction_trial.py`

The evaluation corpus/gold, schemas, Resolver/Verifier implementation, preserved v0.7 evidence artifacts, and frozen v0.7 review records are not changed by that head.

Exact-head validation before this fallback record was added:

- push `schema-validation` run `36748953122` — success on `f2f0986af53fbc52dd147b0af9c5db80a1de764c`;
- PR `schema-validation` run `36748959069` — success on the same head;
- PR `wikibase-verification` run `36748959160` — success on the same head;
- the schema-validation job shows the complete repository validator sequence passing, including the M4 model-extraction, fallback-review, Resolver/Verifier, governance, audit, and daily-brief validators.

## Scope and versioning verification

The implementation makes two evaluated annotation-policy clarifications and no metric-surface change:

- prompt template `v0.6` -> `v0.7`;
- adapter remains `m4-model-trial-v0.3`;
- report version remains unchanged;
- neither convention is mechanically enforced at the extraction boundary.

The prompt/version validators are updated consistently, while the historical v0.7 live-evidence record remains pinned to the prompt version under which it was actually produced. No preserved report or gold expectation is rewritten.

## RRV7-01 — designation typing

The rule is coherent as a bounded annotation convention:

- a named discrete equipment product, expressed as a specific designation for a countable, deliverable, or operable item, is typed `equipment_variant`;
- a generic class, family, or system reference remains `equipment`;
- the type assignment is ontology classification of the named entity, not an assertion that the source literally used the word "variant";
- the rule does not authorize inventing an unstated `variant_of` relationship.

This resolves the Falcon-X rule-1 tension without fitting the gold to the v0.7 model output. The gold already expected `equipment_variant` before the observed live run.

### Canonical grounding and evidentiary weight

The strongest explicit canonical precedent is F-15SA: the repository models the F-15SA as a specific variant relative to the F-15 family, and the existing deterministic M1 proposal uses the F-15SA canonical identity in the manufacturer relationship and delivery event.

PAC-3 MSE supplies useful additional naming precedent because the seed carries the discrete `PAC-3 MSE` item and the expanded `PATRIOT Advanced Capability-3 Missile Segment Enhancement` designation. Its evidentiary weight is narrower than F-15SA's: the current M0 seed does not encode a separate PAC-3 MSE `variant_of` statement. Accordingly, the PR's wording is supportable when read as "specific designation is a classification signal"; future summaries should not overstate the PAC-3 MSE alias as an independently encoded `variant_of` relation.

The ontology's `EquipmentVariant` definition (a specific model/variant separated from an equipment family when variant-specific facts differ) remains the governing conceptual anchor. The new rule is an evaluated bounded-trial classifier, not a new canonical fact or automatic ontology inference rule.

## RRV7-02 — conducted / led exercise fallback

The conducted-role fallback is strongly grounded.

The deterministic Resolver/Verifier predicate registry exposes `exercise.participant.organization` for organization involvement in an exercise and no separate conductor/leader organization predicate. More importantly, the existing Wikibase seed already maps an RSAF-led exercise to the generic participant property while its reference evidence states that the Royal Saudi Air Force led the exercise.

Therefore the bounded annotation choice is internally consistent:

- source-stated conducting or leading -> `participant` when no more-specific source-stated role applies;
- `host` only when hosting or venue responsibility is actually source-stated;
- no unsupported `conductor` or `leader` role is invented.

This convention also predates any post-hoc gold change: the prompt-injection fixture already expected `participant` for "conducted" before the v0.7 live output returned `host`.

## Cross-boundary finding — required follow-on, non-blocking for this PR

A surrounding-code review exposed a pre-existing semantic-signature mismatch that PR #36 does not introduce but makes more likely to surface once a model follows the clarified typing rule.

The bounded delivery gold combines:

- Falcon-X typed `equipment_variant`; and
- the Claim predicate `manufacturer.manufactures.equipment` pointing to Falcon-X.

The deterministic M1 F-15SA proposal likewise uses `manufacturer.manufactures.equipment` with the F-15SA canonical identity. However, the current Resolver/Verifier `_ENTITY_PREDICATES` signature accepts only an `equipment` value for `manufacturer.manufactures.equipment`, not `equipment_variant`. The extraction boundary itself performs referential/authority checks rather than that downstream predicate/entity-type compatibility check.

Consequently, a future extraction that correctly emits the benchmark's `equipment_variant` + manufacturer Claim combination can pass the extraction boundary and then fail closed when resolved to an `equipment_variant` canonical entity.

This is **not a blocker to PR #36's annotation-policy scope** because:

1. the mismatch predates this PR;
2. PR #36 does not claim downstream Resolver/Verifier preservation;
3. the separate downstream-preservation increment is explicitly still unqualified and untouched here; and
4. fixed-configuration extraction repeatability does not itself grant downstream or canonical authority.

It is nevertheless a required compatibility item for the downstream-preservation increment. Before any downstream-preservation qualification, that increment must reconcile the manufacturer predicate's semantic signature with the already-established variant-valued M1 usage (or otherwise define an equally explicit canonical representation) and add a regression proving that a correctly typed discrete variant manufacturer Claim does not fail merely because of the `equipment` / `equipment_variant` distinction. That requirement should not be silently bypassed by replaying only the observed v0.7 `equipment`-typed miss.

## Reconciliation with the maintainer first pass

The maintainer first-pass conclusions are confirmed with two precision additions:

- RRV7-01 is resolved as an evaluated designation-typing convention grounded most strongly by the ontology plus explicit F-15SA precedent; PAC-3 MSE is supporting designation evidence, not a second explicit `variant_of` edge.
- RRV7-02 is resolved, and the existing RSAF-led -> participant seed mapping strengthens the stated registry rationale.
- Gold and preserved v0.7 evidence remain untouched.
- Prompt v0.7 / adapter v0.3 / unchanged report version is internally consistent.
- No live call is needed or authorized by this review.
- The delivery `seller` -> expected `manufacturer` miss remains a model-output miss under the existing role convention; this increment does not relabel it as annotation ambiguity.

No additional blocker was found in the changed prompt, validators, documentation, authority boundary, or version pins.

## Qualification ceiling

This review does **not** qualify:

- GLM-5.3 compliance with prompt v0.7;
- fixed-configuration repeatability results;
- downstream Resolver/Verifier or human-review preservation;
- model quality or production extraction accuracy;
- production provider/model selection;
- representative latency, throughput, scale, or cost;
- autonomous approval, canonical mutation, or publication.

## Decision

Fallback second-review result for frozen PR head `f2f0986af53fbc52dd147b0af9c5db80a1de764c`:

**PASS for the benchmark-annotation-policy increment, with the designation/conducted conventions accepted as bounded evaluated semantics and the pre-existing manufacturer-predicate / `equipment_variant` Resolver compatibility issue explicitly carried into the separate downstream-preservation increment.**

Because this fallback review is a new documentation-only commit, PR #36 must receive successful exact-head CI on the commit containing this record before merge. The corpus/gold and preserved v0.7 evidence/review artifacts must remain byte-identical.