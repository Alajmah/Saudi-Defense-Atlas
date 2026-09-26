# Roadmap

## M0 — Foundation and Knowledge-Core Spike — COMPLETE

### Goal

Prove that the domain model can represent bilingual, sourced, temporal, conflicting defense knowledge cleanly before building the public site.

### Delivered

- project vision and scope
- architecture baseline
- ontology v0.1
- source/claim admission policy
- AI governance policy
- Architecture Pattern Register
- implementation-neutral JSON Schemas
- proposal/review/revision governance validator
- reproducible Wikibase prototype
- bounded seed dataset
- machine read/write/query proof
- approved synthetic adapter-gate proof
- independent first-pass + adversarial review records
- ADR-0002 knowledge-core decision

### Seed Dataset

The M0 representation trial models a deliberately small but diverse set:

- Royal Saudi Air Force
- F-15 family
- F-15SA variant
- Boeing
- PAC-3 MSE procurement item
- one official procurement notification/approval event
- one publicly announced multinational exercise
- one clearly marked synthetic conflict fixture for storage mechanics only

### M0 Acceptance Results

M0 passed the bounded acceptance gate:

1. the same canonical entity can be found by Arabic, English, abbreviation, and alias — **PASS**;
2. a quantity claim can carry scope, date, source/reference, and confidence context — **PASS**;
3. two conflicting claims can coexist without destructive overwrite — **PASS using synthetic non-factual fixture**;
4. procurement approval/notification remains distinct from contract, delivery, and operational state — **PASS**;
5. source/document identifiers and evidence locators can be projected to claim references without replacing the richer SDA provenance model — **PASS**;
6. backend revisions are auditable while remaining distinct from project Revision authority — **PASS**;
7. an AI-style proposal can remain non-canonical until exact-payload review authorization permits a backend write — **PASS**;
8. RED/restricted proposal paths can be blocked by policy/workflow validation — **PASS**;
9. Action API and WDQS output are practical enough to continue toward a custom frontend — **PASS**.

### Evidence

- schema/governance workflow: run `36178033709` — success;
- Wikibase clean-run workflow: run `36178040438`, job `108213344752` — success;
- verification artifact: `10883261546` — `PASS`;
- architecture decision: `docs/adr/ADR-0002-knowledge-core.md` — Wikibase accepted for the bounded M1 knowledge-core role.

### M0 Decision

**Wikibase is adopted as the M1 canonical knowledge-core implementation behind project-owned domain and mutation-governance contracts.**

PostgreSQL remains a deferred fallback. M0 does not qualify production security, HA, backup/recovery, scale, upgrades, observability, exactly-once mutation, or ambiguous-effect reconciliation.

---

## M1 — First Vertical Slice — COMPLETE

### Goal

Deliver one end-to-end path from an authoritative public source to a cited bilingual public equipment page, using the accepted Wikibase core without allowing the backend or AI to bypass SDA authority semantics.

### Pipeline

```text
approved source
  ↓
discovery
  ↓
fetch / parse
  ↓
Document + Evidence
  ↓
structured extraction
  ↓
entity resolution
  ↓
ChangeProposal
  ↓
claim comparison + policy validation
  ↓
human review when required
  ↓
backend mutation
  ↓
canonical Revision + backend receipt
  ↓
read API / projection
  ↓
Arabic + English public page
```

### Delivered

#### Ingestion and provenance

- allowlisted deterministic acquisition for the authoritative F-15SA source slice
- raw retrieval receipts separated from canonical Document identity
- canonical article-body hashing and unchanged-content idempotency
- Source / Document / Evidence projection with bounded evidence locators
- source/feed attribution on retrieval receipts for later monitoring-health reporting

#### Governance and canonical mutation

- typed candidate Claim/Event proposals
- explicit pre-resolved SDA identity boundary
- AMBER human-review binding to exact proposal hash
- backend-independent preflight/apply/reconcile contract
- no blind retry after ambiguous external effects
- explicit `already_applied`, `applied`, `failed`, `effect_unknown`, and `not_attempted` accounting
- project Revision construction only after demonstrable convergence
- pure replay cannot manufacture a second canonical Revision
- single-writer scope remains explicit; concurrent-writer coordination is not implied

#### Wikibase projection/readback

- project-owned write/read adapters
- Source, Document, Evidence, Claim, Event, and Entity read-projection markers
- Action-API-based reconciliation rather than WDQS lag-sensitive recovery
- projection completeness/version checks
- SDA IDs remain public/canonical identity; Q/P IDs remain backend mappings

#### Public slice

- backend-neutral `EquipmentView`
- JSON read API by SDA ID
- Arabic and English F-15SA public pages from the same canonical records
- visible citations and delivery timeline
- explicit unknowns for unsupported operator/inventory/service-state fields
- no legacy M0 trial statement leakage

### M1 Acceptance Result

The demonstrated vertical slice passed the bounded acceptance contract for deterministic acquisition, evidence traceability, review-gated canonical mutation, reconciliation/replay, Wikibase readback, and bilingual public projection.

M1 remains explicitly **single-writer**. Production distributed/concurrent mutation coordination, production Wikibase qualification, and generalized AI extraction at scale remain later work.

---

## M2 — Procurement and Exercise Graph — COMPLETE

### Goal

Extend the verified knowledge/read model from one equipment page into bounded procurement/exercise relationships, temporal views, staleness signals, and a first public relationship visualization without creating a second truth store.

### Delivered

- bounded backend-neutral `RelationshipGraphView` for procurement and exercise domains
- explicit Claim/Event edges only; no inferred topology
- root-bounded event admission preventing unrelated high-degree-entity leakage
- direct Evidence -> Document -> Source citations on material graph edges/events/timeline entries
- event intervals including `ended_at`
- typed `ProcurementProgramView` and `ExerciseView`
- procurement lifecycle represented as history rather than an inferred current state
- typed procurement quantity/lifecycle facts with explicit disputes preserved
- policy-driven Claim staleness with exact `review_due_at`, UTC normalization, and `fresh` / `due` / `unverified`
- registered-feed acquisition freshness based on successful RetrievalReceipts rather than Document creation
- independent freshness per `source_id + document_key`, including `never_retrieved`
- deterministic first relationship visualization using inline SVG + semantic cited HTML fallback
- bilingual node/relation labels while retaining canonical relationship codes for auditability
- relationship JSON API plus Arabic/English relationship pages
- APR-007 / ADR-0003 bounded visualization decision and verification

### M2 Acceptance Boundaries

- relationship/public views remain projections over canonical SDA records;
- staleness/freshness signals are review/monitoring status, not truth/falsity judgments;
- no Q/P/backend identity leakage is accepted in public contracts;
- no frontend framework, graph runtime, search engine, scheduler, or production deployment topology is silently selected;
- deterministic inline SVG is verified only for the bounded M2 role; larger interactive graphs require a new APR forcing function;
- no live operational geography, movement, readiness, patrol, or stock semantics are introduced.

### Verification

The final visualization trial passed on implementation/review head `b78564fa83bf128803205bc2a22ea88a8284ecb2`:

- schema-validation run `36260932930` (#395) — **PASS**;
- Wikibase regression run `36260932947` (#124) — **PASS**;
- exhaustive first-pass: `docs/reviews/M2_RELATIONSHIP_VISUALIZATION_FIRST_PASS.md`;
- architecture decision: `docs/adr/ADR-0003-first-relationship-visualization.md`.

Earlier M2 increments were independently reviewed and merged through PRs #4–#7 before the visualization closure.

---

## M3 — Atlas and Search — NEXT

Planned outcomes:

- Arabic-aware full-text search
- semantic/entity search
- public non-operational map
- filters by service, equipment class, manufacturer, country, and status
- timeline navigation

Architecture choices that require separate APR evidence before adoption include the search engine/index, map/rendering mechanism, frontend framework if one is introduced, and deployment topology.

---

## M4 — AI Editorial Operations

Planned outcomes:

- multi-source monitoring
- automated relevance classification
- claim extraction at scale
- contradiction detection
- stale-record auditor
- bilingual drafting
- daily editorial brief
- model/prompt observability and evaluation dashboards

---

## M5 — Research Assistant

Planned outcomes:

- grounded Q&A over approved knowledge and evidence
- citations on every substantive answer
- temporal queries
- graph-aware retrieval
- explicit uncertainty and source-conflict presentation

The assistant must answer from approved data/evidence rather than treat web search or model memory as canonical truth.

## Immediate Next Sequence

After M2 closure:

1. start a dedicated M3 branch from verified `main`;
2. define the search/query contract before selecting a search engine;
3. characterize Arabic full-text/entity search requirements and evaluate candidate mechanisms through APR evidence;
4. define the public non-operational map data contract and sensitivity boundary before selecting a map library/provider;
5. expose timeline/filter navigation from existing canonical/public projections;
6. keep all M3 indexes/maps downstream of SDA canonical IDs and Claim/Event/Evidence authority;
7. run the same exhaustive first-pass review and exact-head CI gates for each promoted mechanism.
