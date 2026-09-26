# M1 First-Pass Review — Continued Findings

This file continues the independent M1 implementation review after the checkpoint in `M1_FIRST_PASS.md`. It does not rewrite or replace that checkpoint.

## M1-F07 — Asynchronous query indexing cannot arbitrate write recovery

**Area:** canonical mutation / backend consistency

**Finding:** WDQS is intentionally asynchronous. A successful Wikibase write can therefore be absent from SPARQL results for a short period.

**Why it matters:** If mutation reconciliation interpreted an empty WDQS result as `absent`, a timed-out write could be retried and duplicated even though the effect already exists in MediaWiki/Wikibase state.

**Severity:** Critical

**Confidence:** High

**Resolution:** FIXED in current branch; clean-stack runtime proof pending.

M1 reconciliation discovers SDA canonical IDs through current Action API/MediaWiki entity state. WDQS remains a query/read surface but is not allowed to decide whether an ambiguous mutation may be retried.

---

## M1-F08 — One SDA mutation must not expand into an unrecoverable sequence of backend writes

**Area:** canonical mutation / failure atomicity

**Finding:** A naïve Wikibase adapter would create an item, then add the SDA ID, payload hash, qualifiers, and references in separate API calls. A timeout between those calls could leave an effect that is neither absent nor semantically complete, while the generic mutation guard would still see only one project mutation.

**Why it matters:** Proposal-level no-blind-retry semantics are only meaningful if a single project mutation has one recoverable backend effect boundary.

**Severity:** Critical

**Confidence:** High

**Resolution:** FIXED in adapter design; clean-stack runtime proof pending.

For this bounded slice:

- Source, Document, Evidence, and Event each use one `wbeditentity` creation containing SDA canonical ID, exact payload hash, and mapped statements.
- The operator Claim uses one `wbeditentity` append containing its mainsnak, Claim ID, exact payload hash, time/confidence qualifiers, and Evidence reference.
- Network timeout/connection loss is classified as an ambiguous effect and is reconciled by current Action API state.
- Backend/API validation errors are treated as definitive rejection rather than retried.

---

## M1-F09 — Payload hashes alone are insufficient as a public/read projection

**Area:** canonical storage / read model

**Finding:** Exact payload hashes are necessary for equivalence checks, but a hash does not expose provenance/audit fields needed by the M1 read path.

**Why it matters:** A canonical knowledge store that can only prove a payload existed, without exposing Source/Document/Evidence/Claim/Event semantics, would force the frontend to depend on a hidden second truth copy.

**Severity:** High

**Confidence:** High

**Resolution:** PARTIALLY FIXED; public read projection still pending.

The M1 projection vocabulary now includes queryable Source/Document/Evidence fields plus creation/capture metadata, Claim state support, Event participant roles, Evidence roles, and related Claim IDs. The clean-stack adapter proof must confirm the fields required by the first public page are retrievable from Wikibase itself.

## Current verification boundary

The backend-independent schema/governance/ingestion/proposal/reconciliation/Revision suite is green. The real clean-stack Wikibase M1 adapter run is still executing and must pass before M1-F05/F06/F07/F08 can be considered runtime-verified.
