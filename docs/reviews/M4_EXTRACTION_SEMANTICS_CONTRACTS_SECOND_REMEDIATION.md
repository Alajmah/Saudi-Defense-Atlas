# M4 Extraction Semantics Contract — Second Remediation Record

## Protocol

This record remediates the three findings of the fresh fallback second review `5365805681` on PR #33 at frozen head `ee018a179a17628fe50185b5ff28f0abcd503023` (gate: CHANGES REQUIRED). The first-pass and first remediation records are preserved unchanged; this record is additive.

No live call, no merge, no entitlement attestation. Gold and the corpus fixture remain byte-identical to `main`.

## Finding-by-finding remediation

### FSR2-01 — HIGH — gold/ID metric contract not validated before invocation — REMEDIATED

`load_cases()` previously checked only that a version string and a non-empty case list existed. The gold-based bucket machinery then ran after execution: a truthy non-object `gold` would raise `AttributeError` post-invocation, an unrecognized or missing `expected_status` would silently place the case in none of the three denominators, and duplicate case IDs would collapse the gold lookup. Malformed custom evaluation input could therefore consume live model calls and then crash or shrink the quality denominators.

Remediation: `validate_metric_contract(cases)` runs inside `load_cases()`, before provider setup and before any model invocation. It requires unique non-empty string case IDs, object-valued `gold`, and exactly one of the three legal expected statuses (`accepted_for_candidate_review`, `rejected`, `blocked_before_invocation`) per case, and fails closed with a case-identifying message. Regression coverage: six malformed shapes (blank id, non-string id, duplicate ids, non-object gold, missing status, unknown status) each rejected; a malformed-fixture file rejected through `load_cases()` itself, proving the wiring.

### FSR2-02 — MEDIUM — invoked metric diverged from its documented meaning — REMEDIATED

The contract described `invoked_quality_case_pass_rate` as substantive plus expected-abstention, while the denominator was all observed invocations and the numerator was reconstructed from the two bucket pass counts. An unexpectedly invoked policy-gate case would have entered the denominator while its result vanished from the numerator.

Remediation: the pass count is computed directly over `invoked_results` — every observed invocation contributes, whatever its gold expectation. The contract and trial document now state the observed-invocation basis explicitly, including that an unexpectedly invoked policy-gate case counts in both the invoked rate and the policy denominator. The contract no longer describes the policy metric as "unchanged from v0.6"; the field names survive, the membership semantics are gold-based. Symmetric adversarial regression added: an invoked policy-gold case stays in the policy bucket (failing it), never enters substantive or abstention, and the observed-invocation pass count includes its failure directly.

### FSR2-03 — LOW — stale PR description — REMEDIATED (metadata only)

The PR description still advertised ontology-derived role rules, prompt v0.5, and `66102e3` as the validation tip. Updated after this remediation push to state: bounded-trial annotation conventions, prompt v0.6, adapter v0.3, report v0.7, the full FSR and FSR2 remediation chain, and the new exact-head validation SHA. No branch change was needed for this item.

## Deterministic validation evidence

- Complete repository suite at the remediation commit: all 38 `scripts/validate_*.py` validators — **PASS**, including the preflight rejection matrix, the `load_cases` wiring test, and the symmetric invoked-policy adversarial case. The deterministic corpus's happy-path split (4 substantive / 1 abstention / 1 policy, invoked 5/5) is unchanged and still asserted.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` and `wikibase-verification` on the same tip.

## Explicitly unverified / unresolved

- The conventions remain unproven as model-quality instruments until a reviewed rerun under prompt v0.6; that rerun requires a fresh run-specific operator entitlement attestation.
- Semantic class-to-unit mapping and canonical role precedence remain deliberately undefined, per the corrected contract.
- RRV6-04/RRV6-05 claim-discipline constraints stand unchanged.

## Freeze

This record completes remediation of FSR2-01 through FSR2-03. The remediated head awaits the next fallback review of the new exact SHA before PR #33 may merge.
