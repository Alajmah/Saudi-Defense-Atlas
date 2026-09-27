# M3 OpenSearch Trial — Exhaustive First-Pass Review

**Date:** 2026-09-27  
**Milestone:** M3  
**Pattern:** APR-008  
**Trial:** OpenSearch 3.8.0 downstream lexical index  
**Review scope:** ADR-0004, `spikes/opensearch/`, CI workflow, and equivalence with the accepted M3 `SearchDocument` / `SearchQuery` / `SearchResult` lexical contract.

## Review disposition

**PASS after remediation.** No unresolved blocker remains for promoting OpenSearch only to the bounded M3 lexical-index role documented in ADR-0004.

This review does not qualify production security, HA, backup/recovery, upgrades, capacity, semantic/vector relevance, deployment topology, or final frontend architecture.

## Findings

### M3-OS-F01 — Additive engine scores could violate portable quality ordering — FIXED

The initial trial used multiple overlapping scored clauses. A record could match more than one clause, making aggregate `_score` an accidental authority over the project-owned quality order.

**Risk:** `exact_id > exact_name > exact_alias > prefix > token` could be violated even while a small happy-path fixture still passed.

**Remediation:** the hardened trial wraps each quality class in fixed `constant_score` tiers and combines them with `dis_max` / `tie_breaker: 0.0`. `_score` remains engine-internal; the tier values only implement the already-accepted project ordering.

**Regression:** a synthetic collision query makes one record an exact canonical-ID match and another an exact alias match with alphabetically favorable display text. The exact-ID record must rank first.

### M3-OS-F02 — Tie-breaking was not locale-aware — FIXED

The initial engine projection carried one sort name with English preference. The deterministic SDA oracle instead sorts ties by the query-resolved locale, then SDA ID.

**Risk:** Arabic queries with equal match quality could return a different ordering from the accepted public contract.

**Remediation:** indexed trial records now carry `sort_name_ar` and `sort_name_en`, each following the same fallback semantics as the reference contract. The query selects the sort field from `resolve_query_locale()`.

**Regression:** paired synthetic Arabic records intentionally reverse their English ordering; the Arabic query must follow Arabic display ordering.

### M3-OS-F03 — Pre-index SearchDocument validation was implicit — FIXED

The first trial built its own documents through `build_search_document()`, but did not make the admission boundary explicit immediately before indexing.

**Risk:** a future adapter could treat the OpenSearch mapping as sufficient validation and admit stale or malformed search projections.

**Remediation:** the complete trial fixture set is passed through the deterministic SDA reference boundary before any record is projected into OpenSearch. This validates runtime document structure, normalized-term integrity, facet shape, and duplicate canonical IDs before indexing.

## Areas reviewed with no unresolved finding

- OpenSearch remains a downstream index and never becomes canonical truth.
- SDA canonical IDs remain public/domain identity; no Q/P backend IDs are accepted in indexed trial payloads or returned IDs.
- OR-within-facet and AND-across-facets semantics match the deterministic oracle for the tested contract.
- whole-token semantics do not degrade into substring matching (`air` does not match unrelated `chair`).
- reverse indexing order produces the same portable ordering.
- engine results are compared to the oracle for both ordered SDA IDs and portable `match_quality`.
- Arabic orthographic folding remains SDA-owned for baseline lexical behavior.
- the characterized OpenSearch Arabic analyzer is separate from baseline semantics and contains no Arabic stop-word or stemmer filter.
- `_analyze` output is checked for Arabic normalization and decimal-digit conversion.
- the Docker image is pinned to OpenSearch 3.8.0 and the runtime version is asserted.
- security-disabled configuration is confined to the ephemeral trial/CI boundary.
- fuzzy matching, stemming, semantic/vector retrieval, generated transliteration, and engine-specific public scores remain outside the accepted scope.

## Verification evidence

Hardened implementation head before governance promotion:

- `5372d7642b945cddfbd240b1c294b4ce77ed4d5f`
- schema-validation run `36326666973` (#464) — **PASS**
- opensearch-verification run `36326666946` (#10) — **PASS**
- trial evidence uploaded by the workflow as `m3-opensearch-trial-evidence`

## Promotion recommendation

Promote APR-008 to **ACCEPTED / VERIFIED** only for the bounded M3 downstream lexical-index role exercised by this trial.

Retain explicit forcing functions for a new decision before production qualification, semantic/vector search, fuzzy matching, additional analyzers, or material changes to ranking semantics.
