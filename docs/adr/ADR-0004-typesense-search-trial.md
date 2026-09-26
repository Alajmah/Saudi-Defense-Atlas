# ADR-0004 — Bounded Public Search Engine Trial

- status: TRIAL-AUTHORIZED
- date: 2026-09-26
- milestone: M3
- pattern: APR-008

## Context

M3 now has an accepted engine-neutral `SearchDocument` / `SearchQuery` / `SearchResult` contract with conservative Arabic normalization, explicit aliases/facets, deterministic match-quality tiers, and a capability ceiling that does not claim stemming, fuzzy matching, generated transliteration, synonyms, or semantic/vector retrieval.

The roadmap now requires evidence for a concrete public search index/runtime. The selected mechanism must remain a disposable derived index behind the SDA contract rather than become a second source of truth or relevance authority.

## Forcing function

Prove that one self-hostable search engine can index the M3 public projection and retrieve Arabic/English entity candidates without widening the accepted lexical contract or leaking engine identity/scoring semantics into the public API.

## Candidates characterized

### Option A — Typesense

Current official documentation establishes:

- field-level locale support using ICU, including Arabic (`ar`);
- optional stemming rather than mandatory stemming (`stem: true` enables it);
- `pre_segmented_query` for caller-owned space segmentation;
- explicit controls for prefix search, typo tolerance, token dropping, split/join behavior, and infix search;
- faceted fields and exact-value filter syntax;
- collection aliases for zero-downtime full re-indexing/schema changes;
- self-hosted single-binary operation, snapshots, and optional Raft-based HA;
- server licensing under GPL-3.0, while clients are separately licensed.

Fit to SDA trial:

- SDA can normalize text before indexing/querying;
- stemming can remain disabled;
- typo correction/token dropping/split-join/infix can be disabled in the bounded lexical trial;
- exact facets map cleanly to current filters;
- engine `_text_match` need not become a public score because SDA can reclassify/rank returned candidates using its reference contract.

Liabilities:

- in-memory index structures consume RAM proportional to indexed fields/data;
- self-hosted HA requires at least three nodes for one-node fault tolerance;
- GPL-3.0 server licensing must remain visible in deployment/legal review;
- default search behavior is broader than the SDA v0.1 capability ceiling, so the adapter must explicitly disable non-authorized matching behaviors.

### Option B — Meilisearch Community Edition

Current official documentation establishes:

- Community Edition core under MIT licensing;
- localized attributes/query locales;
- configurable typo tolerance, including full disable and field/word controls;
- filterable attributes and faceting;
- atomic index swapping for zero-downtime re-index deployment;
- dumps/snapshots and simple self-hosted operation.

Fit:

- operationally simple and capable of the required filters;
- typo tolerance can be constrained;
- localized attributes provide multilingual control.

Why not the first trial:

- the inspected official evidence is less explicit about caller-owned Arabic token segmentation than Typesense's ICU locale plus `pre_segmented_query` controls;
- the first M3 trial is specifically about preserving SDA's already-frozen token/normalization semantics, so explicit segmentation control has higher evidentiary value than default search ergonomics.

Meilisearch remains a viable candidate and is not rejected.

### Option C — OpenSearch

Current official documentation establishes:

- built-in Arabic analyzer with Arabic normalization/stemming components;
- fully custom analyzers and an optional ICU analysis plugin;
- exact keyword/filter query mechanisms;
- index aliases for zero-downtime cutover;
- snapshot APIs and distributed-cluster operations;
- Apache-2.0 licensing.

Fit:

- strongest analyzer customization surface among the characterized candidates;
- capable of expressing the SDA normalization/tokenization boundary very precisely.

Why not the first trial:

- substantially larger cluster/plugin/analysis configuration surface than needed for the current bounded entity-search forcing function;
- the built-in Arabic analyzer includes stemming, which SDA v0.1 intentionally does not claim, so a custom analyzer would be required immediately;
- production operations are materially more complex than a single-binary bounded trial.

OpenSearch remains a strong future candidate if search scale, analyzer complexity, aggregations, or operational requirements create a forcing function.

## Decision

Authorize **Typesense 30.2** as the first bounded M3 search-engine trial.

This is **not** an adoption decision. APR-008 remains `TRIAL-AUTHORIZED / IN-TRIAL` until an executable current-head trial demonstrates that the adapter preserves the frozen M3 contract.

## Trial architecture

```text
approved SearchDocument[]
        ↓
SDA Typesense adapter
  - flat index document mapping
  - no backend identity leakage
        ↓
Typesense collection (derived/disposable)
        ↓
strict candidate retrieval
  - normalized query from SDA
  - typo tolerance disabled
  - token dropping disabled
  - split/join disabled
  - infix disabled
  - explicit facets only
        ↓
returned candidate SDA IDs
        ↓
SDA reference classifier/ranker
        ↓
SearchResult
```

Typesense is therefore a **candidate retrieval/index mechanism**, not the owner of canonical identity, normalization semantics, match-quality classification, or public ranking semantics.

## Trial invariants

1. SDA `SearchDocument` remains the input contract and can rebuild the entire engine index.
2. The engine stores only the approved public search projection; raw Claims/Evidence/backend IDs are out of scope.
3. SDA ID is the document identity.
4. Search text is normalized by SDA before query construction.
5. Stemming is not enabled.
6. Typo tolerance is disabled for the trial.
7. Token dropping is disabled for the trial.
8. Split/join fallback is disabled for the trial.
9. Infix search is disabled for the trial.
10. Filters preserve OR-within-category / AND-across-category semantics using exact facet values.
11. Typesense `_text_match` or other engine scores are not exposed as public scores.
12. Final `match_quality` and deterministic ordering remain project-owned.
13. A missing/deleted index can be rebuilt from canonical public projections; index state is never canonical evidence.
14. No semantic/vector/natural-language engine feature is authorized by this trial.

## Verification plan

The executable trial must prove at least:

- index creation from the frozen M3 projection;
- Arabic name/alias retrieval using normalized SDA queries;
- English designation/name retrieval;
- exact filter Boolean semantics;
- typo behavior does not silently expand results;
- token dropping does not silently expand multi-token queries;
- input/index order does not change public result ordering after SDA reclassification;
- optional descriptions and bilingual records round-trip safely;
- deleted/rebuilt collection returns the same public results;
- engine-only metadata and scores do not leak into `SearchResult`;
- backend Wikibase Q/P IDs do not enter the engine document;
- an alias can point the stable public collection name at a rebuilt physical collection.

## External evidence inspected

- Typesense multilingual locales: https://typesense.org/docs/guide/locale.html
- Typesense collection/schema and stemming controls: https://typesense.org/docs/30.0/api/collections.html
- Typesense search controls and filters: https://typesense.org/docs/30.0/api/search.html
- Typesense syncing and collection aliases: https://typesense.org/docs/guide/syncing-data-into-typesense.html
- Typesense production/HA: https://typesense.org/docs/guide/running-in-production.html
- Typesense backups: https://typesense.org/docs/guide/backups.html
- Typesense server repository/license: https://github.com/typesense/typesense
- Meilisearch Community/Enterprise licensing: https://github.com/meilisearch/meilisearch
- Meilisearch localized attributes: https://www.meilisearch.com/blog/meilisearch-1-10
- Meilisearch typo tolerance: https://www.meilisearch.com/blog/typo-tolerance
- Meilisearch index swapping: https://www.meilisearch.com/blog/zero-downtime-index-deployment
- OpenSearch Arabic analyzer: https://docs.opensearch.org/latest/analyzers/language-analyzers/arabic/
- OpenSearch ICU analyzer: https://docs.opensearch.org/latest/analyzers/language-analyzers/icu/
- OpenSearch aliases: https://docs.opensearch.org/latest/im-plugin/index-alias/
- OpenSearch snapshots: https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/snapshots/index/
- OpenSearch license/repository: https://github.com/opensearch-project/OpenSearch

## Claim ceiling

Passing the trial may justify Typesense for the bounded M3 public lexical/entity index role only. It will not establish final production sizing, HA topology, disaster recovery, security hardening, large-corpus Arabic relevance, fuzzy/semantic search, or the final frontend stack.
