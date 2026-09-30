# M4 Downstream-Preservation Replay — Remediation Record

## Protocol

This record remediates the four blocking findings of the independent first-pass review comment `5370765946` on PR #37 at frozen head `8b90146c4949a8ee020f2fe5e5c5e2a5e82608ab`. The first-pass record is preserved unchanged; this record is additive. Codex remained quota-blocked; no fallback second review is claimed for a head with unresolved primary findings.

No live call, no merge, no gold or evidence edits.

## Finding-by-finding remediation

### DRR-01 — HIGH — resolver semantics changed without resolver identity — REMEDIATED

The predicate reconciliation changed `_ENTITY_PREDICATES` behavior while the public resolver stayed `resolver-verifier-v0.3` and the edited core still identified as v0.2 — so identical extraction input could receive different semantics under one recorded version and resolution-run identity, contradicting the repository's own v0.2→v0.3 precedent.

Remediation: both the core (`_RESOLVER_VERSION`) and the public boundary (`_PUBLIC_RESOLVER_VERSION`) now identify as `resolver-verifier-v0.4`, minting a new deterministic resolution-run identity for the reconciled semantics. The wrapper docstring now states the versioned history truthfully (v0.2 proposal semantics, v0.3 audit correction, v0.4 manufacturer-target reconciliation) instead of describing the core as frozen v0.2. The isolation validator's version pin was updated to v0.4.

### DRR-02 — HIGH — counterfactual corrupted audit identity — REMEDIATED

The original regression deep-copied the preserved delivery run and edited the entity type in place, retaining the preserved run's ID, hashes, model/prompt trace, timestamps, and evaluation trace — an impossible audit artifact, since run identity is derived from exactly those fields.

Remediation: the counterfactual is now a clearly labeled derived synthetic run. The preserved run's candidate envelope (with Falcon-X corrected per the designation convention) is re-processed through the deterministic extraction boundary (`build_extraction_run_from_model_output`) with a synthetic model trace (`provider="downstream-replay"`, `model="synthetic-corrected-delivery"`), explicit synthetic timestamps, and the case's rendered prompt — so the synthetic run derives its own ID, input/raw-output hashes, and trace. The validator asserts the synthetic run's identity differs from the preserved run's, carries its synthetic provenance label, and passes the extraction boundary before resolution.

### DRR-03 — MEDIUM — provenance gate under-anchored — REMEDIATED

The gate compared the report only to the current sidecar; report and sidecar could drift together, and the fixture queue context was taken from the current corpus without binding it to the frozen report.

Remediation: the gate now requires the report bytes to equal the frozen reviewed digest constant `06d9e8c7…a463` and the current sidecar, and requires the current corpus fixture to hash to the `trial_context.corpus_sha256` the report recorded at generation time. Drift of any one of report, sidecar, or fixture now fails the replay immediately.

### DRR-04 — MEDIUM — claimed assertions absent — REMEDIATED

Added: the quantity claim's `blocked_ambiguous` outcome is explicitly pinned; every resolution run — including no-proposal cases — is validated against `ai-resolution-verification-run.schema.json`; and every resolution run's authority block is asserted to be `mode = proposal_preparation_only` with `approval_authority`, `canonical_mutation_authority`, and `publication_authority` all false. The corrected-typing resolution run receives the same schema validation and authority assertions.

### Wording correction — applied

The replay's zero-authority claim now says no canonical backend is **invoked or instantiated**, acknowledging that the decision-binding service transitively imports mutation-guard/backend symbols. The script docstring, the replay document, and the PR description carry the corrected wording.

## Deterministic validation evidence

- Complete repository suite at the remediation commit: all 39 validators — **PASS**, including the remediated replay validator (hard provenance gate, derived synthetic counterfactual with distinct identity, quantity pin, resolution-run schema and authority assertions on every case).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- The replay remains a preservation proof on the synthetic corpus, not a quality measurement or canonical execution; the quantity-corroboration policy question remains separately scoped.
- Fixed-configuration repeatability trials remain sequenced after this increment merges and passes review.

### Post-push correction (before review)

The first push of this remediation failed its own new gate in CI: the report's `corpus_sha256` was recorded from a CRLF Windows working tree, while the Linux CI checkout holds the identical fixture with LF bytes, so a raw-byte comparison is checkout-dependent. The gate now accepts the recorded digest under either line-ending representation of the same fixture bytes, binding the replay to corpus content rather than to one platform's checkout representation. Discovered by the CI run on the remediation commit; corrected before any review of this record.

## Freeze

This record completes remediation of DRR-01 through DRR-04. The remediated head awaits the next independent review of the new exact SHA.
