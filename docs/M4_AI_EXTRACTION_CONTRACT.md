# M4 Typed AI Extraction Boundary

## Purpose

This contract defines what a future model adapter is allowed to emit after a `candidate_extraction` editorial queue item has been explicitly claimed. It does not select or invoke a model provider.

## Authority sequence

```text
claimed EditorialQueueItem
  -> model adapter
  -> AIExtractionRun
  -> schema + cross-record validation
  -> candidate review / resolver
  -> later ChangeProposal
  -> ReviewDecision
  -> canonical Revision
```

`AIExtractionRun.authority` is always `candidate_only`, with both canonical mutation and publication authority set to `false`.

## Extraction versus entity resolution

The Extractor may identify entity mentions, Claims, Events, and Evidence spans, but it may not decide canonical SDA entity identity. Extracted mentions therefore use run-local `CAND-*` IDs. Candidate Claims and Events may reference only those local entity mentions.

A later Resolver may propose mappings from `CAND-*` mentions to SDA entities; that is a separate authority boundary.

## Required trace

Every extraction run records:

- queue item ID;
- source Document IDs;
- start/completion time;
- model provider, model, model version, and adapter version;
- prompt template ID/version/hash;
- exact input hash;
- raw model-output hash;
- structural validation result;
- evaluator/validator version and named checks;
- candidate Evidence/Entity/Claim/Event records or, for rejected runs, validation errors plus bounded counts-only `rejection_diagnostics.pre_clear_candidate_counts` (per-array record counts captured before candidates were cleared; never candidate content, never raw model text). Accepted runs must not carry `rejection_diagnostics`.

## Evidence discipline

Candidate Evidence references an existing source Document and a bounded locator. Candidate Entities, Claims, and Events must link to candidate Evidence within the same run. The boundary validator rejects unresolved Evidence/entity references or Documents outside the claimed queue item's provenance.

## Rejected-output isolation

A rejected run remains auditable through model/prompt/input/output hashes and validation/evaluation errors, but it exposes **zero candidate records**. Invalid model output therefore cannot accidentally flow into Resolver or proposal generation.

## Execution gate

AI extraction may execute only when the queue item is:

- `lane = candidate_extraction`;
- `state = claimed`;
- `ai_extraction_allowed = true`;
- `canonical_mutation_authority = false`.

Discovery-only or restricted-human queue items cannot cross this boundary.

## Non-scope

- real model invocation or provider selection;
- model quality/performance claims;
- canonical entity resolution;
- corroboration or evidence verification;
- conflict reconciliation;
- ChangeProposal generation;
- canonical writes;
- public prose/publication;
- production model-hosting/security/cost controls.

## Next increment

Build the Resolver/Verifier boundary that maps candidate mentions to canonical SDA entities, compares candidate assertions with existing Claims/Events, preserves unresolved/ambiguous identity, and emits reviewable ChangeProposals without allowing the model to self-approve its extraction.
