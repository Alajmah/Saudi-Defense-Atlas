# Architecture Pattern Register Decision Log

This log records explicit architectural promotion, deferment, rejection, supersession, trial authorization, and bounded verification. Register entries do not promote themselves.

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
- scope: potential knowledge-core fallback.
- non_scope: current implementation work.
- verification_plan: only activate if APR-003 fails a critical project invariant or later evidence demonstrates unacceptable complexity.
- claim_ceiling: no implementation claim; fallback remains architectural knowledge only.
- authority_reference: `docs/ARCHITECTURE.md` M0 decision gate / ADR-0002 fallback clause.
- rationale: Avoid parallel implementation and infrastructure inflation before evidence requires it.

## APRD-005 — Promote Wikibase to accepted knowledge core

- date: 2026-09-25
- pattern: APR-003
- from_status: TRIAL-AUTHORIZED
- to_status: ACCEPTED
- implementation_status: VERIFIED for the bounded M0 representation/governance contract
- forcing_function: M1 requires a selected knowledge-core implementation and the M0 trial has now produced clean current-head verification evidence.
- adopted_invariant: Wikibase is subordinate to SDA domain identity, ontology, evidence semantics, and mutation authority.
- adaptation: claims project to statements/qualifiers; evidence projects to references without replacing the richer SDA Source/Document/Evidence model; SDA IDs map to Q/P IDs but remain canonical.
- scope: canonical knowledge storage/query implementation for M1.
- non_scope: production security, HA, backup/recovery, target-scale performance, exactly-once mutation, ambiguous-effect reconciliation, public API hardening, long-term upgrade qualification.
- failure_model: Q/P identity leakage; adapter bypass; WDQS convergence lag; production operational burden; ambiguous external effects; future store constraints that distort SDA semantics.
- verification_plan: completed M0 clean run plus continuing M1 vertical-slice verification; production properties require separate verification.
- verification_evidence: schema/governance run `36178033709`; Wikibase run `36178040438` / job `108213344752`; artifact `10883261546`; ADR-0002 acceptance matrix.
- claim_ceiling: Wikibase is suitable to proceed as the M1 canonical knowledge core under the tested project-owned adapter/governance contract.
- authority_reference: `docs/adr/ADR-0002-knowledge-core.md`.
- rationale: All critical M0 criteria passed without material ontology distortion or governance bypass.

## APRD-006 — Record bounded verification of review-gated mutation

- date: 2026-09-25
- pattern: APR-002
- pattern_status: ACCEPTED (unchanged)
- implementation_status_from: IN-TRIAL
- implementation_status_to: VERIFIED
- scope: tested M0 proposal/review/hash-binding/temporal-order/adapter-receipt contract.
- non_scope: production exactly-once behavior, retry safety after ambiguous external effects, distributed concurrency, or durable queue semantics.
- verification_evidence: workflow fixtures and validation; synthetic AMBER approval applied through `apply_approved_demo.py` in run `36178040438`.
- claim_ceiling: the tested adapter does not write before authorization and records backend identifiers as receipts after the effect; broader mutation reliability remains future work.
- authority_reference: `docs/AI_GOVERNANCE.md`, `docs/reviews/M0_ADVERSARIAL_REVIEW.md`, ADR-0002.

## APRD-007 — Authorize bounded deterministic SVG relationship-visualization trial

- date: 2026-09-26
- pattern: APR-007
- from_status: CANDIDATE
- to_status: TRIAL-AUTHORIZED
- implementation_status: IN-TRIAL
- forcing_function: M2 requires a first relationship visualization while the accepted graph is deliberately bounded and no frontend/graph runtime has been selected.
- adopted_invariant: visualization consumes `RelationshipGraphView` only and may not invent topology, replace SDA identity, or remove supporting Evidence from material relationships.
- adaptation: use server-rendered deterministic inline SVG with semantic cited HTML fallback; localize labels without changing graph identity.
- alternatives_characterized: Cytoscape.js; D3 selection/force; project-owned SVG.
- scope: first bounded M2 relationship visualization and bilingual route/API proof.
- non_scope: large graph exploration, force-directed layout, drag/pan/zoom, graph editing, browser-side graph analysis, final frontend stack selection.
- failure_model: visual-only inferred edges, Q/P leakage, citation loss, nondeterministic layout, inaccessible SVG, global SVG ID collisions, bounded layout used past readable scale.
- verification_plan: deterministic reorder test; supporting-Evidence rejection; accessible title/description; graph-scoped SVG IDs; cited HTML fallback; bilingual routes; exact graph JSON API; no backend identifiers.
- claim_ceiling: successful trial may justify acceptance only for the bounded M2 visualization role.
- authority_reference: `docs/adr/ADR-0003-first-relationship-visualization.md`, `docs/ROADMAP.md` M2.
- rationale: the first graph is small enough that a browser-native deterministic renderer meets the forcing function with less dependency/interaction surface than a general graph engine.
