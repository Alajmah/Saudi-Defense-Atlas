# M4 Editorial Review Packet — First-Pass Review

## Scope

Review of the deterministic human-review handoff joining EditorialQueueItem, accepted AIExtractionRun, AIResolutionVerificationRun, and one exact AMBER ChangeProposal.

## Findings

### ERP-F01 — Proposal ID was not revalidated against proposal content — FIXED

A packet could bind the SHA-256 of a changed proposal payload while retaining the original resolver-generated proposal ID. That would preserve exact review hashing but lose the assertion that the resolver actually produced that payload.

**Fix:** the public packet boundary recomputes the resolver's deterministic `SDA-PROP-AI` identity from `extraction_run.id + mutations` and rejects any payload whose ID no longer matches.

### ERP-F02 — Standalone ambiguous/unresolved Entity candidates were absent from the editor summary — FIXED

The initial summary combined only Claim/Event blocker assessments. An Entity mention that was ambiguous or unresolved but not referenced by a Claim/Event could disappear from the review surface.

**Fix:** entity-resolution outcomes are merged into the generic blocked ambiguity/unresolved candidate lists and drive the same review flags.

### ERP-F03 — Review handoff had no temporal-order guard — FIXED

A caller could construct a review packet timestamped before the extraction, resolution, or proposal it purported to summarize.

**Fix:** queue/extraction/resolution/proposal/packet timestamps are parsed as timezone-aware values and the packet must not predate any upstream artifact. Queue creation also cannot postdate completed extraction.

### ERP-F04 — Packet identity was not content-addressed after review-summary enrichment — FIXED

Adding or changing review-visible blocker context could otherwise preserve an ID derived only from upstream IDs/hash.

**Fix:** final packet ID is recomputed from the complete packet payload after enrichment.

## Reviewed with no blocking issue found

- full queue/extraction/proposal document-set equality prevents silent multi-source context loss;
- proposal remains AMBER + human_review_required;
- Evidence mutations are constrained to extraction source documents;
- Claim/Event Evidence references must resolve to Evidence created by the exact proposal;
- conflicts, possible duplicates, policy blocks, unresolved and ambiguous candidates remain visible;
- the packet has no approval, canonical-mutation, or publication authority;
- no ReviewDecision or backend effect is created by this layer.

## Claim ceiling

This increment creates a review artifact only. Human decision capture, canonical mutation/reconciliation, Revision creation, concurrent-writer coordination, and publication remain separate authority/effect steps.
