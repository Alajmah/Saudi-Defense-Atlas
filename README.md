# Saudi Defense Atlas

Saudi Defense Atlas is an open-source, bilingual knowledge platform for publicly available information about Saudi defense forces, equipment, procurement, training, defense industry, and historically documented deployments.

The project is **knowledge-first**: facts are modeled as structured entities, claims, evidence, events, and relationships. Articles and visualizations are views over that knowledge base rather than the primary source of truth.

## Principles

- **Source-first:** every material factual claim must be traceable to evidence.
- **Temporal:** facts may change; the system preserves point-in-time context and revision history.
- **Bilingual:** Arabic and English are first-class, with canonical names and aliases.
- **AI-assisted, human-governed:** AI may discover, extract, reconcile, summarize, translate, and propose updates; publication authority is policy-bound.
- **Open-source intelligence only:** the platform focuses on lawful, publicly available information.
- **No operational tracking:** the project does not aim to expose real-time or sensitive operational movements, readiness, patrol patterns, ammunition stocks, or non-public precise locations.
- **Knowledge over news:** news is an input to the knowledge system, not the database itself.

## Initial Scope

- Military organizations and branches
- Equipment and variants
- Manufacturers and defense companies
- Procurement and contracts
- Deliveries and upgrade programs
- Exercises and training
- Defense-industry localization
- Publicly documented bases and facilities at an appropriate non-operational level
- Timelines, relationships, and source-backed analysis

## Architecture

```text
Public sources
    ↓
Discovery / fetch / document parsing
    ↓
Document + Evidence
    ↓
Structured candidate extraction
    ↓
Entity resolution
    ↓
ChangeProposal
    ↓
Policy + evidence validation
    ↓
Human review when required
    ↓
Backend mutation
    ↓
Canonical Revision + backend receipt
    ↓
Wikibase knowledge core
    ↓
Read API / public website / search / research tools
```

The **domain model remains implementation-neutral** even though M0 has selected Wikibase as the M1 canonical knowledge-core implementation. SDA domain IDs, claim/evidence semantics, and mutation authority remain project-owned; Wikibase Q/P identifiers and MediaWiki revisions are implementation mappings/receipts rather than public authority.

See [`docs/adr/ADR-0002-knowledge-core.md`](docs/adr/ADR-0002-knowledge-core.md).

## Repository Structure

```text
architecture/            Architecture Pattern Register and decision/evidence logs
docs/                    Vision, architecture, ontology, policies, roadmap, ADRs, reviews
schemas/v0.1/            Implementation-neutral domain/governance JSON Schemas
scripts/                 Schema and cross-record governance validators
spikes/wikibase/         Reproducible M0 Wikibase knowledge-core verification
tests/fixtures/          Positive/negative schema and workflow fixtures
.github/workflows/       Validation and M0 knowledge-core CI
```

## Status

**M0 — Foundation and Knowledge-Core Spike: COMPLETE**

M0 verified the bounded Wikibase representation/query/governance contract and adopted Wikibase for the M1 knowledge-core role. The project does **not** treat that verification as production qualification.

**M1 — First Vertical Slice: NEXT**

The next objective is one end-to-end path from an authoritative public source to a cited Arabic/English equipment page, including deterministic retrieval/deduplication, typed AI proposals, review-gated mutation, canonical Wikibase storage, evidence traceability, and mutation idempotency/reconciliation semantics.

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Verification Discipline

Architecture promotion is evidence-based:

```text
observation != adoption
adoption != implementation
implementation != verification
verification != production qualification
```

The canonical status vocabulary and evidence are maintained in [`architecture/ARCHITECTURE_PATTERN_REGISTER.md`](architecture/ARCHITECTURE_PATTERN_REGISTER.md).

## License

License selection is intentionally deferred until the repository's code/data/content licensing boundaries are defined. Source code, structured data, and third-party sourced material may require different terms.
