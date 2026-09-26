# Architecture Pattern Register

## Purpose and authority

This register is the project's durable architectural-learning record. It separates what has been observed, what the project has adopted, what is implemented, what is verified, and what is merely a future candidate.

The register **does not create product scope by itself**. Current work remains authorized by project planning artifacts such as `docs/ROADMAP.md` and explicit project-owner decisions.

## Project boundary

Saudi Defense Atlas is a bilingual, source-backed knowledge platform for publicly available strategic, historical, organizational, industrial, procurement, training, and equipment information about Saudi defense.

It is not a real-time operational-intelligence or force-tracking product.

## Canonical truth objects

The project recognizes these domain/governance truth objects:

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

Wikibase is the accepted M1 knowledge-core implementation, but these objects remain project-native semantics rather than Wikibase-native authority.

## Authority owners

| Concern | Current authority |
|---|---|
| Product scope | Project owner + accepted project roadmap |
| Domain semantics | Accepted architecture/ontology decisions |
| Canonical mutation | `ChangeProposal -> ReviewDecision -> Revision`; adapter executes only an exactly authorized proposal |
| AI output | Proposal authority only unless a field is explicitly GREEN in policy |
| Publication of AMBER facts | Human editorial approval |
| Restricted operational detail | Exclusion/restriction policy; no autonomous publication |
| Architecture promotion | Explicit ADR/register decision tied to project authority |
| Backend identity/effect receipts | Implementation metadata only; never canonical domain authority |

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
13. **Authorization ≠ Effect ≠ Revision Evidence** — an approved proposal authorizes a backend attempt; backend receipts describe observed effects; the project Revision records the result.

## Claim ceiling

A successful technical test establishes only the property tested in the tested environment. In particular:

- the verified Wikibase M0 spike establishes representational/query/API suitability for the knowledge-core role; it does not establish production readiness;
- successful structured extraction does not establish factual correctness without evidence verification;
- a source-class label does not prove a particular claim;
- a successful write does not by itself prove governance requirements were satisfied;
- successful M0 mutation gating does not prove exactly-once behavior or ambiguous-effect recovery;
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
| APR-001 | Claim/evidence canonical knowledge model | ACCEPTED | VERIFIED | current-plan-authorized |
| APR-002 | Review-gated canonical mutation | ACCEPTED | VERIFIED | current-plan-authorized |
| APR-003 | Wikibase as knowledge-core implementation | ACCEPTED | VERIFIED | current-plan-authorized |
| APR-004 | PostgreSQL claim/evidence knowledge core | DEFERRED | NOT-LINKED | future-plan-candidate |
| APR-005 | Typed structured AI proposals | ACCEPTED | LINKED | current-plan-authorized |
| APR-006 | Deterministic-before-generative processing | ACCEPTED | LINKED | current-plan-authorized |
| APR-007 | Deterministic inline-SVG relationship visualization | ACCEPTED | VERIFIED | current-plan-authorized |

`VERIFIED` above is bounded to the documented contracts and evidence. It is not a production-qualification label.

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
- implementation_status: VERIFIED for M0 schema/representation mechanics
- planning_disposition: current-plan-authorized
- authority: ADR-0001 / ADR-0002 / foundation roadmap

**Implementation links:** `schemas/v0.1/`, `scripts/validate_schemas.py`, `tests/fixtures/schema-fixtures.json`, `spikes/wikibase/`.

**Verification evidence:** schema-validation run `36178033709`; Wikibase M0 run `36178040438`; artifact `10883261546`.

**Remaining verification:** production operational properties remain separately scoped.

---

## APR-002 — Review-gated canonical mutation

**Problem:** AI and ingestion adapters can generate plausible structured changes but must not become canonical authority.

**Invariant:** Candidate mutation and canonical mutation are separate states.

**Mechanism:** `ChangeProposal -> ReviewDecision -> backend effect -> Revision`, with GREEN automation explicitly policy-authorized and AMBER requiring human approval. The decision binds to the exact proposal payload hash.

**Failure modes:** direct model writes; hidden overwrites; ambiguous reviewer authority; rejected proposals becoming facts; stale decision applied to a modified proposal; ambiguous external effect blindly retried.

**Provenance:** project-native; `docs/AI_GOVERNANCE.md`, `docs/SOURCE_POLICY.md`, first-pass finding F-01, M0 adversarial findings.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: VERIFIED for the bounded mutation-governance/reconciliation contract tested through M1
- planning_disposition: current-plan-authorized
- authority: M0/M1 acceptance criteria and AI governance policy

**Implementation links:** `schemas/v0.1/change-proposal.schema.json`, `schemas/v0.1/review-decision.schema.json`, `schemas/v0.1/revision.schema.json`, `scripts/validate_workflow.py`, M1 mutation guard/reconciliation implementation.

**Verification evidence:** M0 workflow fixtures plus M1 guarded clean-stack convergence/replay and Revision construction tests.

**Claim ceiling:** verification remains bounded to the tested single-writer contract; production distributed concurrency and infrastructure qualification remain separate work.

---

## APR-003 — Wikibase as knowledge-core implementation

**Problem:** The project needs multilingual entities, referenced statements, qualifiers, revisions, and query/API support without building all knowledge infrastructure from scratch.

**Invariant:** The selected store preserves the project-native claim/evidence/revision semantics and does not own governance authority.

**Mechanism:** Wikibase + Action API + WDQS behind a project-owned adapter boundary.

**Benefits observed:** native multilingual entity model, qualifiers/references, revision history, query support, API write/read support, coexistence of conflicting claims.

**Liabilities retained:** operational complexity, separate production security/backup/upgrade requirements, projection of richer SDA evidence into Wikibase references, eventual-consistency behavior of WDQS.

**Failure modes to continue testing:** backend upgrade friction; query lag; adapter bypass; Q/P identity leakage; ambiguous external effects; excessive operational burden at production scale.

**Forcing function:** M1 requires a selected knowledge-core implementation.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: VERIFIED for the bounded M0/M1 knowledge-core contract
- planning_disposition: current-plan-authorized
- authority: `docs/adr/ADR-0002-knowledge-core.md`

**Implementation links:** `spikes/wikibase/`, M1 Wikibase adapters/read projection, `.github/workflows/wikibase-spike.yml`, `docs/adr/ADR-0002-knowledge-core.md`.

**Verification evidence:** M0 run `36178040438` plus continuing clean-stack M1/M2 regression runs.

**Claim ceiling:** suitable as the current canonical knowledge core. This does not establish production scaling, security, HA, backup/recovery, long-term upgrades, or distributed writer coordination.

---

## APR-004 — PostgreSQL claim/evidence knowledge core

**Problem:** The project requires a fallback if later evidence shows Wikibase imposes structural or operational friction that violates project invariants.

**Invariant:** The fallback preserves the same project-native domain semantics.

**Mechanism:** custom PostgreSQL schema, potentially with JSONB and relational claim/evidence tables.

**Decision:**

- pattern_status: DEFERRED
- implementation_status: NOT-LINKED
- planning_disposition: future-plan-candidate
- authority: ADR-0002 fallback clause

**Forcing function for promotion:** material Wikibase failure against a critical project invariant or unacceptable complexity demonstrated by later evidence.

---

## APR-005 — Typed structured AI proposals

**Problem:** Free-form model output is unsafe as a mutation interface.

**Invariant:** AI output that may affect canonical knowledge must cross a typed schema boundary before policy evaluation.

**Mechanism:** versioned JSON Schema/domain objects for candidate entities, claims, evidence, events, proposals, decisions, and revisions.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: LINKED
- planning_disposition: current-plan-authorized
- authority: AI governance policy + roadmap

**Implementation links:** `schemas/v0.1/`, `scripts/validate_schemas.py`, `tests/fixtures/schema-fixtures.json`.

**Verification status:** typed proposal boundaries are mechanically verified; actual generative-model extraction at scale remains later AI-operations work.

---

## APR-006 — Deterministic-before-generative processing

**Problem:** LLMs add cost and nondeterminism when exact parsing/identity rules are available.

**Invariant:** Deterministic mechanisms own exact transformations; generative models are used where semantic ambiguity warrants them.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: LINKED
- planning_disposition: current-plan-authorized
- authority: ADR-0001 design rules

**Implementation links:** deterministic ingestion/canonicalization, JSON Schema validators, proposal hashing, workflow policy validator, Wikibase adapter gating, public projections.

**Verification required:** later AI extraction must demonstrate that model output remains subordinate to these deterministic boundaries.

---

## APR-007 — Deterministic inline-SVG relationship visualization

**Problem:** M2 requires a first public relationship visualization, but current graphs are deliberately bounded and the project has not selected a frontend framework or general graph runtime.

**Invariant:** Visualization remains a projection over `RelationshipGraphView`; it cannot create new factual edges, change SDA identity, or detach material relationships from supporting Evidence.

**Mechanism:** server-rendered deterministic inline SVG plus semantic HTML fallback, with localized labels and graph-scoped accessibility IDs.

**Alternatives characterized:** Cytoscape.js and D3. Both remain future candidates if interaction/scale forcing functions arise; neither is required for the bounded M2 slice.

**Benefits:** zero new runtime dependency; deterministic tests; native browser SVG/DOM; bilingual labels; accessible title/description and cited text fallback.

**Liabilities:** project-owned layout code; not intended for large/free-form interactive graph exploration.

**Failure modes:** visual edge exceeds canonical graph; citation removed in presentation; Q/P IDs leak; input order changes layout; global SVG IDs collide; bounded layout used beyond its readable scale.

**Forcing function:** `docs/ROADMAP.md` M2 requires a first relationship visualization.

**Decision:**

- pattern_status: ACCEPTED
- implementation_status: VERIFIED for the bounded M2 visualization contract
- planning_disposition: current-plan-authorized
- authority: `docs/adr/ADR-0003-first-relationship-visualization.md`

**Implementation links:** `services/presentation/relationship_visualization.py`, `services/presentation/relationship_web.py`, `scripts/validate_m2_relationship_visualization.py`.

**Verification evidence:** trial implementation/review head `b78564fa83bf128803205bc2a22ea88a8284ecb2`; schema-validation run `36260932930` (#395) PASS; Wikibase regression run `36260932947` (#124) PASS; `docs/reviews/M2_RELATIONSHIP_VISUALIZATION_FIRST_PASS.md`.

**Verified properties:** deterministic reorder behavior, supporting-Evidence guard, bilingual node/relation labels, canonical relation-code fallback, graph-scoped SVG accessibility IDs, cited semantic fallback, exact graph JSON API, bilingual routes, and backend-ID leakage rejection.

**Replacement forcing functions:** sustained large visible graphs, pan/zoom/drag requirements, compound nodes, frequent client-side relayout/filtering, browser-side graph analysis, or demonstrated layout-quality failure.

**Claim ceiling:** verification is bounded to the first M2 relationship visualization and does not select the final frontend stack or large-graph engine.
