# Saudi Defense Atlas

Saudi Defense Atlas is a bilingual, source-backed knowledge platform for publicly documented information about Saudi military forces, equipment, procurement, exercises, defense industry, training, and historical development.

The project is designed as a structured knowledge system rather than a conventional news site. Articles, public pages, search results, timelines, and future AI-assisted research experiences are projections of sourced canonical knowledge rather than independent stores of factual truth.

## Current architecture

The durable domain model is built around:

```text
Entity + Claim + Evidence + Event + Revision
```

Key invariants include:

- SDA canonical IDs define domain identity; backend Q/P IDs are adapter mappings only.
- Source, Document, and Evidence are separate provenance layers.
- Procurement approval, contract, delivery, and operational service are distinct states/events.
- Unknown information remains unknown rather than being inferred for presentation convenience.
- AI may propose changes but cannot directly mutate canonical knowledge.
- Public output excludes live operational tracking, readiness, stock levels, patrol patterns, and other sensitive operational aggregation.

Wikibase is the accepted canonical knowledge-core implementation for the bounded M1 role, behind project-owned governance, read, and write contracts.

## M1 vertical slice

The first vertical slice demonstrates an authoritative public-source path for the F-15SA:

```text
Official source
  ↓
Document + Evidence
  ↓
typed Claim / Event proposal
  ↓
human-bound review authorization
  ↓
canonical Wikibase mutation
  ↓
project Revision + backend receipt
  ↓
SDA canonical read adapter
  ↓
EquipmentView
  ↓
SDA-ID JSON API + Arabic/English public page
```

The public projection requires at least one supporting Evidence link for every material Claim/Event, keeps operator/inventory/service-state unknown when not established by admitted Claims, separates canonical payload hashes from public read-projection hashes, and excludes backend Q/P identifiers from the application contract.

The M1 web shell is intentionally framework-neutral. Selection of a production frontend framework and deployment topology remains an Architecture Pattern Register decision rather than an implicit M1 dependency.

## Repository map

- `architecture/` — pattern register, decisions, validation and source ledger
- `docs/` — vision, architecture, ontology, source/AI policy, ADRs, roadmap, and reviews
- `schemas/v0.1/` — implementation-neutral domain, governance, and public read schemas
- `services/` — ingestion, intelligence, governance, and presentation contracts
- `spikes/wikibase/` — reproducible canonical-core and clean-stack verification environment
- `scripts/` — schema, workflow, M1, and public projection validation
- `data/` — bounded source registry/seed material

## Qualification boundary

M0–M3 and the bounded M4 editorial-control increments establish the canonical knowledge model, governed mutation/readback path, cited bilingual public projections, deterministic monitoring/extraction/review contracts, and a logical global single-writer mutation-dispatch boundary. The M4 dispatcher verifies fail-closed single-writer behavior and replay safety with a project-owned in-memory coordination fixture; it does **not** qualify a shared atomic lock/queue/lease mechanism across multiple processes or hosts. Multiple production automated canonical writers remain disabled until such a coordinator is selected and independently verified.

The M4 editorial auditor and daily brief are operational metadata projections only. They add no truth, approval, canonical-mutation, publication, scheduler, or autonomous-remediation authority.

See `docs/ROADMAP.md` and `docs/M1_PUBLIC_PROJECTION.md` for milestone scope and qualification boundaries.
