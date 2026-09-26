# ADR-0004 — Public Search Engine Trial

- status: TRIAL-AUTHORIZED
- date: 2026-09-26
- milestone: M3
- pattern: APR-008 (pending bounded verification)

## Context

M3 now has an engine-neutral, adversarially hardened public search contract (`SearchDocument`, `SearchQuery`, `SearchResult`) and a deterministic lexical reference implementation. The next forcing function is to evaluate a reusable search engine without allowing engine-native scoring, analyzers, or identity to redefine that contract.

The accepted search contract deliberately supports conservative Arabic orthographic normalization, exact names/aliases/designations, whole-token matching, explicit facets, and SDA canonical IDs. It deliberately does not yet authorize stemming, stop-word removal, fuzzy matching, generated transliteration, embeddings, vector ranking, or semantic expansion.

## Forcing function

M3 requires Arabic-aware full-text/entity search and faceted navigation at a scale where a dedicated index may save substantial custom engineering. A concrete engine may be adopted only if a reproducible trial demonstrates that it can remain downstream of the SDA search projection and preserve the public contract.

## Candidates characterized

### Option A — OpenSearch 3.8.0

Evidence inspected:

- current OpenSearch documentation lists 3.8.0 as the released current 3.x version as of 2026-09-26; 3.9.0 remains in its release window;
- OpenSearch is Apache-2.0 licensed;
- the built-in Arabic analyzer uses standard tokenization plus lowercase, decimal-digit normalization, Arabic stop words, Arabic normalization, keyword handling, and Arabic stemming;
- custom analyzers can select only the needed components;
- the Analyze API exposes generated tokens for inspection;
- `arabic_normalization` and `decimal_digit` are available independently;
- official Docker images support a single-node test configuration with the Security plugin disabled for local/test-only use.

Implication for SDA: the built-in `arabic` analyzer exceeds the current M3 capability ceiling because it includes stop-word removal and stemming. The trial therefore must not use it as canonical baseline semantics. Contract-preserving lexical fields will use SDA-generated normalized terms; a separate conservative custom analyzer may be characterized for future full-text recall.

### Option B — Meilisearch Community Edition

Evidence inspected:

- Community Edition is described by the project as fully open source under MIT;
- Meilisearch supports multilingual tokenization, including Arabic locale configuration, and faceted filtering;
- current repository also contains separately licensed Enterprise Edition modules, so a future adoption would need to keep the selected feature set within CE or record the licensing change explicitly.

Strength: lower operational surface and strong out-of-the-box search UX.

Current trial disadvantage: less analyzer-level transparency/control than the forcing function needs for demonstrating exact equivalence to SDA's already frozen Arabic lexical contract.

### Option C — PostgreSQL full-text search + `pg_trgm`

Evidence inspected:

- PostgreSQL provides customizable text-search configurations;
- `pg_trgm` supports indexed trigram similarity/search.

Strength: minimizes additional services and keeps operational topology small.

Current trial disadvantage: reproducing the existing field-specific exact/prefix/token/facet contract and future multilingual relevance work would require more project-owned composition than the dedicated-search candidates. PostgreSQL remains viable as a later forcing-function candidate rather than being rejected.

## Trial decision

Authorize **OpenSearch 3.8.0** for a bounded M3 search-index trial only.

This is not adoption. `SearchDocument` remains the authority boundary, and the deterministic lexical reference remains the acceptance oracle during the trial.

## Trial invariants

1. OpenSearch is a downstream index, never canonical truth.
2. SDA IDs remain the only public/domain identifiers; Q/P/backend IDs are forbidden in indexed/public trial payloads.
3. Only schema-valid `SearchDocument` records may enter the trial index.
4. Baseline exact/prefix/token behavior must use SDA-produced normalized projection semantics rather than silently adopting engine stemming or stop-word behavior.
5. OR-within-facet / AND-across-facets semantics must be preserved.
6. Engine numeric `_score` is implementation metadata and is never exposed as the public relevance contract.
7. The trial compares ordered SDA result IDs and declared portable match categories, not raw engine scores.
8. Semantic/vector search is out of scope for this trial.
9. The conservative Arabic analyzer trial may use `standard + lowercase + decimal_digit + arabic_normalization`; it must not add Arabic stop-word removal or stemming.
10. Security-disabled Docker configuration is local/CI trial infrastructure only and is not production configuration.

## Acceptance matrix

The trial must demonstrate:

- exact F-15SA designation resolution;
- compact alias/designation resolution (`F15SA`);
- Arabic diacritic/orthographic normalization for Typhoon;
- Arabic alef-variant normalization for RSAF;
- whole-token isolation (`air` must not match unrelated `chair` text);
- manufacturer/country/entity-type facet behavior matching the deterministic oracle;
- deterministic tie-breaking by portable fields rather than input order;
- no Q/P/backend identifiers in indexed records or returned public IDs;
- Analyze API evidence for the conservative Arabic analyzer;
- clean ephemeral startup/shutdown on the pinned 3.8.0 image.

## Promotion gate

Promote APR-008 to `ACCEPTED / VERIFIED` only if the bounded trial passes the acceptance matrix and first-pass review finds no unresolved contract violation. Failure to match the baseline contract keeps OpenSearch as `CANDIDATE` or `DEFERRED`; the project must not weaken the search contract merely to fit the engine.

## Non-scope / claim ceiling

A passing trial would establish suitability as the M3 public search-index implementation behind the tested contract only. It would not establish production security, HA, backup/restore, upgrade strategy, target-scale capacity, semantic/vector relevance quality, final deployment topology, or final frontend architecture.

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
