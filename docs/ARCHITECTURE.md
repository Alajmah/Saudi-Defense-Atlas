# Architecture Baseline

## ADR-0001 — Knowledge-first architecture

**Status:** Accepted for foundation; implementation components remain provisional until M0 validation.

## Decision

Saudi Defense Atlas will treat structured knowledge as the primary product. Articles, search results, timelines, maps, and AI answers are projections over a canonical knowledge model rather than independent stores of facts.

The canonical domain model is implementation-neutral:

```text
Entity
Claim
Evidence
Source
Document
Event
Relationship
ChangeProposal
ReviewDecision
Revision
```

The project may evaluate Wikibase, a custom PostgreSQL model, or a hybrid implementation without changing these domain semantics.

## Authority Model

The knowledge store is **not** the authority boundary. Ability to call a backend write API does not authorize a canonical change.

Canonical mutation follows the project-native contract:

```text
candidate extraction / human edit / deterministic process
                    ↓
              ChangeProposal
                    ↓
           schema + policy checks
                    ↓
             ReviewDecision
                    ↓
          canonical adapter write
                    ↓
                 Revision
```

- **GREEN** changes may receive a policy-authorized system approval only for fields explicitly permitted by policy.
- **AMBER** changes require human editorial approval.
- **RED** changes are blocked from canonical/public operational-feed mutation.
- Editing a proposal creates a new superseding proposal; the reviewed payload is not silently mutated.
- Backend write receipts are audit evidence, not proof that the policy decision was valid.

The project owner and accepted roadmap/ADRs define product and architecture authority. Concrete user/role authorization and persistence mechanics remain M0/M1 implementation work.

## Provenance Boundaries

The architecture separates three concepts that must not collapse into a URL:

```text
Source
  publisher / originating authority
       ↓
Document
  retrieved or versioned artifact + content fingerprint
       ↓
Evidence
  bounded locator/span/observation inside the artifact
       ↓
Claim / Event
```

This enables document versioning, claim-level citations, contradiction handling, and deterministic duplicate detection.

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
│ classify · extract · resolve · verify       │
│ deduplicate · compare · detect conflicts    │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│             GOVERNANCE GATE                 │
│ proposal · policy · review · decision       │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│              KNOWLEDGE CORE                 │
│ entities · claims · evidence · revisions    │
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

These are candidates, not commitments until proven and explicitly promoted through project architecture governance:

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

Their observation/adoption/implementation/verification state is governed by `architecture/ARCHITECTURE_PATTERN_REGISTER.md`.

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

Reprocessing the same source artifact must not create duplicate entities, claims, or events.

### 6. Full provenance

Every automated transformation should retain source identity, document identity, retrieval timestamp, content fingerprint, parser/model version, and transformation trace where practical.

### 7. Human authority is risk-based

Routine high-confidence metadata may be automated only when policy explicitly allows it. Material inventory, delivery, retirement, operational-state, conflict-resolution, and strategically significant changes require stronger evidence and human review by default.

### 8. Store identity is not domain identity

Backend-native identifiers are adapter mappings. Public/domain IDs remain stable across a backend migration.

### 9. Procurement history is event-based

Approval, contract, order, delivery, and operational service are distinct events/claims. A convenience lifecycle state must not erase the underlying chronology.

## M0 Knowledge-Core Decision Gate

Wikibase will be accepted only if a prototype demonstrates all of the following without structural workarounds that distort project semantics:

- Arabic and English canonical labels and aliases
- stable project entity identifiers mapped independently of store-native IDs
- typed relationships
- claims with qualifiers
- multiple references per claim
- conflicting claims coexisting
- point-in-time and validity semantics
- revision history
- machine-friendly write/read API
- query support adequate for public views
- clean mapping from approved project ChangeProposals to backend writes
- rejected/unapproved proposals remaining non-canonical

If it fails materially, the fallback is a PostgreSQL claim/evidence schema retaining the same domain model.

Passing M0 may justify adoption for the knowledge-core role; it does **not** establish production scaling, high availability, backup/recovery, security hardening, or operational readiness.

## Deferred Decisions

The following are intentionally deferred until M0/M1:

- final knowledge-store technology
- production authentication/authorization implementation
- graph database adoption
- production hosting topology
- queue technology
- model provider/runtime
- final CMS choice
- final search engine sizing/topology
