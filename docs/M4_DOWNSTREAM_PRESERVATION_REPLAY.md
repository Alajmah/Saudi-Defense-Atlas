# M4 Downstream-Preservation Replay

## Status

Implemented as a deterministic offline replay (`scripts/validate_m4_downstream_replay.py`, CI-gated). No live model call, no canonical backend, and no publication path participate in the replay.

## Purpose

The frozen v0.7 evidence review sequenced this increment: prove that accepted live-trial candidate semantics survive the existing Resolver/Verifier and human-review boundary offline, without granting canonical mutation or publication authority — and reconcile the pre-existing `manufacturer.manufactures.equipment` target-type incompatibility surfaced by the PR #36 review.

## Resolver signature reconciliation

The Resolver/Verifier restricted `manufacturer.manufactures.equipment` to an `equipment` target while established usage — the M1 F-15SA proposal and the merged designation-typing convention — points that predicate at `equipment_variant`. The predicate signature now accepts both target types (`organization → equipment | equipment_variant`). The mismatch predates the annotation-policy increment; no frozen behavior depended on the restriction (no existing validator pinned it).

## What the replay proves

1. **Provenance gate (hard).** The replay refuses to run unless the preserved v0.7 report's bytes hash simultaneously to its committed sidecar digest, to the frozen reviewed digest constant, and the corpus it reads — the frozen generation-time copy at `docs/evidence/m4/2026-09-30/corpus/` (sidecar-verified) — hashes to the `trial_context.corpus_sha256` the report recorded at generation time. Since the semantics adjudication moved the live fixture to v0.4, the replay binds to the frozen v0.3 bytes so drift of the report, sidecar, or corpus copy cannot pass the gate together. It replays exactly the frozen reviewed evidence in its generation-time corpus context.
2. **Rejection isolation.** The rejected v0.7 run (the structured abstention) raises at the resolver boundary and never reaches resolution.
3. **Accepted-run preservation.** Each of the four accepted runs resolves against a canonical registry typed per the merged annotation conventions. Where the resolver prepares an AMBER proposal, the replay builds the editorial review packet, a human decision, and the exact decision binding — each schema-valid, with Document provenance preserved into the packet, `risk_class = AMBER`, and `policy_outcome = human_review_required`.
4. **Honest outcomes, shown not hidden.** The quantity claim is blocked downstream by the resolver's quantity-corroboration policy (`blocked_ambiguous`), and the actual v0.7 delivery claim is `blocked_unresolved` because the model typed Falcon-X as `equipment`, which does not resolve against the correctly typed registry. Both are asserted as observed outcomes.
5. **Corrected-typing regression (the PR #36 obligation).** The counterfactual is a clearly labeled derived synthetic run: the preserved delivery run's candidate envelope with Falcon-X typed per the merged designation convention (`equipment_variant`), re-processed through the deterministic extraction boundary so it carries its own extraction-run identity, input/raw-output hashes, synthetic model trace, and timestamps — never the preserved run's audit identity (distinct identity is asserted). Under the reconciled signature its `manufacturer.manufactures.equipment` claim survives Resolver/Verifier semantics with outcome `new` and is carried in the AMBER proposal's mutations. The replay does not evade the obligation by replaying only the model's incorrect typing: both the actual and the corrected outcomes are asserted.
6. **Zero authority.** No canonical backend is invoked or instantiated (transitive module imports exist through the decision-binding service; the replay never calls or constructs a backend); every replayed artifact remains candidate/proposal/decision data bound to human review; all runs carry `canonical_mutation_authority = false` and `publication_authority = false`, and every resolution run — including no-proposal cases — is schema-validated and asserts `mode = proposal_preparation_only` with all three authority flags false.

## Where the regression lives

The variant-manufacturer regression lives in the replay validator rather than the resolver-validator fixture deliberately: it runs against the actual preserved live-trial artifacts (plus the corrected-typing variant of them), proving survival on real model output rather than only on a synthetic fixture. It executes in CI on every push via the `schema-validation` workflow.

## Claim ceiling

This replay proves preservation of admitted candidate semantics through the reviewed downstream boundary on the synthetic corpus, offline. It does not qualify extraction quality, does not execute canonical writes (the replay stops at the decision binding), does not cover the full editorial audit brief or daily-brief projections, and makes no production claim. Fixed-configuration live repeatability trials remain a separate, later step per the roadmap sequence.
