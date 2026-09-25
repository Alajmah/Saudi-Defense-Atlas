# Architecture Pattern Register

## Purpose and authority

This register is the project's durable architectural-learning record. It separates what has been observed, what the project has adopted, what is implemented, what is verified, and what is merely a future candidate.

The register **does not create product scope by itself**. Current work remains authorized by project planning artifacts such as `docs/ROADMAP.md` and explicit project-owner decisions.

## Project boundary

Saudi Defense Atlas is a bilingual, source-backed knowledge platform for publicly available strategic, historical, organizational, industrial, procurement, training, and equipment information about Saudi defense.

It is not a real-time operational-intelligence or force-tracking product.

## Canonical truth objects

The project currently recognizes these domain truth objects:

- Entity
- Claim
- Evidence
- Source
- Document
- Event
- Relationship
- ChangeProposal
- ReviewDecision
- Revision

The exact storage mechanism remains unresolved until M0 completes.

## Authority owners

| Concern | Current authority |
|---|---|
| Product scope | Project owner + accepted project roadmap |
| Domain semantics | Accepted architecture/ontology decisions |
| Canonical mutation | `ChangeProposal -> ReviewDecision -> Revision` contract; concrete implementation pending M0 |
| AI output | Proposal authority only unless a field is explicitly GREEN in policy |
| Publication of AMBER facts | Human editorial approval |
| Restricted operational detail | Exclusion/restriction policy; no autonomous publication |
| Architecture promotion | Explicit ADR/register decision tied to project authority |

## Constitutional invariants

1. **Canonical Knowledge > Prose** — articles and summaries are projections over approved knowledge.
2. **Evidence ≠ Claim** — evidence bears on a claim; it is not itself the canonical assertion.
3. **Discovery ≠ Authority** — a source or model may reveal a lead without establishing truth.
4. **Proposal ≠ Canonical Revision** — candidate changes cannot become canonical merely because a model or adapter can write them.
5. **Observation ≠ Adoption** — learning that a mechanism exists does not adopt it.
6. **Adoption ≠ Implementation** — accepted architecture may remain unimplemented.
7. **Implementation ≠ Verification** — running code is not proof that the intended contract holds.
8. **Newer ≠ Truer** — time ordering alone does not resolve conflicting evidence.
9. **Unknown ≠ Precision** — missing values remain unknown; the system must not manufacture exactness.
10. **Public Availability ≠ Operational Suitability** — publicly accessible material may still be excluded when aggregation materially increases operational risk.
11. **Store Identity ≠ Domain Identity** — backend-native IDs must not silently define public/canonical identity.
12. **Procurement Approval ≠ Contract ≠ Delivery ≠ Operational Service** — these remain distinct facts/events.

## Claim ceiling

A successful technical test establishes only the property tested in the tested environment. In particular:

- a Wikibase spike can demonstrate representational/API suitability; it does not by itself establish production readiness;
- successful structured extraction does not establish factual correctness without evidence verification;
- a source-class label does not prove a particular claim;
- a successful write does not prove that governance requirements were satisfied;
- public-source discovery does not justify operational inference beyond the source and publication policy.

## Status vocabulary

### Pattern status

`OBSERVED | CHARACTERIZED | CANDIDATE | ACCEPTED | TRIAL-AUTHORIZED | DEFERRED | REJECTED | SUPERSEDED`

### Implementation status

`NOT-LINKED | LINKED | IN-TRIAL | IMPLEMENTED | VERIFIED | ROLLED-BACK`

### Planning disposition

`current-plan-authorized | future-plan-candidate | research-only | do-not-promote`

## Pattern index

| ID | Pattern | Pattern status | Implementation | Planning |
|---|---|---|---|---|
| APR-001 | Claim/evidence canonical knowledge model | ACCEPTED | NOT-LINKED | current-plan-authorized |
| APR-002 | Review-gated canonical mutation | ACCEPTED | NOT-LINKED | current-plan-authorized |
| APR-003 | Wikibase as knowledge-core implementation | TRIAL-AUTHORIZED | NOT-LINKED | current-plan-authorized |
| APR-004 | PostgreSQL claim/evidence knowledge core | DEFERRED | NOT-LINKED | future-plan-candidate |
| APR-005 | Typed structured AI proposals | ACCEPTED | NOT-LINKED | current-plan-authorized |
| APR-006 | Deterministic-before-generative processing | ACCEPTED | NOT-LINKED | current-plan-authorized |

---

## APR-001 — Claim/evidence canonical knowledge model

**Problem:** Defense facts are temporal, sourced, sometimes conflicting, and cannot safely live as unversioned prose fields.

**Invariant:** Material factual knowledge must preserve claim identity, evidence provenance, temporal context, and revision history.

**Mechanism:** Implementation-neutral `Entity + Claim + Evidence + Event + Revision` model.

**Benefits:** provenance, contradiction preservation, temporal queries, reusable public views.

**Liabilities:** more editorial/data-model complexity than a conventional CMS.

**Failure modes:** orphan claims; evidence attached at article rather than claim level; destructive overwrite; backend IDs leaking into domain semantics.

**Provenance:** project-native; `docs/ARCHITECTURE.md`, `docs/ONTOLOGY.md`, `docs/SOURCE_POLICY.md`.

**Forcing function:** the product must answer sourced temporal questions and preserve credible disagreement.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: NOT-LINKED
- planning_disposition: current-plan-authorized
- authority: ADR-0001 / foundation roadmap

**Verification required:** M0 schemas and knowledge-core spike; M1 source-to-page vertical slice.

---

## APR-002 — Review-gated canonical mutation

**Problem:** AI and ingestion adapters can generate plausible structured changes but must not become canonical authority.

**Invariant:** Candidate mutation and canonical mutation are separate states.

**Mechanism:** `ChangeProposal -> ReviewDecision -> Revision`, with GREEN automation explicitly policy-authorized and AMBER requiring human approval.

**Failure modes:** direct model writes; hidden overwrites; ambiguous reviewer authority; rejected proposals becoming facts.

**Provenance:** project-native; `docs/AI_GOVERNANCE.md`, `docs/SOURCE_POLICY.md`, first-pass finding F-01.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: NOT-LINKED
- planning_disposition: current-plan-authorized
- authority: M0 acceptance criterion 7 and AI governance policy

**Verification required:** demonstrate a proposed write that remains non-canonical until a valid review decision creates an auditable revision.

---

## APR-003 — Wikibase as knowledge-core implementation

**Problem:** The project needs multilingual entities, referenced statements, qualifiers, revisions, and query/API support without building all knowledge infrastructure from scratch.

**Invariant:** Any selected store must preserve the project-native claim/evidence/revision semantics and must not own governance authority.

**Mechanism under trial:** Wikibase Suite and its APIs/query service.

**Benefits hypothesized:** mature multilingual entity model, qualifiers/references, revision history, query ecosystem.

**Liabilities to test:** store-native IDs, statement model ergonomics, proposal workflow integration, operational complexity, query/API suitability, custom confidence/evidence semantics.

**Failure modes:** forcing project ontology into awkward store constraints; bypassing proposal/review boundary; excessive adapter complexity; treating a representational demo as production qualification.

**Forcing function:** M0 must choose a knowledge-core implementation before M1.

**Decision:**

- pattern_status: TRIAL-AUTHORIZED
- implementation_status: NOT-LINKED
- planning_disposition: current-plan-authorized
- authority: `docs/ROADMAP.md` M0 Wikibase Spike

**Claim ceiling:** successful M0 can justify architectural adoption for the canonical knowledge role; it does not establish production scaling, HA, backup, or operational readiness.

---

## APR-004 — PostgreSQL claim/evidence knowledge core

**Problem:** The project requires a fallback if Wikibase imposes structural or workflow friction.

**Invariant:** The fallback must preserve the same project-native domain semantics.

**Mechanism:** custom PostgreSQL schema, potentially with JSONB and relational claim/evidence tables.

**Decision:**

- pattern_status: DEFERRED
- implementation_status: NOT-LINKED
- planning_disposition: future-plan-candidate
- authority: `docs/ARCHITECTURE.md` fallback decision gate

**Forcing function for promotion:** material Wikibase failure against a critical M0 acceptance criterion or unacceptable complexity demonstrated by the spike.

---

## APR-005 — Typed structured AI proposals

**Problem:** Free-form model output is unsafe as a mutation interface.

**Invariant:** AI output that may affect canonical knowledge must cross a typed schema boundary before policy evaluation.

**Mechanism:** versioned JSON Schema/domain objects for candidate entities, claims, evidence, events, proposals, decisions, and revisions.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: NOT-LINKED
- planning_disposition: current-plan-authorized
- authority: AI governance policy + M0/M1 roadmap

**Verification required:** schema rejects malformed/unsupported candidate objects and permits explicit unknowns.

---

## APR-006 — Deterministic-before-generative processing

**Problem:** LLMs add cost and nondeterminism when exact parsing/identity rules are available.

**Invariant:** Deterministic mechanisms should own exact transformations; generative models should be used where semantic ambiguity warrants them.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: NOT-LINKED
- planning_disposition: current-plan-authorized
- authority: ADR-0001 design rules

**Verification required:** M1 pipeline demonstrates deterministic hashing/deduplication and typed validation around any model extraction.