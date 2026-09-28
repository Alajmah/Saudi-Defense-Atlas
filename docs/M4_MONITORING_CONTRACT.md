# M4 Monitoring and Editorial Queue Contract

## Purpose

This contract introduces the first M4 control-plane boundary between deterministic source acquisition and later AI-assisted extraction. It does **not** select a scheduler/orchestrator and it does not grant canonical mutation authority to monitoring, routing, or models.

## Flow

```text
registered feed
  -> successful RetrievalReceipt
  -> canonical Document classification
  -> MonitoringObservation
  -> versioned deterministic routing policy
  -> exact-content dedupe group
  -> EditorialQueueItem
  -> later Extractor / human discovery review / restricted human handling
```

## Authority boundaries

- `RetrievalReceipt` records what was fetched; it does not establish a factual Claim.
- `Document` remains the canonical retrieved artifact identity.
- `MonitoringObservation` is operational metadata derived from a successful fetch plus deterministic routing rules.
- every observation records `routing_policy_id` so the routing decision can be reproduced/audited.
- `EditorialQueueItem` is operational work state only and has `canonical_mutation_authority=false` by contract.
- Candidate extraction may produce later typed candidate Entity/Claim/Event/Evidence records, but that later output remains subordinate to existing proposal/review/revision governance.

## Deterministic routing

The reference router uses caller-owned explicit term policies. It performs no model inference. RED/restricted terms are mandatory in a valid policy.

- `unchanged` canonical content: observation retained, no new queue item.
- irrelevant content: no queue item.
- relevant material from an explicitly AI-extraction-allowlisted `source_id + document_key` feed, with Source class A-D and no RED match: `candidate_extraction`.
- relevant material from a feed not explicitly allowlisted for AI extraction: `discovery_review`.
- relevant E-class material: `discovery_review` regardless of feed configuration; automated extraction is disabled because E remains discovery-only until corroborated.
- relevant material matching RED/restricted policy: `restricted_human`; automated extraction is disabled.

AI extraction is therefore **feed-opt-in**, not inferred from Source class alone. `MonitoringObservation.ai_extraction_eligible` records the deterministic decision. Relevance/sensitivity rule IDs and policy identity are retained for auditability. The lexical router is a conservative baseline, not a claim of complete semantic/sensitivity classification.

## Exact-content deduplication

The first dedupe mechanism uses the canonical Document content SHA-256, not raw HTTP bytes. This preserves the M1 distinction between retrieval receipts and canonical Document identity.

Exact-content duplicates may group multiple observation/source/document IDs into one queue item while preserving every provenance identity. An explicitly allowlisted authoritative copy can promote a discovery-only exact-content group into candidate extraction. Any RED observation dominates an unclaimed group and routes it to restricted human handling.

Semantic/near-duplicate clustering is outside this increment and requires separate evaluation.

## Concurrency boundary

A queue item in `claimed` state cannot change routing lane in place. If new evidence requires escalation while a worker may already be processing the item, the router fails closed and requires an explicit coordination/cancellation mechanism.

This contract therefore does not solve the existing multi-writer coordination requirement and does not authorize multiple autonomous canonical mutation workers.

## Fail-closed integrity

The reference implementation rejects:

- Source/Receipt identity mismatch;
- Document/Source identity mismatch;
- non-success retrieval receipts;
- missing RED/restricted routing policy;
- malformed/duplicate queue identity arrays;
- queue records that claim canonical mutation authority;
- extraction authority inconsistent with the queue lane;
- lane escalation of an already claimed item.

## Non-scope

- scheduler/orchestrator selection
- durable queue technology
- LLM provider/model selection
- semantic relevance or near-duplicate detection
- claim-level sensitivity classification after extraction
- model extraction
- entity resolution
- evidence verification
- canonical mutation
- autonomous publication
- operationally sensitive aggregation

## Next M4 increment

Define the typed AI extraction trace/candidate boundary, including provider/model/version, prompt/template version, source Document IDs, evidence locators, validation result, and evaluation metadata. That boundary will consume only `candidate_extraction` queue items and still cannot bypass `ChangeProposal -> ReviewDecision -> Revision`.
