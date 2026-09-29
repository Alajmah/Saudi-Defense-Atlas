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

---

# Remediation and Review Reconciliation

The frozen first-pass baseline above was not rewritten after remediation or second review.

## M4-AUD-F01 — CONFIRMED / FIXED

The daily brief now retains the full bounded finding `context` in each action reference. A regression uses two `never_retrieved` feeds owned by the same authoritative Source and proves both distinct `feed_key` values survive into the editor-facing `source_monitoring` section.

**Result:** feed-level acquisition actions remain actionable without changing the Source-level subject identity or creating a second source/feed truth model.

## M4-AUD-F02 — CONFIRMED / FIXED

The brief boundary now performs semantic validation in addition to content-address integrity. It validates exact field sets, date-time syntax, SHA-256 syntax, finding kind/priority, canonical-ID bounds, reason-code bounds, kind-specific context, summary keys/counts/types, and type-strict zero-authority flags before rendering.

Adversarial regressions cover:

- changed content without re-hashing;
- a re-hashed but empty `subject_id`;
- a re-hashed 129-character `subject_id`;
- a re-hashed 129-character reason code;
- a re-hashed numeric `0` substituted for JSON boolean `false` in an authority field;
- summary tampering;
- empty claim-review context;
- empty source-monitoring context;
- queue action with missing Source provenance;
- source-monitoring reason/context mismatch.

**Result:** content identity and semantic validity are no longer conflated. A self-consistent malformed report fails closed before a brief is emitted, including when its action context can no longer identify what an editor must handle.

## M4-AUD-F03 — CONFIRMED / FIXED WITH BOUNDED CLAIM CEILING

`build_editorial_audit_report` now requires an explicit `queue_snapshot_as_of`, normalizes it to UTC, and requires exact alignment with the staleness report, source-freshness report, and audit `as_of`. The snapshot timestamp is included in the exact audit input digest.

This deliberately does **not** add queue event sourcing or historical reconstruction. The qualified contract is only:

> a contemporaneously captured current queue snapshot may participate in an audit at the same `as_of` boundary.

It does not establish that current mutable queue records can reconstruct historical queue state, and it does not qualify queue transition history.

## Codex independent second review — pass 1

Codex was invoked only after the first-pass baseline was frozen. Its review of remediation head `51f16cfcae` reported one P2 issue: the semantic brief validator still needed to enforce the JSON Schema's 128-character bounds for `subject_id` and reason codes.

### Reconciliation

**CODEX CLAIM:** a self-consistent re-hashed report with an overlong subject ID or reason code could pass the semantic boundary and cause the generated brief to fail its own JSON Schema.

**OUR VERIFICATION:** confirmed independently during the post-remediation adversarial pass. The same review pass also identified a Python-specific type-strictness risk where `0 == False` and `True == 1` can make ordinary equality insufficient for JSON boolean/integer semantics.

**RESULT:** CONFIRMED and remediated. Canonical IDs and reason codes now enforce the same 128-character ceiling as the schemas, authority flags are checked with identity semantics (`is False`), summary values reject booleans masquerading as integers, and dedicated regressions cover these cases.

**Provenance:** M4-AUD-F01/F02/F03 were independently discovered in our first pass. The schema-bound subcase of F02 was independently identified during our remediation/adversarial pass and then corroborated by Codex.

## Codex independent second review — pass 2

Codex reviewed head `0ebdbab1fe` after the first remediation and reported one additional P2 hypothesis: a self-consistent re-hashed report could replace kind-specific `context` with a generic or empty object and still pass the semantic boundary, making source and queue actions non-actionable.

### Reconciliation

**CODEX CLAIM:** `source_monitoring_required` could lose `feed_key`, and queue actions could lose provenance, while remaining content-address consistent.

**OUR VERIFICATION:** CONFIRMED. The integrity boundary required only that `context` was a mapping; it did not re-derive the action contract from the finding kind. This is a real semantic-integrity subcase of M4-AUD-F02 and an actionability subcase of M4-AUD-F01.

**RESULT:** CONFIRMED and remediated. The validator now checks exact context fields per finding kind and re-derives identity linkage, reason codes, priority, enumerated state, relevant timestamps, and Source/Document provenance before a brief can be emitted. Re-hashed empty-context and provenance-loss fixtures now fail closed.

## Codex independent second review — pass 3

Codex reviewed head `e609d9845992d915c1574855fe7131c4e3158a21` and reported two additional P2 semantic-integrity findings.

### Reconciliation

**CODEX CLAIM 1:** Python's permissive `datetime.fromisoformat` accepted basic ISO forms that the JSON Schema `date-time` format rejects, while retained finding context was copied unchanged into the brief.

**OUR VERIFICATION:** CONFIRMED. A self-consistent re-hashed queue finding using `20260115T000000+0000` passed the old runtime parser but would produce a schema-invalid brief.

**RESULT:** CONFIRMED and remediated. Runtime date-time admission now requires the RFC 3339 shape accepted by the public schemas before parsing, while preserving timezone normalization. A dedicated re-hashed basic-ISO regression fails closed.

**CODEX CLAIM 2:** claim-review context validated the presence of `review_due_at` but did not re-derive whether the deadline was actually due or fresh at audit `as_of`.

**OUR VERIFICATION:** CONFIRMED. A self-consistent re-hashed `due` finding with a deadline after `as_of` passed the previous semantic boundary; the inverse `fresh`/past-deadline inconsistency was also constructible.

**RESULT:** CONFIRMED and remediated. The semantic boundary now requires `review_due_at > verified_at`, `review_due_at <= as_of` for `due`, and `review_due_at > as_of` for `fresh`. Dedicated adversarial regressions cover both due/future and fresh/past inconsistencies.

## Codex independent second review — pass 4

Codex reviewed head `829bec06ee75048a82e9fcccea7c0bf4d78e0a3b` and reported one additional P2 semantic-integrity finding: a `due` source-monitoring context could carry `next_check_due_at <= latest_observed_at` while still satisfying the existing `next_check_due_at <= as_of` check.

### Reconciliation

**CODEX CLAIM:** a self-consistent re-hashed source-monitoring finding could present a polling deadline at or before the observation it supposedly follows.

**OUR VERIFICATION:** CONFIRMED independently against the upstream M2 source-freshness contract. `build_source_freshness_report` derives `next_check_due_at = latest_observed_at + timedelta(days=poll_days)`, and polling windows are constrained to positive integer days, so a valid deadline must be strictly later than the latest successful observation.

**RESULT:** CONFIRMED and remediated. The semantic brief boundary now requires `next_check_due_at > latest_observed_at` for `due` source-monitoring findings in addition to requiring the deadline to be at or before audit `as_of`. A self-consistent re-hashed equality fixture now fails closed.

## Codex independent second review — pass 5

Codex reviewed head `180dd015de64e0be9eff894816ad99e4d3eba08f` and reported one additional P2 semantic-integrity finding: two otherwise equivalent actions could receive distinct finding IDs when `reason_codes` order differed, allowing duplicate editor actions and inflated summary counts.

### Reconciliation

**CODEX CLAIM:** content-ID uniqueness alone is insufficient because array-order variants can encode the same editorial action under different hashes.

**OUR VERIFICATION:** CONFIRMED and generalized. The invariant is semantic action uniqueness, not merely canonical reason ordering. Claim-review actions are unique per Claim ID; queue actions are unique per queue-item ID; source-monitoring actions are unique per Source + registered `feed_key`, preserving the intentional ability for one Source to expose multiple independent feeds.

**RESULT:** CONFIRMED and remediated. The semantic brief boundary now tracks action keys after kind-specific context validation and rejects duplicate semantic actions even when content-addressed finding IDs differ. A self-consistent re-hashed fixture duplicates one source-monitoring action with reversed `reason_codes`, updates its summary consistently, proves the content IDs differ, and must still fail closed.

## Final bounded assessment

No architectural scope was expanded while closing these findings. This increment still:

- emits operational/editorial attention only;
- carries no truth, approval, canonical-mutation, or publication authority;
- performs no canonical writes;
- uses no LLM or model judgment;
- selects no scheduler, alerting channel, dashboard framework, orchestrator, or second truth store;
- does not reconstruct historical queue state;
- does not qualify autonomous remediation.

Merge remains contingent on exact-head schema-validation and Wikibase regression success and a final independent review of the final head.