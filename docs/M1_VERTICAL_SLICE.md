# M1 — F-15SA First Vertical Slice

## Status

**Phase:** implementation started

**Target:** one authoritative public source → provenance records → typed proposal → review-gated Wikibase mutation → bilingual public projection.

## Selected source

### Publisher

United States Air Force / Air Force Life Cycle Management Center Public Affairs.

### Document

**AFLCMC delivers final F-15SA to Royal Saudi Air Force**

Canonical URL:

`https://www.af.mil/News/Article-Display/Article/2444558/aflcmc-delivers-final-f-15sa-to-royal-saudi-air-force/`

The source is classified **A — Primary / Official** under `docs/SOURCE_POLICY.md`.

## Why this slice

The document is useful without requiring sensitive operational detail. It can support a compact but meaningful graph around:

- F-15SA equipment variant;
- F-15 family relationship;
- Royal Saudi Air Force operator relationship;
- Boeing manufacturer context;
- dated final-delivery event;
- source/document/evidence provenance;
- Arabic/English public projection.

The vertical slice must not infer current aircraft location, readiness, sortie generation, unit disposition, or other operational state beyond what approved evidence explicitly establishes.

## Source-supported facts targeted for extraction

The implementation may propose only facts supported by bounded evidence from the document. Initial target facts are:

1. the document was published on 2020-12-11;
2. it reports final F-15SA aircraft delivery on 2020-12-10;
3. the recipient/operator named in the release is the Royal Saudi Air Force;
4. it describes F-15SA as an advanced version of the F-15S;
5. it identifies Boeing as producer of the delivered aircraft.

These are candidate claims/events until admitted through the project governance path.

## M1 implementation order

### Increment A — deterministic acquisition

Before AI extraction:

- register the publisher/source;
- allowlist the exact source host;
- fetch bytes through an explicit source adapter;
- record final/retrieved URL;
- hash the response body with SHA-256;
- issue a deterministic SDA Document ID from source-document key + content hash;
- avoid duplicate Document creation for identical content;
- create a new Document version if the content changes;
- retain immutable retrieval/output metadata.

### Increment B — bounded parsing and evidence

- parse only the required page fields/text sections;
- create explicit Evidence locators;
- do not treat whole-document presence as evidence for every claim;
- preserve extraction uncertainty.

### Increment C — proposal generation

- deterministic extraction where possible;
- AI extraction may be added only behind typed schemas;
- output ChangeProposal rather than canonical writes;
- bind review decisions to exact proposal payload hashes.

### Increment D — canonical adapter

Before generalizing Wikibase mutation:

- derive an idempotency key from backend + proposal identity/hash + intended effect;
- detect an already-observed equivalent effect;
- distinguish `not_attempted`, `applied`, `failed`, and `effect_unknown`;
- never blindly retry `effect_unknown`;
- reconcile by reading backend state using SDA claim/entity identifiers;
- record backend receipts only after an authorized attempt.

### Increment E — public projection

- read by SDA canonical identity through a project-owned adapter;
- render Arabic and English from the same canonical records;
- show citations/evidence for material facts;
- expose delivery as a dated event rather than a timeless inventory scalar;
- avoid an independent CMS copy of factual truth.

## First-pass review surface

The M1 vertical slice will be reviewed across:

- source allowlisting and redirect handling;
- byte/content identity;
- repeated retrieval and changed-content semantics;
- Source / Document / Evidence boundaries;
- parser failure and page-structure drift;
- entity resolution ambiguity;
- proposal schema validity;
- human/system authorization rules;
- exact proposal-hash binding;
- backend idempotency and ambiguous effects;
- Wikibase adapter/domain identity separation;
- bilingual rendering from one canonical record set;
- citation completeness;
- restricted operational-detail filtering;
- test reproducibility and network-independent CI fixtures.

## Initial claim ceiling

Increment A may establish only deterministic acquisition/versioning mechanics. It does not establish factual extraction correctness, production crawler resilience, or canonical admission.

Each later increment must expand the claim ceiling only after its own evidence exists.
