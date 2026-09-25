# Architecture Pattern Register Source Ledger

The source ledger records the evidence basis used to characterize architectural patterns. External evidence can inform architecture but does not itself authorize adoption.

## SRC-PROJ-001 — Architecture baseline

- kind: project-native
- identity: `docs/ARCHITECTURE.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: canonical domain model, system boundaries, design rules, M0 knowledge-core gate, deferred decisions
- reliability_notes: project-authoritative architectural baseline, subject to later ADR supersession
- linked_patterns: APR-001, APR-003, APR-004, APR-006
- claim_limitations: does not prove implementation or production fitness

## SRC-PROJ-002 — Ontology v0.1

- kind: project-native
- identity: `docs/ONTOLOGY.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: entity/claim/evidence/event semantics, procurement/service states, quantity, naming, temporal and geographic semantics
- reliability_notes: conceptual contract; not yet an executable schema
- linked_patterns: APR-001, APR-005
- claim_limitations: does not define storage or mutation authority

## SRC-PROJ-003 — Source and claim admission policy

- kind: project-native
- identity: `docs/SOURCE_POLICY.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: source classes, claim admission, confidence, review requirements, staleness, corrections
- reliability_notes: project policy baseline
- linked_patterns: APR-001, APR-002
- claim_limitations: automation thresholds remain intentionally qualitative in v0.1

## SRC-PROJ-004 — AI governance policy

- kind: project-native
- identity: `docs/AI_GOVERNANCE.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: AI roles, GREEN/AMBER/RED authority, trace requirements, mutation/publication constraints, evaluation
- reliability_notes: project policy baseline
- linked_patterns: APR-002, APR-005, APR-006
- claim_limitations: no concrete implementation has yet been verified

## SRC-PROJ-005 — M0/M1 roadmap

- kind: project-native
- identity: `docs/ROADMAP.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: current-plan authorization, M0 Wikibase spike, acceptance criteria, M1 vertical slice
- reliability_notes: current planning authority for foundation and M0
- linked_patterns: APR-001, APR-002, APR-003, APR-004, APR-005, APR-006
- claim_limitations: later milestones are planned outcomes, not implemented commitments

## SRC-APR-001 — Architecture Pattern Register governance specification

- kind: external/project-supplied governance specification
- identity: `Architecture Pattern Register Agent Implementation Specification` supplied to the project agent
- revision: supplied 2026-09-25
- observed_at: 2026-09-25
- inspection_scope: separation of observation/adoption/implementation/verification, forcing functions, status axes, promotion records, evidence ceilings, source ledger, validation rules
- reliability_notes: used as a governance mechanism; its source-project architecture and vocabulary are not imported as product architecture
- linked_patterns: governance shell for all APR entries
- claim_limitations: does not authorize product implementation or adoption of any specific mechanism

## SRC-REV-001 — Independent foundation review

- kind: project-native review
- identity: `docs/reviews/FOUNDATION_FIRST_PASS.md`
- revision: initial frozen review
- observed_at: 2026-09-25
- inspection_scope: foundation architecture, ontology, authority, failure semantics, M0 prerequisites
- reliability_notes: frozen pre-implementation assessment; later findings must not rewrite this baseline
- linked_patterns: APR-002, APR-003, APR-005
- claim_limitations: findings are architectural review evidence, not implementation verification