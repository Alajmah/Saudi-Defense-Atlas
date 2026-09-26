# M3 Search Contract — Exhaustive First-Pass Review

**FIRST-PASS REVIEW COMPLETE**

- review date: 2026-09-26
- milestone: M3
- review surface: `SearchDocument` / `SearchQuery` / `SearchResult`, deterministic normalization/reference matcher, CI validators, and `docs/M3_SEARCH_CONTRACT.md`
- implementation/review head before this frozen record: `3635243bef2dfc048c97ed3bcf8ba7949eee9a2d`
- authority: `docs/ROADMAP.md` M3 immediate sequence — define search/query contract before selecting a search engine

## Objective reviewed

Establish a backend-neutral public lexical/entity search contract that is Arabic-aware enough to support the first M3 acceptance slice, while refusing to select or imply a search engine, vector store, stemming system, fuzzy matcher, or semantic-retrieval mechanism before separate evidence and APR review.

## Review map

Reviewed:

- query shape and capability ceiling;
- search-document admission and public-field boundary;
- canonical/store identity separation;
- Arabic/Unicode normalization behavior;
- explicit alias handling;
- compact designation handling;
- token/prefix/exact semantics;
- facet validation and Boolean semantics;
- result ranking/portable metadata;
- malformed input behavior;
- optional fields;
- deterministic ordering;
- CI/regression integration;
- operational-sensitivity boundary;
- future technology-adoption boundary.

Not claimed/reviewed as implemented:

- production relevance quality;
- Arabic morphology/stemming;
- fuzzy matching;
- generated synonyms/transliterations;
- semantic/vector search;
- production search-engine operations, HA, backups, scaling, or deployment;
- final frontend search UX.

## Findings register

### M3-SC-F01 — Python query/filter boundary was initially looser than the JSON Schema

- **Area:** interface correctness / fail-closed behavior
- **Finding:** the first reference implementation consumed known filter keys but did not reject unknown keys, string-valued arrays, duplicates, or undeclared top-level query options itself.
- **Evidence:** initial `_filters_match` used `.get()` without an exact query/filter-shape validator.
- **Why it matters:** callers could observe behavior that the normative schema would reject, creating two contracts and making adapter conformance ambiguous.
- **Severity:** high
- **Confidence:** high
- **Resolution:** fixed. The service now requires the exact v0.1 query/filter key set, validates array types/duplicates/entity-type vocabulary, enforces the 256-character query ceiling, and rejects undeclared options such as a silent `semantic` flag.
- **Verification:** `validate_m3_search_contract_isolation.py` exercises unknown, string-valued, duplicate, extra, and overlong inputs.

### M3-SC-F02 — `token` initially meant substring containment rather than whole lexical token membership

- **Area:** search correctness
- **Finding:** the initial token path tested `token in combined_string`, so a query such as `air` could match unrelated text containing those characters inside a larger word.
- **Evidence:** initial `_match_document` constructed joined strings and used substring membership.
- **Why it matters:** this would inflate recall with false positives and make the portable `match_quality="token"` label semantically misleading.
- **Severity:** high
- **Confidence:** high
- **Resolution:** fixed. Normalized terms are split on whitespace/hyphen boundaries and query tokens must be a subset of the resulting whole-token set.
- **Verification:** isolation fixture proves `air` does not match `Chair System` while the exact name still resolves correctly.

### M3-SC-F03 — Search projector initially depended on downstream JSON Schema to reject invalid Entity/alias vocabulary

- **Area:** projection boundary / contract consistency
- **Finding:** the initial projector accepted any non-empty `entity_type` and passed alias metadata through without validating `kind` or unknown alias fields.
- **Evidence:** initial `build_search_document` and `_aliases` checked shape only partially.
- **Why it matters:** a service call could emit a schema-invalid search document and defer failure to an optional later validation stage.
- **Severity:** medium-high
- **Confidence:** high
- **Resolution:** fixed. The projector now enforces the v0.1 Entity type set, alias-kind vocabulary, localized-field keys, alias-field keys, subtype type, Revision IDs, and facet shape directly.
- **Verification:** adversarial tests reject unknown entity types and generated/undeclared alias kinds.

### M3-SC-F04 — Compact designation folding was initially applied to arbitrary description prose

- **Area:** normalization precision / index hygiene
- **Finding:** the first `_normalized_variants` implementation generated no-separator compact variants for any ASCII-containing text, including long descriptions.
- **Evidence:** descriptions called the same compacting helper used for designations.
- **Why it matters:** this invents unnatural searchable strings, bloats the index projection, and can create surprising prefix/exact behavior unrelated to a real name or designation.
- **Severity:** medium
- **Confidence:** high
- **Resolution:** fixed. Compact variants are bounded and enabled only for canonical IDs, names, and aliases; description prose receives ordinary normalized text only.
- **Verification:** isolation test rejects the appearance of a concatenated description phrase.

### M3-SC-F05 — Test helper initially represented an absent optional description as `{}`

- **Area:** test correctness
- **Finding:** the first fixture helper emitted `descriptions: {}` when no description was supplied, which is not a valid `localized_text` object.
- **Evidence:** helper used `descriptions or {}`.
- **Why it matters:** the test would not actually cover the legitimate optional-description case and could mask confusion between “missing” and “empty localized value.”
- **Severity:** low
- **Confidence:** high
- **Resolution:** fixed. The property is omitted on the source Entity when unknown, and the search projection explicitly emits `descriptions: null`.
- **Verification:** main M3 validator schema-validates the no-description Entity and resulting SearchDocument.

## Areas reviewed with no material issue found

- **Canonical identity:** SearchDocument and SearchResult expose SDA IDs; backend identifiers are neither indexed nor returned.
- **Authority boundary:** facets are explicit inputs from approved projections; the search layer does not infer manufacturer/service/status/country from raw Claims.
- **Normalization sovereignty:** canonical/display strings remain unchanged; folded strings are projection-only.
- **Arabic conservatism:** diacritic/tatweel/alef/alif-maqsura/digit/dash folding is explicit; taa-marbuta/haa merging, article stripping, stemming, and transliteration are intentionally absent.
- **Capability honesty:** schemas and docs do not claim fuzzy or semantic behavior.
- **Scoring portability:** no numeric engine score is exposed as a cross-engine public semantic.
- **Facet logic:** OR within a facet category and AND across categories is explicit and testable.
- **Record admission:** v0.1 indexes active Entity records only rather than guessing redirect behavior for merged/deprecated records.
- **Determinism:** reference ordering is independent of input document ordering.
- **Sensitive-data boundary:** the contract indexes only public projection fields and does not create a path for raw/private/restricted ingestion content.

## Open questions / deferred forcing functions

1. Which engine/analyzer best satisfies this contract on a representative Arabic/English entity corpus?
2. Whether Arabic stemming/morphological analyzers improve useful recall without unacceptable false positives.
3. Whether fuzzy matching is required for real user misspellings and model/designation variants.
4. Whether semantic/vector retrieval materially improves discovery beyond explicit aliases and lexical search.
5. How merged/deprecated Entity IDs should behave in public search (hidden, redirect hit, historical result, or another explicit state).
6. Production ranking evaluation metrics and a representative query relevance set.
7. Index refresh/deletion mechanics and production operational topology.

These are not silently resolved by this increment.

## Missing evidence

- representative production-scale Arabic/English query corpus;
- measured relevance/latency/resource behavior of candidate engines;
- user search logs or relevance judgments;
- evidence supporting any specific Arabic morphology, fuzzy, or semantic mechanism.

## First-pass disposition

The reviewed contract is suitable to proceed to CI/adversarial verification as the **engine-neutral M3 search baseline** after findings M3-SC-F01 through M3-SC-F05 were corrected.

No search engine or semantic mechanism is promoted by this review.
