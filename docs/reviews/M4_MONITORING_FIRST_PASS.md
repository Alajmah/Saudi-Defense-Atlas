# M4 Monitoring / Editorial Queue — Exhaustive First Pass

**Scope:** PR #18 first M4 increment: `RetrievalReceipt/Document -> MonitoringObservation -> deterministic routing/dedupe -> EditorialQueueItem`.

**Review rule:** This review was performed before accepting any scheduler, queue backend, or model-dependent mechanism. The queue/control plane is evaluated as operational metadata only and may not acquire canonical knowledge authority.

## Findings

### M4-MON-F01 — Source class alone could implicitly authorize AI extraction — FIXED

**Risk:** Treating every relevant A-D source as extraction-eligible would make AI processing default-on at publisher class level, even when a specific feed had not been reviewed for sensitivity/scope.

**Fix:** AI extraction is now explicit per `source_id|document_key` in the routing policy. Non-allowlisted relevant feeds route to `discovery_review`; E-class remains discovery-only regardless of allowlist configuration; RED always disables extraction.

**Regression:** main routing validator checks explicitly allowlisted, non-allowlisted, E-class, and RED paths.

### M4-MON-F02 — Routing decision lacked durable policy/version identity — FIXED

**Risk:** Rule IDs alone were insufficient to reconstruct which routing policy version produced an observation after policies evolve.

**Fix:** `RoutingPolicy.policy_id` is mandatory and is stored as `MonitoringObservation.routing_policy_id`; queue reason metadata retains the policy identity through the observation/queue chain.

**Regression:** observation schema and validator require/check policy identity.

### M4-MON-F03 — Source/Receipt/Document cross-record integrity was incomplete — FIXED

**Risk:** A manually constructed or corrupted ingestion result could bind a Receipt for one Source to a Document belonging to another, contaminating routing/provenance.

**Fix:** observation construction requires Source ID = Receipt source ID = Document source ID, requires an HTTP 200 successful receipt, a non-empty registered document key, and valid raw/canonical SHA-256 fingerprints.

**Regression:** isolation validator rejects Document/Source mismatch and non-success receipts.

### M4-MON-F04 — Claimed queue item could be escalated while a worker may already be processing it — FIXED

**Risk:** An exact-content duplicate newly classified RED could mutate an already claimed `candidate_extraction` item in place while an extractor still holds the previous authority/state.

**Fix:** routing lane changes on `claimed` items fail closed and require a later explicit coordination/cancellation mechanism. Completed/dismissed items also cannot absorb new observations.

**Regression:** isolation validator asserts claimed-item escalation is rejected.

## Areas reviewed with no unresolved blocker

- `unchanged` canonical content does not re-enter the queue;
- irrelevant content does not enter the queue;
- exact-content dedupe uses canonical Document SHA-256 rather than raw response bytes;
- exact duplicates retain all observation/source/document provenance IDs;
- RED routing dominates unclaimed duplicate groups and disables extraction;
- queue schema hard-codes `canonical_mutation_authority=false`;
- `candidate_extraction` is candidate authority only and does not bypass existing `ChangeProposal -> ReviewDecision -> Revision` governance;
- lexical relevance/sensitivity matching is explicitly a conservative deterministic baseline, not a claim of semantic completeness;
- semantic/near-duplicate grouping, durable queue technology, scheduler/orchestrator, and model selection remain out of scope.

## Remaining bounded risks / later forcing functions

- deterministic RED terms cannot prove complete semantic sensitivity detection; later extraction/sensitivity boundaries must remain fail-closed and policy-governed;
- no durable claim/lease/cancellation protocol is selected yet;
- existing project-wide concurrent-writer coordination remains unresolved and must be solved before multiple automated canonical mutation workers;
- no LLM extraction quality claim is made by this increment.

## Disposition

**GO for merge if exact-head schema-validation and continuing Wikibase regression gates pass.**

Successful verification qualifies only the deterministic monitoring/editorial-routing contract. It does not qualify production orchestration, AI extraction, distributed queue concurrency, or autonomous publication/mutation.
