# Architecture Pattern Register Source Ledger

The source ledger records the evidence basis used to characterize architectural patterns. External evidence can inform architecture but does not itself authorize adoption.

## SRC-PROJ-001 — Architecture baseline

- kind: project-native
- identity: `docs/ARCHITECTURE.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: canonical domain model, system boundaries, design rules, M0 knowledge-core gate, deferred decisions
- reliability_notes: project-authoritative architectural baseline, subject to later ADR supersession
- linked_patterns: APR-001, APR-003, APR-004, APR-006
- claim_limitations: does not prove implementation or production fitness

## SRC-PROJ-002 — Ontology v0.1

- kind: project-native
- identity: `docs/ONTOLOGY.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: entity/claim/evidence/event semantics, procurement/service states, quantity, naming, temporal and geographic semantics
- reliability_notes: conceptual contract; not yet an executable schema
- linked_patterns: APR-001, APR-005
- claim_limitations: does not define storage or mutation authority

## SRC-PROJ-003 — Source and claim admission policy

- kind: project-native
- identity: `docs/SOURCE_POLICY.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: source classes, claim admission, confidence, review requirements, staleness, corrections
- reliability_notes: project policy baseline
- linked_patterns: APR-001, APR-002
- claim_limitations: automation thresholds remain intentionally qualitative in v0.1

## SRC-PROJ-004 — AI governance policy

- kind: project-native
- identity: `docs/AI_GOVERNANCE.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: AI roles, GREEN/AMBER/RED authority, trace requirements, mutation/publication constraints, evaluation
- reliability_notes: project policy baseline
- linked_patterns: APR-002, APR-005, APR-006
- claim_limitations: no concrete implementation has yet been verified

## SRC-PROJ-005 — M0/M1 roadmap

- kind: project-native
- identity: `docs/ROADMAP.md`
- revision: `bootstrap/foundation`
- observed_at: 2026-09-25
- inspection_scope: current-plan authorization, M0 Wikibase spike, acceptance criteria, M1 vertical slice
- reliability_notes: current planning authority for foundation and M0
- linked_patterns: APR-001, APR-002, APR-003, APR-004, APR-005, APR-006, APR-007
- claim_limitations: later milestones are planned outcomes, not implemented commitments

## SRC-APR-001 — Architecture Pattern Register governance specification

- kind: external/project-supplied governance specification
- identity: `Architecture Pattern Register Agent Implementation Specification` supplied to the project agent
- revision: supplied 2026-09-25
- observed_at: 2026-09-25
- inspection_scope: separation of observation/adoption/implementation/verification, forcing functions, status axes, promotion records, evidence ceilings, source ledger, validation rules
- reliability_notes: used as a governance mechanism; its source-project architecture and vocabulary are not imported as product architecture
- linked_patterns: governance shell for all APR entries
- claim_limitations: does not authorize product implementation or adoption of any specific mechanism

## SRC-REV-001 — Independent foundation review

- kind: project-native review
- identity: `docs/reviews/FOUNDATION_FIRST_PASS.md`
- revision: initial frozen review
- observed_at: 2026-09-25
- inspection_scope: foundation architecture, ontology, authority, failure semantics, M0 prerequisites
- reliability_notes: frozen pre-implementation assessment; later findings must not rewrite this baseline
- linked_patterns: APR-002, APR-003, APR-005
- claim_limitations: findings are architectural review evidence, not implementation verification

## SRC-VIS-001 — MDN SVG in HTML / accessibility guidance

- kind: external official web documentation
- identity: `https://developer.mozilla.org/en-US/docs/Web/SVG/Guides/SVG_in_HTML`
- observed_at: 2026-09-26
- inspection_scope: inline SVG in HTML, `viewBox`, `role="img"`, `<title>`, `<desc>`, accessibility object model
- reliability_notes: MDN technical documentation; current page inspected during M2 visualization APR
- linked_patterns: APR-007
- claim_limitations: establishes browser/web-platform mechanism guidance, not project-specific layout quality or production UX

## SRC-VIS-002 — Cytoscape.js official documentation

- kind: external official project documentation
- identity: `https://js.cytoscape.org/`
- observed_at: 2026-09-26
- inspection_scope: graph visualization/analysis scope, pure-JS implementation, dependency model, browser/module support
- reliability_notes: primary documentation for Cytoscape.js capabilities
- linked_patterns: APR-007
- claim_limitations: capability evidence only; does not establish that SDA currently needs a general graph runtime

## SRC-VIS-003 — D3 force and selection official documentation

- kind: external official project documentation
- identity: `https://d3js.org/d3-force` and `https://d3js.org/d3-selection`
- observed_at: 2026-09-26
- inspection_scope: force simulation, SVG/Canvas rendering, DOM selection/data joins and interaction primitives
- reliability_notes: primary D3 documentation; current v7 documentation inspected
- linked_patterns: APR-007
- claim_limitations: capability evidence only; does not establish a need for force simulation or D3 in the bounded M2 graph

## SRC-SEARCH-001 — OpenSearch version/release documentation

- kind: external official project documentation
- identity: `https://docs.opensearch.org/latest/version-history/`, `https://opensearch.org/releases/`, `https://opensearch.org/artifacts/by-version/`
- observed_at: 2026-09-26
- inspection_scope: released OpenSearch version line, release timing, and 3.8.0 artifact availability used for the pinned trial
- reliability_notes: primary OpenSearch project sources
- linked_patterns: APR-008
- claim_limitations: version/artifact evidence only; does not establish SDA suitability or production qualification

## SRC-SEARCH-002 — OpenSearch analyzer and Docker documentation

- kind: external official project documentation
- identity: `https://docs.opensearch.org/latest/analyzers/language-analyzers/arabic/`, `https://docs.opensearch.org/latest/analyzers/token-filters/normalization/`, `https://docs.opensearch.org/latest/analyzers/token-filters/decimal-digit/`, `https://docs.opensearch.org/latest/analyzers/custom-analyzer/`, `https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/`
- observed_at: 2026-09-26
- inspection_scope: built-in Arabic analyzer composition, Arabic normalization and decimal-digit filters, custom analyzer composition, and disposable Docker trial configuration
- reliability_notes: primary OpenSearch technical documentation
- linked_patterns: APR-008
- claim_limitations: documents mechanism capability; project-specific lexical equivalence is established only by executable SDA trial evidence

## SRC-SEARCH-003 — OpenSearch repository and license

- kind: external official project repository
- identity: `https://github.com/opensearch-project/OpenSearch`
- observed_at: 2026-09-26
- inspection_scope: open-source repository and Apache-2.0 licensing context
- reliability_notes: primary project repository
- linked_patterns: APR-008
- claim_limitations: licensing/project evidence only; does not establish runtime suitability

## SRC-SEARCH-004 — Meilisearch repository/licensing and search capability context

- kind: external official project repository/documentation
- identity: `https://github.com/meilisearch/meilisearch`
- observed_at: 2026-09-26
- inspection_scope: Community Edition licensing context, multilingual/tokenization and filtering capability used for candidate characterization
- reliability_notes: primary project source; enterprise modules require separate licensing consideration if ever selected
- linked_patterns: APR-008
- claim_limitations: characterization only; Meilisearch was not executed in this bounded trial and is not rejected globally

## SRC-SEARCH-005 — PostgreSQL text search and pg_trgm documentation

- kind: external official project documentation
- identity: `https://www.postgresql.org/docs/current/sql-createtsconfig.html`, `https://www.postgresql.org/docs/current/pgtrgm.html`
- observed_at: 2026-09-26
- inspection_scope: configurable text-search mechanisms and trigram similarity/index support used for candidate characterization
- reliability_notes: primary PostgreSQL documentation
- linked_patterns: APR-008
- claim_limitations: characterization only; PostgreSQL search was not executed in this bounded trial and remains a future candidate

## SRC-SEARCH-006 — SDA OpenSearch trial verification evidence

- kind: project-native executable verification
- identity: `spikes/opensearch/run_contract_trial.py`, workflow run `36326666946` (#10), artifact `m3-opensearch-trial-evidence`
- observed_at: 2026-09-27
- inspection_scope: exact/alias/token ranking, Arabic normalization, facet semantics, exact-ID priority, Arabic-locale tie-breaking, reverse-index-order determinism, portable match-quality equivalence, backend-ID exclusion, analyzer tokens, and OpenSearch 3.8.0 runtime pin
- reliability_notes: executable bounded trial against the accepted deterministic SDA oracle; reviewed in `docs/reviews/M3_OPENSEARCH_TRIAL_FIRST_PASS.md`
- linked_patterns: APR-008
- claim_limitations: establishes only the bounded M3 downstream lexical-index role; no production/semantic/vector qualification
