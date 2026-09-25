# Roadmap

## M0 — Foundation and Knowledge-Core Spike

### Goal

Prove that the domain model can represent bilingual, sourced, temporal, conflicting defense knowledge cleanly before building the public site.

### Deliverables

- project vision and scope
- architecture baseline
- ontology v0.1
- source/claim admission policy
- AI governance policy
- knowledge-core prototype
- seed dataset
- minimal read/write API proof

### Seed Dataset

Model a deliberately small but diverse set:

- Royal Saudi Air Force
- F-15 family
- F-15SA variant
- Boeing
- one air-defense procurement item such as PAC-3 MSE
- one official procurement event
- one publicly announced multinational exercise

### Wikibase Spike

Prototype the seed dataset in Wikibase and validate:

- Arabic/English labels
- aliases
- stable IDs
- typed statements
- qualifiers
- multiple references
- conflicting claims
- temporal qualifiers
- revision history
- machine read/write
- query ergonomics
- AI-proposed changes that can be reviewed before admission

### M0 Acceptance Criteria

M0 passes only if:

1. the same canonical entity can be found by Arabic, English, abbreviation, and common alias;
2. a quantity claim can carry scope, date, source, and confidence context;
3. two credible conflicting quantities can coexist without destructive overwrite;
4. procurement approval, contract, delivery, and operational state remain distinct;
5. a source document can be traced to every admitted claim it supports;
6. revisions are auditable;
7. an AI extraction can be represented as a proposal before it becomes canonical;
8. restricted operational detail can be blocked by policy;
9. API/query output is practical enough to power a custom frontend.

### M0 Decision

At the end of the spike:

- **Adopt Wikibase** if all critical criteria pass cleanly.
- **Adopt PostgreSQL claim/evidence core** if Wikibase requires structural workarounds or makes controlled AI/editorial workflows unnecessarily difficult.
- A hybrid remains possible, but only if responsibilities are explicit.

---

## M1 — First Vertical Slice

### Goal

Deliver one end-to-end path from authoritative public source to a cited bilingual public equipment page.

### Pipeline

```text
approved source
  ↓
discovery
  ↓
fetch / parse
  ↓
structured extraction
  ↓
entity resolution
  ↓
claim comparison
  ↓
evidence + policy validation
  ↓
human review when required
  ↓
canonical knowledge revision
  ↓
search/API index
  ↓
Arabic + English public page
```

### Deliverables

#### Ingestion

- source registry
- fetcher for at least one official structured source
- parser for HTML and one PDF/document path
- content hashing and duplicate detection

#### Intelligence

- typed extraction schemas
- entity resolver
- candidate claim comparison
- confidence and review routing
- provenance capture

#### Editorial

- queue of proposed changes
- approve / reject / edit workflow
- visible evidence and current-vs-proposed diff

#### Knowledge

- canonical entity retrieval
- claim/evidence retrieval
- revision history
- bilingual labels and aliases

#### Public

- minimal Next.js shell
- one equipment page
- citations
- related entities
- timeline snippet
- Arabic/English switching

### M1 Acceptance Criteria

1. Re-ingesting the same document is idempotent.
2. A changed source produces a reviewable delta rather than duplicates.
3. Every public material fact resolves to evidence.
4. Arabic and English pages render from the same canonical entity.
5. The public page does not require manually copying facts into a CMS article.
6. An ambiguous entity resolution is routed to review.
7. A conflicting claim is surfaced, not silently overwritten.
8. No AI free-form output can directly mutate canonical data.

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

## Near-Term Backlog

After merging the foundation branch, the next engineering sequence should be:

1. create `schemas/` for implementation-neutral domain objects;
2. create a reproducible Wikibase local spike;
3. encode the seven seed entities;
4. test qualifiers/references/conflicts via API;
5. document findings in ADR-0002;
6. make the knowledge-core decision;
7. only then scaffold ingestion and the first public page.
