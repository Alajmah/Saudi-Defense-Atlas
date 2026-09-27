# ADR-0004 — Public Search Engine Trial

- status: ACCEPTED — VERIFIED for bounded M3 lexical-index role
- trial_authorized: 2026-09-26
- verified: 2026-09-27
- milestone: M3
- pattern: APR-008

## Context

M3 has an engine-neutral, adversarially hardened public search contract (`SearchDocument`, `SearchQuery`, `SearchResult`) and a deterministic lexical reference implementation. The forcing function was to evaluate a reusable search engine without allowing engine-native scoring, analyzers, or identity to redefine that contract.

The accepted search contract supports conservative Arabic orthographic normalization, exact names/aliases/designations, whole-token matching, explicit facets, and SDA canonical IDs. It deliberately does not authorize stemming, stop-word removal, fuzzy matching, generated transliteration, embeddings, vector ranking, or semantic expansion.

## Forcing function

M3 requires Arabic-aware full-text/entity search and faceted navigation at a scale where a dedicated index may save substantial custom engineering. A concrete engine could be adopted only if a reproducible trial demonstrated that it remains downstream of the SDA search projection and preserves the public contract.

## Candidates characterized

### Option A — OpenSearch 3.8.0

Evidence inspected:

- OpenSearch documentation identified 3.8.0 as the released current 3.x version during the trial window;
- OpenSearch is Apache-2.0 licensed;
- the built-in Arabic analyzer includes standard tokenization, lowercase, decimal-digit normalization, Arabic stop words, Arabic normalization, keyword handling, and Arabic stemming;
- custom analyzers can select only the needed components;
- the Analyze API exposes generated tokens for inspection;
- `arabic_normalization` and `decimal_digit` are available independently;
- official Docker images support a single-node test configuration with the Security plugin disabled for local/test-only use.

Implication for SDA: the built-in `arabic` analyzer exceeds the M3 capability ceiling because it includes stop-word removal and stemming. The accepted lexical baseline therefore does **not** use that analyzer as canonical semantics. Contract-preserving fields use SDA-generated normalized terms; the OpenSearch Arabic analyzer is characterized separately and conservatively.

### Option B — Meilisearch Community Edition

Evidence inspected:

- Community Edition is described by the project as open source under MIT;
- Meilisearch supports multilingual tokenization, including Arabic locale configuration, and faceted filtering;
- the current project repository also contains separately licensed Enterprise Edition modules, so any future SDA adoption would need to keep the selected feature set within CE or record a licensing decision explicitly.

Strength: lower operational surface and strong out-of-the-box search UX.

Current disadvantage for this forcing function: less analyzer-level transparency/control than required to prove exact equivalence to SDA's frozen Arabic lexical contract.

### Option C — PostgreSQL full-text search + `pg_trgm`

Evidence inspected:

- PostgreSQL provides customizable text-search configurations;
- `pg_trgm` supports indexed trigram similarity/search.

Strength: minimizes additional services and keeps operational topology small.

Current disadvantage for this forcing function: reproducing the field-specific exact/prefix/token/facet contract and future multilingual relevance work would require more project-owned composition than the dedicated-search candidates. PostgreSQL remains a future candidate rather than being rejected.

## Trial decision

The project authorized **OpenSearch 3.8.0** for a bounded M3 search-index trial only. `SearchDocument` remained the authority boundary and the deterministic lexical reference remained the acceptance oracle.

## Trial invariants

1. OpenSearch is a downstream index, never canonical truth.
2. SDA IDs remain the only public/domain identifiers; Q/P/backend IDs are forbidden in indexed/public trial payloads.
3. Only validated `SearchDocument` records may enter the trial index.
4. Baseline exact/prefix/token behavior uses SDA-produced normalized projection semantics rather than engine stemming or stop-word behavior.
5. OR-within-facet / AND-across-facets semantics are preserved.
6. Engine numeric `_score` is implementation metadata and is never exposed as the public relevance contract.
7. Portable quality order remains `exact_id > exact_name > exact_alias > prefix > token`.
8. Tie-breaking is query-locale-aware and then SDA-ID deterministic.
9. The trial compares ordered SDA result IDs and portable `match_quality`, not raw engine scores.
10. Semantic/vector search is outside this decision.
11. The conservative Arabic analyzer uses `standard + lowercase + decimal_digit + arabic_normalization`; it does not add Arabic stop-word removal or stemming.
12. Security-disabled Docker configuration is local/CI trial infrastructure only and is not production configuration.

## Acceptance matrix and result

The hardened trial demonstrated:

- exact F-15SA designation resolution — **PASS**;
- compact alias/designation resolution (`F15SA`) — **PASS**;
- Arabic diacritic/orthographic normalization for Typhoon — **PASS**;
- Arabic alef-variant normalization for RSAF — **PASS**;
- whole-token isolation (`air` does not match unrelated `chair`) — **PASS**;
- manufacturer/country/entity-type facet behavior matching the deterministic oracle — **PASS**;
- portable `match_quality` equivalence — **PASS**;
- exact-ID priority over another record's exact alias — **PASS**;
- Arabic-locale tie ordering where English ordering differs — **PASS**;
- deterministic result ordering after reverse indexing order — **PASS**;
- no Q/P/backend identifiers in indexed trial payloads or returned IDs — **PASS**;
- Analyze API evidence for the conservative Arabic analyzer — **PASS**;
- clean ephemeral startup/shutdown on the pinned OpenSearch 3.8.0 image — **PASS**.

## First-pass findings closed before promotion

The first-pass review identified and remediated three issues before adoption:

1. overlapping scored clauses could allow aggregate `_score` to distort portable quality ordering;
2. one English-preferred sort field could violate Arabic tie ordering;
3. SearchDocument validation immediately before indexing was implicit rather than explicit.

The hardened trial now uses fixed `constant_score` quality tiers under `dis_max`, locale-specific tie fields, and an explicit deterministic SDA validation pass before indexing. See `docs/reviews/M3_OPENSEARCH_TRIAL_FIRST_PASS.md`.

## Final decision

Accept **OpenSearch 3.8.0 as the M3 downstream public lexical-search index implementation behind SDA-owned search contracts**.

This acceptance does not make OpenSearch canonical truth, does not expose engine `_score`, and does not adopt the built-in Arabic stemmed analyzer as SDA lexical semantics.

Meilisearch CE and PostgreSQL FTS/`pg_trgm` remain characterized alternatives for future forcing functions; this decision does not globally reject them.

## Verification evidence

Hardened implementation head before governance promotion:

- `5372d7642b945cddfbd240b1c294b4ce77ed4d5f`
- schema-validation run `36326666973` (#464) — **PASS**
- opensearch-verification run `36326666946` (#10) — **PASS**
- workflow artifact: `m3-opensearch-trial-evidence`
- first-pass review: `docs/reviews/M3_OPENSEARCH_TRIAL_FIRST_PASS.md`

## Replacement / expansion forcing functions

A new APR decision is required before materially expanding this role for any of the following:

- production security/HA/backup/recovery/upgrade qualification;
- target-scale capacity or performance commitments;
- fuzzy matching;
- stemming or stop-word policy;
- semantic/vector retrieval or hybrid ranking;
- materially different multilingual relevance requirements;
- final deployment topology;
- evidence that OpenSearch operational burden outweighs its index benefits.

## Claim ceiling

Verification establishes suitability only for the tested M3 downstream lexical-index role. It does not establish production security, HA, backup/restore, upgrade strategy, target-scale capacity, semantic/vector relevance quality, final deployment topology, or final frontend architecture.

## External evidence inspected

- OpenSearch version history: https://docs.opensearch.org/latest/version-history/
- OpenSearch release schedule: https://opensearch.org/releases/
- OpenSearch 3.8.0 artifacts: https://opensearch.org/artifacts/by-version/
- OpenSearch Arabic analyzer: https://docs.opensearch.org/latest/analyzers/language-analyzers/arabic/
- OpenSearch normalization filters: https://docs.opensearch.org/latest/analyzers/token-filters/normalization/
- OpenSearch decimal-digit filter: https://docs.opensearch.org/latest/analyzers/token-filters/decimal-digit/
- OpenSearch custom analyzers: https://docs.opensearch.org/latest/analyzers/custom-analyzer/
- OpenSearch Docker installation: https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/
- OpenSearch repository/license: https://github.com/opensearch-project/OpenSearch
- Meilisearch repository/licensing: https://github.com/meilisearch/meilisearch
- PostgreSQL text-search configuration: https://www.postgresql.org/docs/current/sql-createtsconfig.html
- PostgreSQL `pg_trgm`: https://www.postgresql.org/docs/current/pgtrgm.html
