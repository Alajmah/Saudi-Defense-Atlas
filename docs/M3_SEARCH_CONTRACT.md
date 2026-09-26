# M3 Public Search Contract

## Purpose

Define the public search semantics that any future search engine/index adapter must preserve before the project selects a concrete search technology.

Search is a **derived public projection**, never a canonical truth store. SDA IDs and approved canonical/public projections remain authoritative.

## v0.1 capability ceiling

This contract provides:

- canonical SDA entity lookup;
- Arabic/English name and explicit alias lookup;
- conservative Arabic orthographic normalization;
- deterministic lexical prefix/token reference behavior;
- public filters for entity type, service, manufacturer, country, equipment class, and status;
- stable result identity and portable match-quality categories.

This contract does **not** provide or claim:

- Arabic stemming or morphological analysis;
- automatic definite-article stripping;
- fuzzy/edit-distance matching;
- generated transliteration;
- synonym generation;
- semantic/vector retrieval;
- embeddings;
- engine-specific relevance scores;
- final production ranking quality.

Those require separate evidence and, where they adopt an external mechanism, APR promotion.

## SearchDocument

A public search document contains only:

- canonical SDA `id`;
- `entity_type` / subtype;
- approved Arabic/English names;
- explicit canonical aliases;
- approved public descriptions when available;
- deterministic normalized search terms;
- explicitly supplied public facets;
- projection timestamp and Revision IDs.

It must not contain backend/store-native identifiers such as Wikibase Q/P IDs. It must not infer facets from raw Claims. Facets are supplied by an upstream approved public projection.

Only active Entity records enter this v0.1 public index. Redirect/search behavior for merged or deprecated records is deferred rather than guessed.

## Normalization semantics

Normalization is search-only. Display/canonical text is preserved unchanged.

The v0.1 fold:

- applies Unicode NFKC and case folding;
- removes Arabic tatweel and Arabic diacritics/annotation marks covered by the implementation range;
- folds alef variants `أ إ آ ٱ` to `ا`;
- folds alif maqsura `ى` to `ي`;
- maps Arabic-Indic and Eastern Arabic/Persian digits to ASCII digits;
- normalizes common Unicode dash variants to ASCII `-`;
- collapses punctuation/symbol separators and repeated whitespace.

It intentionally does **not** merge `ة` with `ه`, remove Arabic `ال`, stem words, or transliterate between scripts.

Compact designation variants are generated only for bounded ID/name/alias terms, not arbitrary description prose.

## Query/filter semantics

`locale` is `ar`, `en`, or `auto`. `auto` selects Arabic when the query contains Arabic-script code points; otherwise it selects English for display/query handling. Explicit canonical aliases remain searchable across the bilingual document.

Filters are strict and explicit:

- `entity_types`
- `service_ids`
- `manufacturer_ids`
- `country_ids`
- `equipment_classes`
- `status_values`

Within a single facet category, selected values are **OR**. Across different non-empty facet categories, conditions are **AND**.

Unknown query/filter fields, invalid types, duplicates, and undeclared semantic options fail closed.

## Reference lexical matching

The Python reference implementation is an acceptance oracle, not the production engine. Its match tiers are:

1. `exact_id`
2. `exact_name`
3. `exact_alias`
4. `prefix`
5. `token`

`token` means whole normalized tokens, not arbitrary substring matches.

Results expose `rank`, `match_quality`, and `matched_fields`. They do not expose a numeric relevance score because scoring scales are engine-specific and should not become a public semantic contract.

Future engines may improve ranking inside the same capability boundary, but must preserve canonical identity, filters, declared match behavior, public field boundaries, and capability claims.

## Security and sensitivity boundary

Search indexes only already-approved public projection fields. It must not become a convenience path for indexing excluded operational detail, raw ingestion text, hidden Evidence excerpts, unpublished Claims, backend IDs, or review-only metadata.

The existing project restriction against live operational geography, movement, readiness, patrol patterns, and stock semantics remains unchanged.

## Verification

M3 search validation must cover:

- Arabic normalization invariants and non-over-normalization;
- exact designation/name/alias matching;
- auto locale handling;
- optional descriptions;
- deterministic ranking independent of input order;
- strict filter shape and OR-within/AND-across semantics;
- whole-token behavior rather than substring leakage;
- active-record admission only;
- malformed search-document rejection;
- no backend Q/P identifier leakage;
- no invented cross-script transliteration.

## Next forcing function

Once this contract is reviewed and frozen, M3 may characterize candidate search engines/analyzers against it. Technology adoption must be based on measured Arabic/entity-search behavior and operational fit, not feature lists alone.
