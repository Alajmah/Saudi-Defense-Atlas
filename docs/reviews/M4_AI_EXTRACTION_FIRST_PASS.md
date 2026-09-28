# M4 Typed AI Extraction Boundary — Exhaustive First Pass

**Scope:** typed model trace/candidate bundle and cross-record authority validation before any real model/provider integration.

## Findings

### M4-AI-F01 — Extractor could collapse extraction and canonical entity resolution — FIXED

**Risk:** allowing a model to emit SDA entity IDs directly would make name recognition an implicit canonical-resolution decision.

**Fix:** extracted entity mentions use run-local `CAND-*` IDs only. Candidate Claim/Event references use those local IDs. Canonical SDA entity mapping is deferred to a later Resolver boundary.

### M4-AI-F02 — Rejected structured output could leak candidates downstream — FIXED

**Risk:** retaining candidate records alongside `validation.status=rejected` could allow a later consumer to process invalid model output accidentally.

**Fix:** rejected runs must contain validation errors and zero Evidence/Entity/Claim/Event candidates. Both JSON Schema and the cross-record validator enforce the isolation.

### M4-AI-F03 — Model execution needed an explicit claimed-queue authority gate — FIXED

**Risk:** an extractor could consume a queued, discovery-only, or restricted-human item without a claim/authorization transition.

**Fix:** cross-record validation requires the source EditorialQueueItem to be `candidate_extraction`, `claimed`, `ai_extraction_allowed=true`, and `canonical_mutation_authority=false`.

### M4-AI-F04 — Candidate references needed closure against queue/document provenance — FIXED

**Risk:** a model could cite a Document outside the queue item, invent an Evidence ID, reuse candidate IDs across record types, or reference a missing entity mention.

**Fix:** the validator requires run Documents to be a subset of queue provenance, candidate Evidence to reference those Documents, globally unique CAND IDs, and all Entity/Claim/Event evidence/entity references to resolve inside the same run.

## Areas reviewed with no unresolved blocker

- provider/model/model-version/adapter-version trace is mandatory;
- prompt template ID/version/hash is mandatory;
- input and raw-output hashes are mandatory;
- evaluator version and named check results are mandatory;
- accepted runs cannot contain failed evaluation checks;
- candidate predicates/event types reuse accepted SDA ontology vocabulary;
- no numeric model self-confidence is promoted into canonical confidence semantics;
- ambiguous extraction remains representable as candidate-review data;
- `candidate_only`, `canonical_mutation_authority=false`, and `publication_authority=false` are schema invariants;
- no actual LLM provider or orchestration technology is selected by this increment.

## Remaining bounded risks / later forcing functions

- actual model quality, false-positive rate, refusal to infer unknowns, Arabic/English extraction behavior, and restricted-detail handling require a curated evaluation corpus before any production model adoption;
- Resolver and Verifier remain separate later boundaries;
- a model-generated candidate is not evidence verification and cannot self-approve a ChangeProposal;
- durable queue claims/cancellation and distributed worker coordination remain unqualified.

## Disposition

**GO if exact-head schema-validation and continuing Wikibase regression gates pass.**

Passing this increment verifies the typed candidate-only extraction boundary only; it does not verify any model/provider or authorize canonical mutation/publication.
