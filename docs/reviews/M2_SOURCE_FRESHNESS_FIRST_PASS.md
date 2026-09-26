# M2 Registered-Feed Acquisition Freshness — Exhaustive First-Pass Review

## Review Surface

Reviewed increment: receipt-based acquisition freshness introduced by PR #7.

Scope reviewed:

- `services/ingestion/acquisition.py` retrieval receipt extension
- `services/presentation/source_freshness.py`
- `schemas/v0.1/source-freshness-report.schema.json`
- `scripts/validate_m2_source_freshness.py`
- M1 ingestion invariants around unchanged canonical content
- M2 source/claim staleness semantic boundaries

Explicitly out of scope:

- scheduling/orchestration technology
- receipt persistence backend
- source-authority changes
- Claim truth/re-verification decisions
- failed-fetch retry policy
- frontend visualization

## Required Invariants

1. Monitoring freshness must measure acquisition observations, not canonical Document version creation.
2. An unchanged re-fetch must refresh monitoring health without rewriting immutable Document identity/metadata.
3. Monitoring scope must be a registered feed, not an entire publisher Source.
4. Checking one feed must not mark sibling feeds under the same Source fresh.
5. Only successful retrieval receipts count as positive acquisition-health evidence.
6. Polling windows are explicit caller-supplied policy, never model-generated defaults hidden in the projector.
7. `due` means another acquisition check is due; it does not mean content or Claims are stale, unreliable, or false.
8. Inactive Sources are outside the active monitoring workload.
9. Unknown/mismatched Source/feed identities and future observations fail closed.
10. Output is deterministic under input ordering and equivalent timezone representations.

## Findings Register

### M2-SF-F01 — Document timestamps cannot represent monitoring freshness

**Area:** acquisition semantics

**Finding:** The initial implementation derived source freshness from `Document.retrieved_at`.

**Why it matters:** M1 intentionally keeps Document identity immutable when canonical content is unchanged. A successful re-fetch may produce a new RetrievalReceipt while retaining the original Document and its original `retrieved_at`. Using Documents would therefore report a regularly checked feed as overdue.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Freshness is now derived from successful `RetrievalReceipt.observed_at`. Integration validation proves an unchanged re-fetch refreshes monitoring health while the canonical Document remains unchanged.

---

### M2-SF-F02 — Source-level freshness overstates coverage when a Source has multiple feeds

**Area:** monitoring scope

**Finding:** The first receipt-based design aggregated observations only by `source_id`. A single checked feed could therefore mark an entire publisher Source fresh while another registered feed had never been checked.

**Why it matters:** Large official publishers can expose multiple independently monitored pages/feeds. Source-level aggregation would create a false acquisition-coverage signal.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. `RetrievalReceipt` now carries both `source_id` and `document_key`; the report evaluates each registered feed independently. Regression coverage includes two feeds under one Source and proves that a checked feed does not refresh its never-retrieved sibling.

---

### M2-SF-F03 — Receipt attribution was insufficient for feed-level monitoring

**Area:** provenance / compatibility

**Finding:** M1 RetrievalReceipt originally recorded URLs/timestamp/raw hash but not canonical Source/feed identity.

**Why it matters:** Monitoring health should not infer identity from URLs after redirects or from Document creation, especially when no new Document is produced.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Receipts are explicitly attributed with `source_id` and `document_key` from the validated `SourceAcquisitionPolicy`. The M2 integration test exercises the actual M1 `classify_fetch()` path and validates those fields.

---

### M2-SF-F04 — Failed attempts must not be mistaken for successful freshness evidence

**Area:** failure semantics

**Finding:** A monitoring report needs a clear definition of what observation refreshes health.

**Why it matters:** Treating HTTP failures as successful checks would hide acquisition outages.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED FOR THIS CONTRACT. Positive freshness accepts only successful HTTP-200 retrieval receipts. A non-200 receipt supplied to the projector fails closed. Persistence/reporting of failed acquisition attempts remains a separate future observability concern.

## Failure and Trust Review

The projector rejects:

- duplicate Source IDs;
- duplicate registered feed keys;
- feeds referencing unknown Sources;
- polling policy entries for unknown feeds;
- receipts referencing unknown feeds;
- receipts whose Source does not match the registered feed;
- non-200 receipts presented as successful retrieval evidence;
- future receipt timestamps;
- timezone-naive/malformed timestamps;
- invalid polling windows.

Inactive Sources and their feeds are excluded from the active workload. A registered active feed with no successful receipt is represented explicitly as `never_retrieved`.

## Areas Reviewed With No Material Issue Found

- Exact polling deadline semantics use `as_of >= due_at`.
- Equivalent timezone forms normalize to UTC `Z`.
- Reordering Sources, feeds, or receipts does not change output.
- Receipt observations remain distinct from canonical Document identity/versioning.
- No mutation authority is introduced by this report.
- Source class is presented as metadata; freshness does not alter evidentiary authority.
- No operational military data is introduced.

## Deferred / Non-Blocking Work

1. Failed acquisition attempts/outage history should eventually have a separate observability record rather than being encoded as successful RetrievalReceipts.
2. Poll scheduling remains outside this projector and requires an orchestration decision later.
3. RetrievalReceipt persistence/retention is not selected in this increment.
4. Production feed-specific polling windows remain an editorial/operations policy decision.

## First-Pass Judgment

After fixes M2-SF-F01 through M2-SF-F04, no first-pass merge-blocking defect remains. Merge is gated on exact-head schema validation and Wikibase regression workflows.
