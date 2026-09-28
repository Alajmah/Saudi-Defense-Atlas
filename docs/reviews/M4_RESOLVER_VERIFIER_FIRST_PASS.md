# M4 Resolver / Verifier First-Pass Review

## Scope

Review of PR #20 against the M4 deterministic resolver/verifier forcing function and the existing proposal/review/revision authority boundary.

## Findings

### RV-F01 — Ambiguous entity references collapsed into unresolved downstream assessments — FIXED

The v0.2 core represented both ambiguous and unresolved entity mentions as `None` in its internal lookup. Claim/Event assessment therefore emitted `blocked_unresolved` for both, despite the public run schema defining `blocked_ambiguous` separately and the PR contract promising explicit ambiguity.

**Fix:** the public resolver boundary now preserves the frozen v0.2 proposal semantics while postconditioning downstream audit classifications from explicit `entity_resolutions`. Any blocked Claim/Event that references an entity with `outcome = ambiguous` is reported as `blocked_ambiguous`; genuinely unmatched mentions remain `blocked_unresolved`. The behavior change is versioned as `resolver-verifier-v0.3`, producing a new deterministic resolution-run ID. A dedicated adversarial validator proves both classifications and proves no canonical match from an ambiguous set enters the proposal.

### RV-F02 — Branch CI definition lagged accepted `main` validation surface — FIXED

PR #20 branched before later M3 hardening was merged and also modified `schema-validation.yml`. Merging the stale workflow would have dropped the public-map hardening gate.

**Fix:** the PR is synchronized with current `main` via a merge commit. Its workflow is based on current `main` and adds only the M4 resolver/verifier and isolation validators.

## Reviewed with no blocking issue found

- exact multilingual name/selected-alias resolution remains deterministic and type-constrained;
- search-only aliases are not resolution authority;
- duplicate Claim detection does not mint mutations;
- same-time conflicting Claims are preserved as `disputed` + `unverified` review candidates rather than overwriting canonical facts;
- clearly distinct point-in-time history is not collapsed into conflict;
- uncertain temporal overlap and scoped canonical Claims fail closed as `blocked_ambiguous`;
- inventory/procurement quantities remain blocked from this automated preparation path;
- public latitude/longitude extraction is policy-blocked;
- candidate Evidence must remain within the extraction run's source-document provenance and is materialized with original locator/hash context;
- possible-duplicate Events are suppressed from mutation preparation without being asserted as certain duplicates;
- prepared factual records remain `unverified`;
- any emitted proposal remains `AMBER` + `human_review_required`;
- resolver authority explicitly excludes approval, canonical mutation, and publication;
- no proposal is emitted when no mutation survives deterministic blocking/deduplication.

## Remaining claim ceiling

This review verifies only the deterministic candidate-resolution/comparison/proposal-preparation boundary. It does not authorize fuzzy entity resolution, model self-verification, automatic approval, canonical writes, publication, concurrent writers, or production orchestration.
