# ADR-0002 — Canonical Knowledge-Core Implementation

**Status:** Pending Evidence

**Decision date:** Not set

**Pattern:** APR-003 (Wikibase trial) / APR-004 (PostgreSQL fallback)

## Context

ADR-0001 defines an implementation-neutral knowledge model and explicitly prevents the backing store from becoming the project's authority model. M0 must now determine whether Wikibase can represent and expose those semantics cleanly enough to adopt for the canonical knowledge-core role.

The decision is intentionally narrower than production deployment. A successful M0 does not establish production security, high availability, backup/recovery, scale, or hosting topology.

## Candidate A — Wikibase

Trial implementation: `spikes/wikibase/`

Current architecture status:

- pattern_status: `TRIAL-AUTHORIZED`
- implementation_status: `LINKED`
- planning_disposition: `current-plan-authorized`

## Candidate B — PostgreSQL claim/evidence store

Current architecture status:

- pattern_status: `DEFERRED`
- implementation_status: `NOT-LINKED`
- planning_disposition: `future-plan-candidate`

It becomes active only if the Wikibase trial fails a critical M0 criterion or demonstrates unacceptable semantic/operational complexity.

## M0 Acceptance Matrix

| Criterion | Required evidence | Result |
|---|---|---|
| Arabic + English labels | same item exposes both labels | PENDING |
| aliases | `RSAF` resolves to the RSAF item | PENDING |
| domain/store identity separation | `SDA-ORG-RSAF` maps to, but is not equal to, its Q-ID | PENDING |
| typed relationships | item-valued statement exists | PENDING |
| qualifiers | claim ID, quantity type, time, confidence retained | PENDING |
| multiple references | one claim has at least two references | PENDING |
| conflicting claims | synthetic 10/12 quantities coexist | PENDING |
| temporal semantics | day-qualified statements round-trip | PENDING |
| procurement-stage semantics | possible-FMS notification remains approval/notification, not contract/delivery | PENDING |
| revision history | multiple backend revisions visible | PENDING |
| machine read/write API | Action API seed/read succeeds | PENDING |
| query support | WDQS resolves item by SDA canonical ID | PENDING |
| review-before-admission | proposal/review/revision tests pass | PENDING |
| backend remains subordinate to governance | mapping keeps proposals/decisions/revisions outside Wikibase authority | PENDING |

## Evidence Sources

Expected evidence:

- `schema-validation` GitHub Actions workflow
- `wikibase-m0-spike` GitHub Actions workflow
- generated `state.generated.json` artifact
- generated `verification.generated.json` artifact
- implementation review findings

Do not change this ADR to Accepted or Rejected until the relevant evidence is actually observed.

## Decision Rule

### Accept Wikibase if

All critical representational/governance criteria pass and the adapter does not require material distortion of the project ontology.

### Reject Wikibase if

Any critical criterion cannot be represented cleanly, the authority boundary must be bypassed, or the adapter complexity is disproportionate to the reuse benefit.

### Defer if

The trial is technically inconclusive (for example infrastructure/environment failure unrelated to semantics). Infrastructure failure is not evidence that the data model is unsuitable.

## Consequences if accepted

Only the canonical knowledge-core role is accepted. Separate ADRs/verification remain required for:

- production deployment topology
- authentication/authorization
- backups and disaster recovery
- scaling/performance
- public API hardening
- upgrade lifecycle
- monitoring/operability

## Consequences if rejected

Activate APR-004 and implement the same domain contracts over PostgreSQL. Do not redesign the ontology merely to match a preferred datastore.

## Decision

**PENDING.** No knowledge-core technology is adopted by this ADR yet.