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

## M3 — Atlas and Search — COMPLETE

### Goal

Add public discovery/navigation over approved SDA projections without allowing search indexes, map runtimes, or navigation views to become new truth stores or broaden the operational-sensitivity boundary.

### Delivered

#### Search

- engine-neutral `SearchDocument`, `SearchQuery`, and `SearchResult` contracts
- conservative Arabic orthographic normalization with no hidden stemming, transliteration generation, fuzzy expansion, or semantic/vector inference
- deterministic lexical reference oracle with portable match-quality classes
- service, equipment-class, manufacturer, country, status, and entity-type facets
- OpenSearch 3.8.0 accepted and verified as a downstream lexical index only
- fixed portable quality tiers and locale-aware deterministic tie-breaking
- SDA IDs remain canonical/public identity; engine `_score` and backend Q/P IDs never become public semantics

#### Public map

- backend-neutral `PublicMapView` for allowlisted fixed public facilities only
- high/verified coordinate Claims with direct supporting Evidence
- exactly one eligible latitude/longitude pair and explicit fail-closed conflict handling
- coordinates coarsened to two decimals before entering the public projection
- no Event/movement input and no operationally sensitive facility categories
- deterministic `PublicMapView -> GeoJSON` renderer adapter
- MapLibre GL JS 6.11.2 accepted and verified for the bounded browser-renderer role
- provider-free browser verification with zero external requests
- tile/basemap provider and geocoder remain deliberately unselected

#### Navigation

- public filter catalog derived only from accepted `SearchDocument.facets`
- bilingual resolution for entity-backed service/manufacturer/country filter values
- deterministic public counts over indexed SearchDocuments
- timeline navigation derived only from `RelationshipGraphView.timeline`
- supporting/contradicting/contextual Evidence retained with timeline events
- root/domain context preserved when duplicate Event IDs are merged
- unknown temporal precision remains explicit and sorts after known dates
- no inferred lifecycle/current-state conclusion from event ordering

### M3 Architecture Decisions

- ADR-0004 / APR-008 — OpenSearch accepted and verified for the bounded lexical-index role
- ADR-0005 / APR-009 — MapLibre GL JS accepted and verified for the bounded `PublicMapView` browser-renderer role
- semantic/vector retrieval remains outside the M3 capability ceiling and is deferred to the research-assistant milestone where it can be evaluated with grounded retrieval/citation requirements
- no frontend framework, tile provider, geocoder, or production deployment topology is selected by M3

### M3 Acceptance Boundaries

- indexes, navigation views, and map payloads remain disposable projections downstream of SDA canonical Entity/Claim/Event/Evidence authority;
- no search/map component may mint canonical facts or identities;
- no raw/canonical precise geography is exposed to the browser renderer;
- live unit positions, movements, deployment timing, patrol patterns, readiness, stocks, tactical air-defense/radar/command-post geography, and unofficial precise operational coordinates remain excluded;
- OpenSearch and MapLibre verification is bounded to tested contracts and does not constitute production security/HA/scale qualification;
- semantic/vector retrieval, final frontend selection, tile-provider selection, geocoding, and deployment topology require later forcing functions and separate evidence.

### Verification

M3 was delivered through the reviewed increments merged in PRs #10, #12, #13, #14, #15, and #16. The final navigation increment passed exact-head gates on `180932049e8051b7014b62d3cc1b1c3e60a211a3`:

- schema-validation run `36335528979` (#541) — **PASS**;
- Wikibase regression run `36335528977` (#167) — **PASS**;
- first-pass review: `docs/reviews/M3_NAVIGATION_FIRST_PASS.md`.

The OpenSearch and MapLibre adoption evidence remains recorded in ADR-0004/ADR-0005 and APR-008/APR-009.

---

## M4 — AI Editorial Operations — NEXT

### Goal

Scale the proven deterministic/source-backed pipeline into an AI-assisted editorial operating system without allowing models to bypass evidence, review, sensitivity, or canonical-mutation authority.

Planned outcomes:

- multi-source monitoring
- automated relevance classification
- claim extraction at scale
- contradiction detection
- stale-record auditor
- bilingual drafting
- daily editorial brief
- model/prompt observability and evaluation dashboards

M4 must preserve the existing proposal/review/revision boundary. Model output remains candidate/proposal data until policy and review authorize canonical effects.

---

## M5 — Research Assistant

Planned outcomes:

- grounded Q&A over approved knowledge and evidence
- citations on every substantive answer
- temporal queries
- graph-aware retrieval
- explicit uncertainty and source-conflict presentation
- semantic/vector retrieval only after an explicit evaluation proves it improves grounded research without bypassing canonical evidence or citation constraints

The assistant must answer from approved data/evidence rather than treat web search or model memory as canonical truth.

## Immediate Next Sequence

After M3 closure:

1. define the M4 source-monitoring and editorial-queue contracts before selecting a scheduler/orchestrator;
2. define a typed AI extraction boundary that emits candidate Entity/Claim/Event/Evidence records only;
3. build deterministic relevance/deduplication/source-routing before invoking generative models;
4. add model/prompt/version/evaluation metadata to every AI-produced proposal artifact;
5. keep AMBER/RED review and operational-sensitivity gates intact;
6. resolve the outstanding concurrent-writer coordination requirement before enabling multiple automated canonical mutation workers;
7. prove one multi-source editorial vertical slice through discovery -> extraction -> verification -> review -> canonical Revision -> public projection;
8. run exhaustive first-pass and exact-head CI gates before promoting any orchestration or model-dependent mechanism.
