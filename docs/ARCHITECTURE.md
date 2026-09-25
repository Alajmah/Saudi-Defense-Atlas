# Architecture Baseline

## ADR-0001 — Knowledge-first architecture

**Status:** Accepted for foundation; implementation components remain provisional until M0 validation.

## Decision

Saudi Defense Atlas will treat structured knowledge as the primary product. Articles, search results, timelines, maps, and AI answers are projections over a canonical knowledge model rather than independent stores of facts.

The canonical domain model is:

```text
Entity
Claim
Evidence
Source
Event
Relationship
Revision
```

The model must remain implementation-neutral so the project can evaluate Wikibase, a custom PostgreSQL model, or a hybrid implementation without changing domain semantics.

## System Boundaries

```text
┌─────────────────────────────────────────────┐
│                 SOURCES                     │
│ official / manufacturer / specialist / OSINT│
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│              INGESTION PLANE                │
│ discovery · fetch · parse · normalize       │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│            INTELLIGENCE PLANE               │
│ classify · extract · resolve · verify        │
│ deduplicate · compare · detect conflicts     │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│             GOVERNANCE GATE                 │
│ policy · confidence · review · approval      │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│              KNOWLEDGE CORE                 │
│ entities · claims · evidence · revisions     │
└───────────────┬───────────────┬─────────────┘
                │               │
        ┌───────▼──────┐ ┌──────▼────────┐
        │ Search / API │ │ Editorial CMS │
        └───────┬──────┘ └──────┬────────┘
                └────────┬───────┘
                         ▼
┌─────────────────────────────────────────────┐
│              EXPERIENCE PLANE               │
│ web · atlas · timeline · graph · AI research│
└─────────────────────────────────────────────┘
```

## Candidate Open-Source Components

These are candidates, not commitments until proven by a spike:

- Knowledge core: Wikibase Suite or PostgreSQL-based claim store
- Editorial CMS: Payload CMS
- Deterministic crawling: Scrapy
- AI-oriented crawling: Crawl4AI
- Browser automation: Playwright
- Article extraction: Trafilatura
- Document parsing: Docling
- AI structured extraction: PydanticAI
- Workflow orchestration: Prefect
- Relational/application data: PostgreSQL
- Vector similarity: pgvector
- Search: OpenSearch
- Maps: MapLibre GL JS
- Relationship visualization: Cytoscape.js
- AI observability: Langfuse
- Public frontend: Next.js

## Design Rules

### 1. Evidence before prose

An AI-generated article cannot create canonical truth by itself. Canonical claims are admitted through evidence and policy.

### 2. Preserve contradiction

If credible sources disagree, store the disagreement. Do not overwrite one value merely because a newer document exists.

### 3. Separate discovery from authority

Low-trust sources may trigger research but cannot automatically establish high-impact claims.

### 4. Deterministic before generative

Use parsers, schemas, rules, and exact identifiers where possible. Use LLMs for ambiguity, language understanding, extraction, reconciliation proposals, and drafting.

### 5. Idempotent ingestion

Reprocessing the same source must not create duplicate entities, claims, or events.

### 6. Full provenance

Every automated transformation should retain source URI, fetch timestamp, content fingerprint, parser/model version, and transformation trace where practical.

### 7. Human authority is risk-based

Routine high-confidence metadata may be automated. Material inventory, delivery, retirement, and conflict-resolution changes require stronger evidence and may require explicit review.

## M0 Knowledge-Core Decision Gate

Wikibase will be accepted only if a prototype demonstrates all of the following without awkward workarounds:

- Arabic and English canonical labels and aliases
- stable entity identifiers
- typed relationships
- claims with qualifiers
- multiple references per claim
- conflicting claims coexisting
- point-in-time and validity semantics
- revision history
- machine-friendly write/read API
- query support adequate for public views
- clean mapping to AI-proposed changes and human approval

If it fails materially, the fallback is a PostgreSQL claim/evidence schema retaining the same domain model.

## Deferred Decisions

The following are intentionally deferred until M0/M1:

- final knowledge-store technology
- graph database adoption
- production hosting topology
- queue technology
- model provider/runtime
- final CMS choice
- final search engine sizing/topology
