# Architecture Pattern Register Decision Log

This log records explicit architectural promotion, deferment, rejection, supersession, and trial authorization. Register entries do not promote themselves.

## APRD-001 — Adopt claim/evidence canonical knowledge model

- date: 2026-09-25
- pattern: APR-001
- from_status: CANDIDATE
- to_status: ACCEPTED
- forcing_function: The product must preserve sourced, temporal, conflicting defense knowledge and expose the same facts across multiple views.
- adopted_invariant: Material factual knowledge preserves claim identity, evidence provenance, temporal context, and revision history.
- scope: canonical defense knowledge represented by the Atlas.
- non_scope: editorial prose as authoritative storage; unsourced rumor as canonical truth.
- failure_model: orphan claims, destructive overwrite, evidence detached from claims, store-native identity leaking into domain identity.
- verification_plan: implementation-neutral schemas in M0; end-to-end source-to-page proof in M1.
- claim_ceiling: adoption establishes the domain contract, not the final storage implementation.
- authority_reference: `docs/ARCHITECTURE.md` ADR-0001 and `docs/ROADMAP.md` M0.
- rationale: This is the minimum data model needed to satisfy the product thesis.

## APRD-002 — Adopt review-gated canonical mutation

- date: 2026-09-25
- pattern: APR-002
- from_status: CANDIDATE
- to_status: ACCEPTED
- forcing_function: M0 requires machine read/write and AI-proposed changes without allowing model output to become canonical automatically.
- adopted_invariant: Proposal is distinct from canonical revision.
- scope: all canonical knowledge mutations, including AI-assisted ingestion.
- non_scope: deterministic internal metadata fields explicitly authorized as GREEN by policy may be admitted automatically through the same revision contract.
- failure_model: direct model writes, review bypass, hidden overwrite, ambiguous approval authority.
- verification_plan: demonstrate proposal creation, rejection without canonical mutation, approval with auditable revision, and deterministic policy rejection.
- claim_ceiling: successful verification establishes mutation-governance semantics for tested adapters, not universal security or production readiness.
- authority_reference: `docs/AI_GOVERNANCE.md`, `docs/ROADMAP.md` M0 criterion 7.
- rationale: The knowledge store must not become the authority boundary.

## APRD-003 — Authorize bounded Wikibase trial

- date: 2026-09-25
- pattern: APR-003
- from_status: CANDIDATE
- to_status: TRIAL-AUTHORIZED
- forcing_function: M0 must choose a knowledge-core implementation before M1.
- adopted_invariant: Any trial must preserve project-native claim/evidence/revision semantics and remain behind the proposal/review authority boundary.
- adaptation: Wikibase is evaluated as a storage/query implementation, not adopted as the project's ontology or governance vocabulary.
- scope: local reproducible M0 prototype using the seed dataset.
- non_scope: production hosting, scaling, availability, backup, final adoption, public release.
- failure_model: awkward qualifier/reference mapping; inability to represent conflict cleanly; write API bypassing governance; store-native identity leakage; excessive operational complexity.
- verification_plan: execute every M0 Wikibase acceptance criterion and record evidence in ADR-0002.
- claim_ceiling: passing the spike may justify architectural adoption for the knowledge-core role only.
- authority_reference: `docs/ROADMAP.md` M0 Wikibase Spike.
- rationale: Trial is authorized because reuse may substantially reduce custom knowledge-system engineering.

## APRD-004 — Defer custom PostgreSQL knowledge core

- date: 2026-09-25
- pattern: APR-004
- from_status: CANDIDATE
- to_status: DEFERRED
- forcing_function: none while the Wikibase trial remains viable.
- scope: potential M0 fallback.
- non_scope: current implementation work.
- verification_plan: only activate if APR-003 fails a critical acceptance criterion or demonstrates unacceptable complexity.
- claim_ceiling: no implementation claim; fallback remains architectural knowledge only.
- authority_reference: `docs/ARCHITECTURE.md` M0 decision gate.
- rationale: Avoid parallel implementation and infrastructure inflation before evidence requires it.