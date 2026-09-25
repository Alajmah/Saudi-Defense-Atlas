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

## M1 — First Vertical Slice — NEXT

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

### Deliverables

#### Ingestion

- source registry
- fetcher for at least one authoritative source
- parser for HTML and one PDF/document path
- content hashing and duplicate detection
- immutable retrieval metadata

#### Intelligence

- typed extraction schemas used by a real extraction path
- entity resolver
- candidate claim comparison
- confidence and review routing
- provenance capture
- explicit unknown/ambiguous result handling

#### Editorial

- queue of proposed changes
- approve / reject / return-for-revision workflow
- visible evidence and current-vs-proposed diff
- immutable decision binding to exact proposal payload

#### Knowledge

- project-owned Wikibase adapter
- canonical entity retrieval by SDA ID
- claim/evidence projection retrieval
- revision history
- bilingual labels and aliases
- mutation idempotency/reconciliation contract

#### Public

- minimal web application shell
- one equipment page
- claim-level/section-level citations
- related entities
- timeline snippet
- Arabic/English switching from the same canonical entity

### M1 Acceptance Criteria

1. Re-ingesting the same unchanged document is idempotent.
2. A changed source produces a reviewable delta rather than duplicate entities/claims.
3. Every public material fact resolves to approved evidence.
4. Arabic and English pages render from the same canonical entity/claim IDs.
5. The public page does not require manually copying facts into an independent CMS truth store.
6. Ambiguous entity resolution is routed to review rather than guessed.
7. A conflicting claim is surfaced, not silently overwritten.
8. No AI free-form output can directly mutate canonical data.
9. A review decision cannot authorize a payload different from the exact proposal it reviewed.
10. Mutation retries use an idempotency/reconciliation mechanism; an ambiguous external effect is not blindly repeated or collapsed into success/failure.
11. Source, Document, Evidence, Claim, Decision, Revision, and backend receipt can be traced end-to-end for the demonstrated page.
12. Restricted operational detail remains excluded even if discovered in source material.

### M1 Architecture Work That Requires Separate Evidence

The following may be researched or prototyped, but adoption must follow the APR process rather than this roadmap silently selecting them:

- public frontend framework and deployment topology;
- ingestion orchestration technology;
- document/PDF parser;
- model/provider/runtime;
- search engine;
- editorial UI/CMS.

Wikibase is the only major implementation mechanism promoted by M0 for the knowledge-core role.

---

## M2 — Procurement and Exercise Graph

Planned outcomes:

- procurement-program lifecycle views
- contract/event timeline
- exercise entities and participation
- company/manufacturer graph
- first relationship visualization
- source staleness checks

---

## M3 — Atlas and Search

Planned outcomes:

- Arabic-aware full-text search
- semantic/entity search
- public non-operational map
- filters by service, equipment class, manufacturer, country, and status
- timeline navigation

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

After merging the M0/foundation PR:

1. create a dedicated M1 branch;
2. select one authoritative source + one equipment entity for the vertical slice;
3. define the M1 source registry/Document/Evidence ingestion contract;
4. define idempotency and ambiguous-effect reconciliation before generalizing backend writes;
5. implement deterministic fetch/hash/parse first;
6. add typed extraction as a proposal-producing boundary;
7. implement the minimal project-owned read/write adapter around Wikibase;
8. implement one bilingual public page from canonical data;
9. run the same exhaustive-first/adversarial review process against the vertical slice.
