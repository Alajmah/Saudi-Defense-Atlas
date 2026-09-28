# M4 Editorial Audit and Daily Brief — Exhaustive First Pass

**Baseline reviewed:** PR #26 head `8bc6a20f273f5aca5f841b6c1934359842559ab1` before first-pass remediation.

**Scope:** deterministic M4 `EditorialAuditReport` and `EditorialDailyBrief` contracts over Claim staleness, registered-feed acquisition freshness, and editorial queue state. The increment must remain operational/editorial metadata only: no truth, approval, canonical-mutation, or publication authority.

## Review surface

The first pass independently examined:

- the two new JSON Schemas and their authority/status semantics;
- `services/intelligence/editorial_audit.py` control flow, content addressing, ordering, failure behavior, and `as_of` handling;
- the validator and CI integration;
- upstream `build_staleness_report` and `build_source_freshness_report` semantics;
- `EditorialQueueItem` schema and `editorial_routing` merge/state behavior;
- cross-record identity, provenance, temporal, and actionability boundaries;
- deterministic replay and malformed/tampered input behavior;
- scope exclusions: no scheduler, LLM, dashboard framework, second truth store, canonical write, or publication path.

## First-pass findings register

### M4-AUD-F01 — Daily brief loses registered-feed identity

**Area:** projection / source-monitoring actionability  
**Finding:** `EditorialAuditReport` correctly retains `feed_key` inside each source-monitoring finding context, but `EditorialDailyBrief` reduces findings to `finding_id`, `kind`, `priority`, `subject_id`, and `reason_codes`. The source-monitoring `subject_id` is the Source ID, not the feed key. If one Source owns multiple registered feeds, two due/never-retrieved actions can therefore become indistinguishable in the brief except for opaque finding IDs.  
**Evidence:** source freshness is defined per registered `feed_key`; audit finding context preserves that key; `build_daily_editorial_brief` drops the context entirely.  
**Why it matters:** the daily brief is the editor-facing action projection. A source-level label is insufficient to identify which registered feed must be checked when a source has multiple feeds.  
**Severity:** MEDIUM  
**Confidence:** HIGH  
**Recommended verification:** add a multi-feed/same-source regression and require the brief to retain action context, including `feed_key` for source-monitoring findings.

### M4-AUD-F02 — Content-address integrity can accept a semantically invalid audit report

**Area:** integrity / fail-closed validation  
**Finding:** `_validate_audit_report_integrity` validates authority, unique/content-addressed finding IDs, summary consistency, and report ID, but it does not validate the finding contract itself (`kind`, `priority`, `subject_id`, `reason_codes`, `context`) or top-level `as_of` / `input_sha256` semantics before projecting the brief. A malformed report can be modified and re-content-addressed consistently, pass this integrity function, and cause `build_daily_editorial_brief` to emit an object that does not satisfy the daily-brief schema.  
**Evidence:** the integrity function derives hashes from whatever finding body it receives and `_summary` silently counts only known values; the brief copies unvalidated `kind`/`priority`/`reason_codes`.  
**Why it matters:** content identity proves that bytes were not changed relative to an ID; it is not semantic validity. The brief boundary should fail closed rather than conflate these two properties.  
**Severity:** MEDIUM  
**Confidence:** HIGH  
**Recommended verification:** construct a self-consistent, re-hashed report with an invalid priority/kind and prove the brief rejects it before rendering.

### M4-AUD-F03 — Queue state is not provably aligned to the audit `as_of` boundary

**Area:** temporal integrity / operational snapshot semantics  
**Finding:** staleness and source-freshness inputs each carry and validate their own `as_of`, but queue input is passed as a bare sequence of mutable `EditorialQueueItem` records. The auditor checks only `created_at <= as_of`. Queue items can later change state, lane, priority, reason codes, and merged provenance while retaining the original `created_at`; no queue snapshot timestamp is supplied to the auditor. A current queue record can therefore be used to construct a report for an earlier `as_of` even though its current state did not exist then.  
**Evidence:** `editorial_routing.route_observation` merges into an existing queue item without changing `created_at`; `EditorialQueueItem` has no update/transition timestamp; the new auditor accepts `queue_items` plus `as_of` and has no independently aligned queue snapshot boundary.  
**Why it matters:** a content-addressed operational report must not imply historical state by reconstructing it from current mutable state. This is the same historical-integrity class guarded elsewhere in SDA architecture.  
**Severity:** HIGH  
**Confidence:** HIGH  
**Recommended verification:** make queue snapshot time explicit and require it to equal the audit `as_of`; document that the increment qualifies contemporaneously captured queue snapshots, not historical reconstruction from current queue state.

## Open questions / bounded uncertainties

- The current queue contract has no transition timestamp. This PR should not silently broaden into a full queue-history/event-sourcing design; the minimum acceptable remediation is an explicit contemporaneous snapshot boundary and a corresponding claim ceiling.
- Upstream staleness and source-freshness reports are deterministic builders rather than separately content-addressed records. The audit input digest is sufficient for this increment provided their exact payloads remain part of the digest.

## Areas reviewed with no issue found

- staleness is treated as review due, never as factual falsity;
- acquisition due/never-retrieved is treated as monitoring attention, never as evidence that source content changed;
- completed/dismissed queue items are suppressed;
- disputed/unverified Claims and never-retrieved A/B feeds receive deterministic priority rather than model judgment;
- finding/report/brief IDs are deterministic content-addressed identities;
- audit and brief authority objects explicitly deny truth, approval, canonical mutation, and publication authority;
- no canonical records are mutated by this module;
- queue input order does not change the generated report;
- CI executes the new validator and existing Wikibase regression remains independent;
- no LLM, scheduler, orchestrator, dashboard framework, alerting channel, or second truth store is selected by this increment.

## FIRST-PASS REVIEW COMPLETE

**Known findings:** M4-AUD-F01, M4-AUD-F02, M4-AUD-F03.  
**Suspected findings:** none beyond the bounded uncertainties above.  
**Areas considered sound:** authority separation, deterministic classification/ordering, action-class ceiling, content-addressed identities, completed-item suppression, CI integration.  
**Areas requiring deeper verification after remediation:** multi-feed source action identity, semantic fail-closed brief validation, and explicit queue snapshot / `as_of` alignment.

This baseline is intentionally frozen before any second-review or remediation pass.