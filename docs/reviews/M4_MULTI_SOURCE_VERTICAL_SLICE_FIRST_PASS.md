# M4 Multi-Source Editorial Vertical Slice — Exhaustive First Pass

**Scope:** PR #24 bounded deterministic integration proof from two authoritative monitoring observations through canonical Revision and public EquipmentView.

## Disposition

The slice is suitable for merge once exact-head CI passes after the remediation below. This review does not qualify model extraction quality, distributed/concurrent writers, production orchestration, scheduler reliability, automatic approval, or autonomous publication.

## Finding M4-VS-F01 — Multi-source context could collapse before canonical/public provenance — FIXED

**Original condition:** the queue and review packet preserved both Source/Document identities, but the deterministic Evidence assignment alternated by list index. Every Evidence candidate that survived resolver/verifier admission happened to land on the same source Document. The final assertion accepted any non-empty citation subset of the two source IDs, so the test could pass while one authoritative source disappeared from canonical Evidence and the public EquipmentView.

**Risk:** the PR claimed a multi-source editorial vertical slice, but the executable proof only established multi-source review metadata plus a single-source canonical/public factual path.

**Remediation:**

- distribute proposal-bearing candidate Evidence across both authoritative Documents;
- assert canonical Evidence references exactly both queue Documents;
- assert public EquipmentView citations contain exactly both authoritative Source IDs;
- keep Source/Document identity and supporting Evidence provenance unchanged through the existing accepted boundaries.

**Verification requirement:** `python scripts/validate_m4_multi_source_vertical_slice.py` must pass on the final PR head through the normal schema-validation workflow.

## Areas reviewed with no additional blocker

- deterministic exact-content deduplication remains upstream of extraction;
- queue and extraction retain no canonical mutation authority;
- resolver/verifier continues to emit AMBER + human-review-required proposals only;
- review packet and decision binding preserve exact proposal/content hashes;
- canonical execution reuses the existing single-writer mutation guard;
- project Revision accounts for every converged mutation;
- public projection is built from applied canonical Evidence/Claim/Event payloads rather than proposal objects;
- public provenance remains SDA-ID based with no backend identity leakage;
- no LLM provider, scheduler, queue backend, orchestrator, or publication engine is selected by this slice.

## Claim ceiling

Passing this slice proves deterministic integration of already-accepted M4/M1 contracts for one bounded two-source case. It does not prove factual extraction quality, corroboration quality across arbitrary sources, production queue semantics, distributed mutation coordination, or autonomous editorial operation.
