# M4 Monitoring and Editorial Queue Contract

## Purpose

This contract introduces the first M4 control-plane boundary between deterministic source acquisition and later AI-assisted extraction. It does **not** select a scheduler/orchestrator and it does not grant canonical mutation authority to monitoring, routing, or models.

## Flow

```text
registered feed
  -> successful RetrievalReceipt
  -> canonical Document classification
  -> MonitoringObservation
  -> deterministic relevance/sensitivity routing
  -> exact-content dedupe group
  -> EditorialQueueItem
  -> later Extractor / human discovery review / restricted human handling
```

## Authority boundaries

- `RetrievalReceipt` records what was fetched; it does not establish a factual Claim.
- `Document` remains the canonical retrieved artifact identity.
- `MonitoringObservation` is operational metadata derived from a successful fetch plus deterministic routing rules.
- `EditorialQueueItem` is operational work state only and has `canonical_mutation_authority=false` by contract.
- Candidate extraction may produce later typed candidate Entity/Claim/Event/Evidence records, but that later output remains subordinate to existing proposal/review/revision governance.

## Deterministic routing

The reference router uses caller-owned explicit term policies. It performs no model inference.

- `unchanged` canonical content: observation retained, no new queue item.
- irrelevant content: no queue item.
- relevant A-D source material: `candidate_extraction`; AI extraction may run, but only to produce candidates.
- relevant E-class material: `discovery_review`; automated extraction is disabled in this first contract because E is discovery-only until corroborated.
- relevant material matching RED/restricted policy: `restricted_human`; automated extraction is disabled.

Relevance/sensitivity rule IDs are retained on the observation/queue record for auditability. The lexical router is a conservative baseline, not the final M4 relevance system.

## Exact-content deduplication

The first dedupe mechanism uses the canonical Document content SHA-256, not raw HTTP bytes. This preserves the M1 distinction between retrieval receipts and canonical Document identity.

Exact-content duplicates may group multiple observation/source/document IDs into one queue item while preserving every provenance identity. A stronger authoritative copy can promote an E-class discovery group into candidate extraction. Any RED observation dominates the group and routes it to restricted human handling.

Semantic/near-duplicate clustering is outside this increment and requires separate evaluation.

## Concurrency boundary

A queue item in `claimed` state cannot change routing lane in place. If new evidence requires escalation while a worker may already be processing the item, the router fails closed and requires an explicit coordination/cancellation mechanism.

This contract therefore does not solve the existing multi-writer coordination requirement and does not authorize multiple autonomous canonical mutation workers.

## Non-scope

- scheduler/orchestrator selection
- durable queue technology
- LLM provider/model selection
- semantic relevance or near-duplicate detection
- model extraction
- entity resolution
- evidence verification
- canonical mutation
- autonomous publication
- operationally sensitive aggregation

## Next M4 increment

Define the typed AI extraction trace/candidate boundary, including provider/model/version, prompt/template version, source Document IDs, evidence locators, validation result, and evaluation metadata. That boundary will consume only `candidate_extraction` queue items and still cannot bypass `ChangeProposal -> ReviewDecision -> Revision`.
