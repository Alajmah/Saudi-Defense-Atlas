# Architecture Pattern Register Decision Log

This log records explicit architectural promotion, deferment, rejection, supersession, trial authorization, and bounded verification. Register entries do not promote themselves.

## APRD-001 — Adopt claim/evidence canonical knowledge model

- date: 2026-09-25
- pattern: APR-001
- from_status: CANDIDATE
- to_status: ACCEPTED
- forcing_function: The product must preserve sourced, temporal, conflicting defense knowledge and expose the same facts across multiple views.
- adopted_invariant: Material factual knowledge preserves claim identity, evidence provenance, temporal context, and revision history.
- scope: canonical defense knowledge represented by the Atlas.
- non_scope: editorial prose as authoritative storage; unsourced rumor as canonical truth.
- failure_model: orphan claims, destructive overwrite, evidence detached from claims, store-native identity leaking into domain identity.
- verification_plan: implementation-neutral schemas in M0; end-to-end source-to-page proof in M1.
- claim_ceiling: adoption establishes the domain contract, not the final storage implementation.
- authority_reference: `docs/ARCHITECTURE.md` ADR-0001 and `docs/ROADMAP.md` M0.
- rationale: This is the minimum data model needed to satisfy the product thesis.

## APRD-002 — Adopt review-gated canonical mutation

- date: 2026-09-25
- pattern: APR-002
- from_status: CANDIDATE
- to_status: ACCEPTED
- forcing_function: M0 requires machine read/write and AI-proposed changes without allowing model output to become canonical automatically.
- adopted_invariant: Proposal is distinct from canonical revision.
- scope: all canonical knowledge mutations, including AI-assisted ingestion.
- non_scope: deterministic internal metadata fields explicitly authorized as GREEN by policy may be admitted automatically through the same revision contract.
- failure_model: direct model writes, review bypass, hidden overwrite, ambiguous approval authority.
- verification_plan: demonstrate proposal creation, rejection without canonical mutation, approval with auditable revision, and deterministic policy rejection.
- claim_ceiling: successful verification establishes mutation-governance semantics for tested adapters, not universal security or production readiness.
- authority_reference: `docs/AI_GOVERNANCE.md`, `docs/ROADMAP.md` M0 criterion 7.
- rationale: The knowledge store must not become the authority boundary.

## APRD-003 — Authorize bounded Wikibase trial

- date: 2026-09-25
- pattern: APR-003
- from_status: CANDIDATE
- to_status: TRIAL-AUTHORIZED
- forcing_function: M0 must choose a knowledge-core implementation before M1.
- adopted_invariant: Any trial must preserve project-native claim/evidence/revision semantics and remain behind the proposal/review authority boundary.
- adaptation: Wikibase is evaluated as a storage/query implementation, not adopted as the project's ontology or governance vocabulary.
- scope: local reproducible M0 prototype using the seed dataset.
- non_scope: production hosting, scaling, availability, backup, final adoption, public release.
- failure_model: awkward qualifier/reference mapping; inability to represent conflict cleanly; write API bypassing governance; store-native identity leakage; excessive operational complexity.
- verification_plan: execute every M0 Wikibase acceptance criterion and record evidence in ADR-0002.
- claim_ceiling: passing the spike may justify architectural adoption for the knowledge-core role only.
- authority_reference: `docs/ROADMAP.md` M0 Wikibase Spike.
- rationale: Trial is authorized because reuse may substantially reduce custom knowledge-system engineering.

## APRD-004 — Defer custom PostgreSQL knowledge core

- date: 2026-09-25
- pattern: APR-004
- from_status: CANDIDATE
- to_status: DEFERRED
- forcing_function: none while the Wikibase trial remains viable.
- scope: potential knowledge-core fallback.
- non_scope: current implementation work.
- verification_plan: only activate if APR-003 fails a critical project invariant or later evidence demonstrates unacceptable complexity.
- claim_ceiling: no implementation claim; fallback remains architectural knowledge only.
- authority_reference: `docs/ARCHITECTURE.md` M0 decision gate / ADR-0002 fallback clause.
- rationale: Avoid parallel implementation and infrastructure inflation before evidence requires it.

## APRD-005 — Promote Wikibase to accepted knowledge core

- date: 2026-09-25
- pattern: APR-003
- from_status: TRIAL-AUTHORIZED
- to_status: ACCEPTED
- implementation_status: VERIFIED for the bounded M0 representation/governance contract
- forcing_function: M1 requires a selected knowledge-core implementation and the M0 trial has now produced clean current-head verification evidence.
- adopted_invariant: Wikibase is subordinate to SDA domain identity, ontology, evidence semantics, and mutation authority.
- adaptation: claims project to statements/qualifiers; evidence projects to references without replacing the richer SDA Source/Document/Evidence model; SDA IDs map to Q/P IDs but remain canonical.
- scope: canonical knowledge storage/query implementation for M1.
- non_scope: production security, HA, backup/recovery, target-scale performance, exactly-once mutation, ambiguous-effect reconciliation, public API hardening, long-term upgrade qualification.
- failure_model: Q/P identity leakage; adapter bypass; WDQS convergence lag; production operational burden; ambiguous external effects; future store constraints that distort SDA semantics.
- verification_plan: completed M0 clean run plus continuing M1 vertical-slice verification; production properties require separate verification.
- verification_evidence: schema/governance run `36178033709`; Wikibase run `36178040438` / job `108213344752`; artifact `10883261546`; ADR-0002 acceptance matrix.
- claim_ceiling: Wikibase is suitable to proceed as the M1 canonical knowledge core under the tested project-owned adapter/governance contract.
- authority_reference: `docs/adr/ADR-0002-knowledge-core.md`.
- rationale: All critical M0 criteria passed without material ontology distortion or governance bypass.

## APRD-006 — Record bounded verification of review-gated mutation

- date: 2026-09-25
- pattern: APR-002
- pattern_status: ACCEPTED (unchanged)
- implementation_status_from: IN-TRIAL
- implementation_status_to: VERIFIED
- scope: tested M0 proposal/review/hash-binding/temporal-order/adapter-receipt contract.
- non_scope: production exactly-once behavior, retry safety after ambiguous external effects, distributed concurrency, or durable queue semantics.
- verification_evidence: workflow fixtures and validation; synthetic AMBER approval applied through `apply_approved_demo.py` in run `36178040438`.
- claim_ceiling: the tested adapter does not write before authorization and records backend identifiers as receipts after the effect; broader mutation reliability remains future work.
- authority_reference: `docs/AI_GOVERNANCE.md`, `docs/reviews/M0_ADVERSARIAL_REVIEW.md`, ADR-0002.

## APRD-007 — Authorize bounded deterministic SVG relationship-visualization trial

- date: 2026-09-26
- pattern: APR-007
- from_status: CANDIDATE
- to_status: TRIAL-AUTHORIZED
- implementation_status: IN-TRIAL
- forcing_function: M2 requires a first relationship visualization while the accepted graph is deliberately bounded and no frontend/graph runtime has been selected.
- adopted_invariant: visualization consumes `RelationshipGraphView` only and may not invent topology, replace SDA identity, or remove supporting Evidence from material relationships.
- adaptation: use server-rendered deterministic inline SVG with semantic cited HTML fallback; localize labels without changing graph identity.
- alternatives_characterized: Cytoscape.js; D3 selection/force; project-owned SVG.
- scope: first bounded M2 relationship visualization and bilingual route/API proof.
- non_scope: large graph exploration, force-directed layout, drag/pan/zoom, graph editing, browser-side graph analysis, final frontend stack selection.
- failure_model: visual-only inferred edges, Q/P leakage, citation loss, nondeterministic layout, inaccessible SVG, global SVG ID collisions, bounded layout used past readable scale.
- verification_plan: deterministic reorder test; supporting-Evidence rejection; accessible title/description; graph-scoped SVG IDs; cited HTML fallback; bilingual routes; exact graph JSON API; no backend identifiers.
- claim_ceiling: successful trial may justify acceptance only for the bounded M2 visualization role.
- authority_reference: `docs/adr/ADR-0003-first-relationship-visualization.md`, `docs/ROADMAP.md` M2.
- rationale: the first graph is small enough that a browser-native deterministic renderer meets the forcing function with less dependency/interaction surface than a general graph engine.

## APRD-008 — Promote deterministic SVG relationship visualization after bounded verification

- date: 2026-09-26
- pattern: APR-007
- from_status: TRIAL-AUTHORIZED
- to_status: ACCEPTED
- implementation_status_from: IN-TRIAL
- implementation_status_to: VERIFIED
- forcing_function: the M2 trial has implemented the authorized renderer and passed the bounded publication/accessibility/provenance contract.
- adopted_invariant: the visual layer remains a deterministic projection over `RelationshipGraphView`, and every rendered material edge retains supporting Evidence plus canonical source-record identity.
- scope: bounded M2 procurement/exercise relationship visualization, JSON graph API, and Arabic/English public relationship pages.
- non_scope: large graph exploration, interactive pan/zoom/drag, force-directed layout, compound nodes, final frontend-stack selection, browser-side graph analysis.
- failure_model_verified: reordered input changing output; unsupported/context-only edge publication; backend Q/P leakage; inaccessible/global SVG identifiers; untranslated human edge labels; graph API mutation.
- verification_evidence: implementation/review head `b78564fa83bf128803205bc2a22ea88a8284ecb2`; schema-validation run `36260932930` (#395) PASS; Wikibase regression run `36260932947` (#124) PASS; `docs/reviews/M2_RELATIONSHIP_VISUALIZATION_FIRST_PASS.md`.
- replacement_forcing_functions: sustained large graphs, required pan/zoom/drag, compound nodes, frequent client-side relayout/filtering, graph analytics, or demonstrated deterministic-layout quality failure.
- claim_ceiling: verification establishes only the bounded M2 visualization role; it does not qualify a general graph engine or final frontend architecture.
- authority_reference: `docs/adr/ADR-0003-first-relationship-visualization.md`.
- rationale: the project-owned renderer satisfies the current forcing function with less dependency and nondeterminism than a general graph runtime, while preserving an explicit future migration gate.

## APRD-009 — Authorize bounded OpenSearch lexical-index trial

- date: 2026-09-26
- pattern: APR-008
- from_status: CANDIDATE
- to_status: TRIAL-AUTHORIZED
- implementation_status: IN-TRIAL
- forcing_function: M3 requires Arabic-aware public search and explicitly requires engine/index selection through APR evidence after the engine-neutral contract is frozen.
- adopted_invariant: `SearchDocument`, SDA identity, normalization, portable match-quality ordering, and facet semantics remain authoritative; the engine is a downstream index only.
- alternatives_characterized: OpenSearch 3.8.0; Meilisearch Community Edition; PostgreSQL FTS + `pg_trgm`.
- scope: reproducible OpenSearch 3.8.0 lexical-index trial against the M3 deterministic oracle.
- non_scope: production qualification, fuzzy/stemming behavior, semantic/vector retrieval, final deployment topology, final frontend stack.
- failure_model: engine scoring overriding quality order; analyzer drift; backend identity leakage; facet semantic drift; locale-insensitive ordering; malformed index inputs; ingestion-order dependence.
- verification_plan: compare ordered SDA IDs and portable `match_quality` against the deterministic oracle; inspect conservative Arabic analyzer tokens; pin runtime version; reverse indexing order; verify no Q/P leakage.
- claim_ceiling: a passing trial may justify acceptance only for the bounded downstream lexical-index role.
- authority_reference: `docs/adr/ADR-0004-search-engine-trial.md`, `docs/ROADMAP.md` M3.
- rationale: OpenSearch provides the strongest analyzer transparency/control for proving equivalence to the already-frozen SDA lexical contract without requiring the project to adopt stemming or semantic features.

## APRD-010 — Promote OpenSearch lexical index after bounded verification

- date: 2026-09-27
- pattern: APR-008
- from_status: TRIAL-AUTHORIZED
- to_status: ACCEPTED
- implementation_status_from: IN-TRIAL
- implementation_status_to: VERIFIED
- forcing_function: the hardened OpenSearch trial has passed the portable lexical contract after first-pass remediation.
- adopted_invariant: OpenSearch remains downstream of validated `SearchDocument` records; engine `_score` is not public authority, and fixed quality tiers implement rather than redefine SDA ranking semantics.
- scope: bounded M3 lexical/entity search and facets under the tested contract.
- non_scope: production security, HA, backup/recovery, upgrades, target-scale capacity, fuzzy matching, stemming/stop-word policy, semantic/vector search, final deployment topology, final frontend architecture.
- failure_model_verified: additive score collision; exact-ID versus alias priority; Arabic locale tie ordering; substring false positives; facet semantics; index-order nondeterminism; backend Q/P leakage; analyzer overreach; malformed projected records.
- verification_evidence: implementation head `5372d7642b945cddfbd240b1c294b4ce77ed4d5f`; schema-validation run `36326666973` (#464) PASS; OpenSearch verification run `36326666946` (#10) PASS; workflow artifact `m3-opensearch-trial-evidence`; `docs/reviews/M3_OPENSEARCH_TRIAL_FIRST_PASS.md`.
- replacement_forcing_functions: production qualification; target-scale evidence; semantic/vector retrieval requirement; fuzzy/stemming policy; materially different multilingual relevance needs; unacceptable operational burden.
- claim_ceiling: verification establishes suitability only for the tested M3 downstream lexical-index role.
- authority_reference: `docs/adr/ADR-0004-search-engine-trial.md`.
- rationale: the hardened trial matches the deterministic SDA oracle on ordered IDs and portable match quality while keeping Arabic normalization, facets, and identity under project-owned contracts.
