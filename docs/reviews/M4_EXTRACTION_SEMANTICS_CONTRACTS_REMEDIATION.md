# M4 Extraction Semantics Contract — Remediation Record

## Protocol

This record remediates the four blocking findings of the fallback second review `5365118637` (posted on PR #33 at frozen head `66102e3e45163262799e9fef3ede5bc6e66c0537`; protocol gate CHANGES REQUIRED). The first-pass record is preserved unchanged; this record is additive.

No live call, no merge, no entitlement attestation. Gold and the corpus fixture remain byte-identical to `main`.

## Finding-by-finding remediation

### FSR-01 — HIGH — denominator classification wrong under failure — REMEDIATED

The runner previously bucketed by observed behavior: `policy_results` was every observed non-invocation, and only invoked cases entered the substantive/abstention buckets. A substantive-gold case that was unexpectedly blocked before invocation therefore disappeared from the substantive denominator instead of counting as a failure there.

Remediation: bucket membership now comes **solely from `gold.expected_status`** via a new testable function `classify_quality_buckets(results, cases)`. Observed invocation remains a separate metric (`invoked_case_count`, `invoked_quality_case_pass_rate`). The contract document states the rule explicitly. Adversarial regression added: a synthetic results list containing an unexpectedly blocked substantive case (`TRIAL-EN-DELIVERY` gold-accepted, observed not invoked, run absent) asserts the case stays in the substantive bucket, does not leak into the policy bucket, and no spurious abstention bucket appears.

Report version stays `v0.7`: that version was never published in any merged artifact (the only live evidence is v0.6), so its definition is corrected in place within this PR rather than versioned again.

### FSR-02 — HIGH — role semantics contradictory and over-derived — REMEDIATED

The contract claimed the role rules were derived from canonical semantics while also saying a role reflects the relation "to this event, not to the equipment in general" — yet anchored `manufacturer` in an organization→equipment predicate. The ontology registers predicates and prohibits free-text ones; it states no role-precedence law, and the Event schema supplies vocabulary without precedence semantics.

Remediation: the role section is reframed as **bounded-trial annotation conventions** — chosen mappings (stated manufacture → `manufacturer` including in delivery events; contract-signature/award company party → `contractor`; `supplier` only when supply is all the source states; exercise/training attendance → `participant`), with the specificity preference described as mirroring the ontology's precision discipline "without being implied by it." A new provenance note states plainly that the predicate registry inspired the mappings but relates entities to entities and assigns no event-participant roles; the conventions were fixed against pre-existing corpus gold and make no claim about canonical SDA semantics. The internal contradiction is resolved by dropping the "not to the equipment in general" framing in favor of the convention list.

### FSR-03 — MEDIUM — unit rule mixed lexical and semantic normalization — REMEDIATED

The old rule's `84 F-15SA → aircraft` example required semantic entity classification, not lexical normalization, while exact-gold scoring treated the result as normative.

Remediation: the rule is narrowed to the **head noun of the counted-class phrase the source itself states**, with modifiers removed ("12 trainer aircraft" → `aircraft`). When the source counts by designation only, the unit is the designation exactly as stated. A semantic class-to-unit mapping is explicitly declared undefined and out of scope until independently justified. The contract and prompt rule 18 both carry the narrowed rule; the `84 F-15SA` example is removed.

### FSR-04 — MEDIUM — status documents stale after PR #32 — REMEDIATED

The trial document now records the v0.6 rerun as merged reviewed evidence (PR #32: 2/5 invoked, 1/4 substantive derived, four contract deltas behaving as intended) and marks the next rerun — under prompt v0.6/report v0.7, requiring a fresh attestation — as pending. The ROADMAP remaining-bullet now attributes unqualified downstream Resolver/Verifier preservation to the actual cause: the complete downstream path was never executed on either run's live candidates; the superseded first-run role-vocabulary rationale is removed (the rerun's roles were canonical). Version strings across both documents are updated.

## Version note

Prompt template v0.5 → **v0.6** (rule 18 reworded per FSR-03; the version-pin validator forced the bump). Adapter remains `m4-model-trial-v0.3`; report remains `v0.7` (corrected in place, never published); corpus/gold unchanged.

## Deterministic validation evidence

- Complete repository suite at the remediation commit: all 38 `scripts/validate_*.py` validators — **PASS**, including the new FSR-01 adversarial bucket regression, the v0.6 template pin, and the updated unit-rule prompt fragments in both the harness and fallback validators.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` and `wikibase-verification` on the same tip.

## Explicitly unverified / unresolved

- The conventions remain unproven as model-quality instruments until a reviewed rerun under prompt v0.6; that rerun requires a fresh run-specific operator entitlement attestation.
- Semantic class-to-unit mapping and canonical role precedence remain deliberately undefined; defining either requires independent justification per the corrected contract.
- RRV6-04/RRV6-05 claim-discipline constraints stand unchanged.

## Freeze

This record completes remediation of FSR-01 through FSR-04. The remediated head awaits the fresh fallback review of the new exact SHA before PR #33 may merge.
