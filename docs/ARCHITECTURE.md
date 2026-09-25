# Architecture Baseline

## ADR-0001 — Knowledge-first architecture

**Status:** Accepted. M0 knowledge-core mechanism resolved by ADR-0002.

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

The storage implementation may change without changing these domain semantics. ADR-0002 selects Wikibase for the M1 canonical knowledge-core role while retaining PostgreSQL as a deferred fallback.

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
- The ReviewDecision binds to the exact proposal payload.
- Backend write receipts are audit evidence, not proof that the policy decision was valid.
- A project Revision records the applied result after authorization; it is distinct from a MediaWiki/Wikibase backend revision.

The project owner and accepted roadmap/ADRs define product and architecture authority. Production user/role authorization, effect reconciliation, and operational persistence mechanics remain M1/later implementation work.

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
│   Wikibase via project-owned adapters       │
└───────────────┬───────────────┬─────────────┘
                │               │
        ┌───────▼──────┐ ┌──────▼────────┐
        │ Search / API │ │ Editorial UI  │
        └───────┬──────┘ └──────┬────────┘
                └────────┬───────┘
                         ▼
┌─────────────────────────────────────────────┐
│              EXPERIENCE PLANE               │
│ web · atlas · timeline · graph · AI research│
└─────────────────────────────────────────────┘
```

## Open-Source Component Status

Architecture status is governed by `architecture/ARCHITECTURE_PATTERN_REGISTER.md`, not by appearance in this list.

- **Accepted/verified for bounded M0 knowledge-core contract:** Wikibase
- **Deferred fallback:** PostgreSQL claim/evidence knowledge core
- **Observed/candidate only until separately promoted:** Payload CMS, Scrapy, Crawl4AI, Playwright, Trafilatura, Docling, PydanticAI, Prefect, pgvector, OpenSearch, MapLibre GL JS, Cytoscape.js, Langfuse, Next.js, and other future mechanisms.

External mechanism availability does not create roadmap scope or architecture authority.

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

### 10. Authorization, effect, and audit evidence remain distinct

An approval authorizes an exact proposed effect. The backend effect may succeed, fail, or become ambiguous. The project Revision records the observed result and receipts. Production adapters must reconcile ambiguity rather than blindly retrying.

## M0 Knowledge-Core Decision — RESOLVED

The original M0 gate required a prototype to demonstrate:

- Arabic and English canonical labels and aliases;
- stable project IDs independent from store-native IDs;
- typed relationships;
- claims with qualifiers;
- multiple references;
- conflicting claims coexisting;
- temporal semantics;
- revision history;
- machine read/write API;
- query support;
- review-gated write mapping.

The current-head M0 workflow passed these bounded criteria. ADR-0002 therefore accepts Wikibase for the M1 knowledge-core role.

Passing M0 does **not** establish production scaling, high availability, backup/recovery, security hardening, exactly-once effect semantics, or operational readiness.

## Deferred Decisions

The following remain deferred until M1/later evidence creates a forcing function:

- production authentication/authorization implementation;
- production Wikibase hosting topology;
- backup/disaster recovery design;
- target-scale performance qualification;
- mutation idempotency/reconciliation implementation;
- graph database adoption;
- queue/orchestration technology;
- model provider/runtime;
- editorial CMS/UI mechanism;
- public frontend framework/deployment;
- final search engine sizing/topology.
