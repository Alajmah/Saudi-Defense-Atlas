# ADR-0002 — Canonical Knowledge-Core Implementation

**Status:** Accepted

**Decision date:** 2026-09-25

**Pattern:** APR-003 (Wikibase) / APR-004 (PostgreSQL fallback)

## Context

ADR-0001 defines an implementation-neutral knowledge model and explicitly prevents the backing store from becoming the project's authority model. M0 evaluated whether Wikibase can represent and expose those semantics cleanly enough to adopt for the canonical knowledge-core role.

This decision is intentionally narrower than production deployment. Successful M0 verification does not establish production security, high availability, backup/recovery, scale, mutation-reconciliation guarantees, or hosting topology.

## Decision

Adopt **Wikibase** as the canonical knowledge-core implementation for M1, behind the project-native `ChangeProposal -> ReviewDecision -> Revision` authority boundary.

Wikibase is adopted as a storage/query implementation, not as the owner of Saudi Defense Atlas ontology, confidence semantics, evidence policy, mutation authority, or public identity.

Project SDA IDs remain canonical. Wikibase Q/P identifiers remain backend mappings.

## Candidate A — Wikibase

Trial implementation: `spikes/wikibase/`

Architecture status after this decision:

- pattern_status: `ACCEPTED`
- implementation_status: `VERIFIED` for the bounded M0 representation/governance contract
- planning_disposition: `current-plan-authorized`

## Candidate B — PostgreSQL claim/evidence store

Architecture status remains:

- pattern_status: `DEFERRED`
- implementation_status: `NOT-LINKED`
- planning_disposition: `future-plan-candidate`

PostgreSQL remains the explicit fallback if later implementation evidence exposes material Wikibase limitations that violate project invariants. Acceptance of Wikibase does not erase fallback knowledge.

## M0 Acceptance Matrix

| Criterion | Observed evidence | Result |
|---|---|---|
| Arabic + English labels | RSAF item returned both labels | PASS |
| aliases | `RSAF` resolved to the same RSAF item | PASS |
| domain/store identity separation | `SDA-ORG-RSAF` mapped to Q1 while remaining distinct | PASS |
| typed relationships | item-valued F-15SA relationships were created/read | PASS |
| qualifiers | claim ID, quantity type, time, and confidence survived round-trip | PASS |
| multiple references | F-15SA quantity statement retained at least two references | PASS |
| conflicting claims | synthetic `+10` and `+12` quantities coexisted without overwrite | PASS |
| temporal semantics | day-qualified statements round-tripped | PASS |
| procurement-stage semantics | PAC-3 MSE possible-FMS event remained `procurement_approval_or_notification` | PASS |
| revision history | multiple MediaWiki revisions were observed | PASS |
| machine read/write API | Action API seed/read/write path succeeded | PASS |
| query support | WDQS resolved RSAF by SDA canonical ID | PASS |
| review-before-admission | schema/workflow validation and approved synthetic adapter gate passed | PASS |
| backend remains subordinate to governance | proposal/decision authorization preceded write; project Revision recorded backend receipt after write | PASS |

## Verification Evidence

### Exact implementation head

- branch: `bootstrap/foundation`
- implementation head verified: `e3d08935907d85c20da12531a81a22d43e23f597`

### Schema and governance validation

GitHub Actions run `36178033709` completed successfully. Its validation job passed both:

- schema/fixture validation;
- proposal/review/revision mutation-governance validation, including temporal ordering.

### Wikibase clean-run verification

GitHub Actions run `36178040438`, job `108213344752`, completed successfully on the same implementation head.

The clean run successfully executed:

1. local Wikibase/WDQS stack startup;
2. API health verification;
3. M0 fixture seeding;
4. representation verification;
5. one human-approved synthetic proposal through the adapter gate;
6. evidence artifact upload;
7. clean stack teardown.

Artifact `wikibase-m0-verification` (`10883261546`) contains:

- `state.generated.json` — project-ID/backend-ID and statement mappings;
- `verification.generated.json` — bounded representation/query verification report with status `PASS`;
- `approved-demo-applied.generated.json` — approved synthetic mutation result with project Revision and backend receipt.

Observed verification details include:

- bilingual/alias resolution = PASS;
- SDA identity distinct from Q-ID (`SDA-ORG-RSAF` / Q1);
- qualified multi-reference claim = PASS;
- contradictory synthetic quantities `+10` and `+12` coexist;
- procurement-stage separation = `procurement_approval_or_notification`;
- revision history visible;
- SPARQL lookup = PASS;
- Action API read = PASS;
- synthetic approved mutation produced `SDA-REVISION-M0-DEMO-001` with a Wikibase statement/revision recorded only as backend receipt.

## Why Wikibase Passed

The trial did not require a material change to project-native semantics:

- SDA IDs remain independent from Q/P IDs;
- claims map cleanly to statements plus qualifiers;
- evidence can project to multiple references while the richer `Source -> Document -> Evidence` model remains project-owned;
- conflicting claims can coexist;
- multilingual labels/aliases are native;
- revisions and query/API access are available;
- governance records remain outside Wikibase and authorize backend writes rather than being replaced by backend revision history.

The adapter is non-trivial but not disproportionate to the infrastructure reuse gained.

## Claim Ceiling

This ADR establishes only:

> The tested Wikibase configuration is suitable to proceed as the Saudi Defense Atlas canonical knowledge-core implementation for M1 under the project-native ontology and mutation-governance boundary.

It does **not** establish:

- production security or authorization design;
- production availability/HA;
- backup or disaster recovery;
- performance/scalability at target dataset size;
- long-term upgrade compatibility;
- production observability;
- exactly-once mutation semantics;
- reconciliation after ambiguous or interrupted external effects;
- public API security/hardening.

Those require separate implementation and verification.

## Consequences

### Authorized next work

M1 may implement the first source-to-public-page vertical slice against Wikibase through a project-owned adapter/API boundary.

### Required architectural constraints

- public/application code depends on SDA domain contracts, not raw Q/P identity;
- no AI/free-form output writes directly to Wikibase;
- canonical mutations remain proposal/review/revision governed;
- backend receipts remain audit metadata, not domain authority;
- production mutation design must add reconciliation semantics for interrupted/ambiguous external effects;
- source/evidence semantics remain richer than Wikibase reference projections.

### Deferred production decisions

Separate ADRs or verification remain required for:

- production deployment topology;
- authentication/authorization;
- backups and disaster recovery;
- scaling/performance;
- public API hardening;
- upgrade lifecycle;
- monitoring/operability;
- mutation idempotency/reconciliation.

## Fallback

APR-004 remains `DEFERRED`, not rejected. If M1 or later evidence shows that Wikibase violates a critical project invariant or creates disproportionate operational complexity, the project may activate the PostgreSQL fallback while retaining the same domain contracts.
