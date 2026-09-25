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

## Architecture Direction

```text
Public sources
    ↓
Discovery / crawling / document parsing
    ↓
Structured extraction
    ↓
Entity resolution
    ↓
Claim + evidence verification
    ↓
Human review when required
    ↓
Canonical knowledge store
    ↓
Search / API / editorial tools / public website / research assistant
```

The canonical domain model is implementation-neutral. Wikibase is the first knowledge-core candidate to evaluate during M0, not a permanent dependency until it passes the acceptance tests in the roadmap.

## Repository Structure

```text
docs/
  VISION.md
  ARCHITECTURE.md
  ONTOLOGY.md
  SOURCE_POLICY.md
  AI_GOVERNANCE.md
  ROADMAP.md
```

Application and infrastructure directories will be introduced only after M0 validates the data model and knowledge-core choice.

## Status

**Phase:** Foundation / M0

The immediate objective is to prove one complete vertical slice from a public source to a structured, referenced, bilingual fact and then expose it through an API and a minimal public page.

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## License

License selection is intentionally deferred until the repository's code/data/content licensing boundaries are defined. Source code, structured data, and third-party sourced material may require different terms.
