# M2 Claim Staleness — Exhaustive First-Pass Review

## Review Surface

Reviewed increment: policy-driven, backend-neutral staleness report for current canonical Claims in PR #5.

Reviewed artifacts:

- `schemas/v0.1/staleness-report.schema.json`
- `services/presentation/staleness.py`
- `scripts/validate_m2_staleness.py`
- `scripts/validate_m2_staleness_isolation.py`
- M2 staleness CI steps
- interaction with `claim.schema.json` and `SOURCE_POLICY.md` staleness semantics

Out of scope:

- scheduling re-verification jobs
- automatically mutating Claim state
- source/document staleness scoring
- editorial UI prioritization
- production review-window values

## Required Semantics

1. Staleness means re-verification is due, not that a Claim is false.
2. Review windows are explicit caller-owned policy, not model-generated confidence.
3. Predicate-specific policy may override a documented default.
4. A missing `verified_at` remains explicitly `unverified` and must not invent age/deadline.
5. Disputed state and staleness are independent dimensions.
6. Withdrawn/superseded Claims are not part of the current review workload.
7. Exact review deadlines must be machine-visible and unambiguous.
8. Equivalent timezone representations must produce deterministic UTC output.

## Findings Register

### M2-SF01 — Review-window boundary was implicit and off by one instant

**Area:** temporal correctness

**Finding:** Initial logic used `elapsed > timedelta(days=review_days)`. A Claim exactly at its review boundary remained `fresh`, and consumers had no explicit deadline field.

**Why it matters:** “Review after 30 days” needs an exact machine-readable boundary. Without it, UI/workflow implementations could disagree on when a Claim becomes due.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Each verified Claim now exposes `review_due_at`; `due` begins at `as_of >= review_due_at`. Regression coverage tests the exact 30-day boundary.

---

### M2-SF02 — Duplicate canonical IDs could be hidden by Claim-state filtering

**Area:** input integrity / fail-closed behavior

**Finding:** Initial duplicate-ID detection ran only after filtering to `active`/`disputed`. An `active` Claim plus a `withdrawn` record with the same canonical ID could avoid duplicate detection.

**Why it matters:** Canonical ID uniqueness is a collection invariant, independent of whether a record is visible in the current staleness workload.

**Severity:** Medium

**Confidence:** High

**Disposition:** FIXED. ID validation/uniqueness now runs over the full input collection before state filtering. A dedicated regression test covers active + withdrawn duplicate IDs.

---

### M2-SF03 — Staleness could be misread as a truth judgment

**Area:** semantics / editorial safety

**Finding:** A maintenance report that labels old Claims without explicit semantics could be interpreted as withdrawing or disproving them.

**Why it matters:** `SOURCE_POLICY.md` explicitly states that a stale Claim is not automatically false.

**Severity:** Medium

**Confidence:** High

**Disposition:** CONTROLLED. The report exposes only `fresh`, `due`, and `unverified`; the `due` reason explicitly states that the Claim is not automatically false. The projector has no canonical mutation path and preserves `claim_state` separately.

---

### M2-SF04 — Timezone representation could make semantically equivalent reports differ

**Area:** determinism / temporal normalization

**Finding:** Returning raw `as_of`/`verified_at` representations would allow the same instant expressed with different offsets to produce different report payloads.

**Severity:** Medium

**Confidence:** High

**Disposition:** FIXED. Parsed timestamps normalize to UTC `Z`; regression coverage proves `2026-01-10T00:00:00Z` and `2026-01-10T03:00:00+03:00` produce the same report.

## Failure Review

The projector rejects:

- timezone-naive `as_of` or `verified_at`;
- invalid/future `verified_at` relative to `as_of`;
- review windows below one day or boolean/non-integer values;
- empty predicate-policy keys;
- duplicate canonical Claim IDs anywhere in the input collection;
- malformed current Claim identity/predicate/confidence fields.

## Areas Reviewed With No Material Issue Found

- withdrawn/superseded Claims are excluded from the current workload;
- disputed Claims remain present with `claim_state=disputed` rather than being silently promoted/demoted;
- `unverified` Claims receive neither fabricated age nor fabricated deadline;
- policy is serialized into the report so downstream consumers know which windows produced the result;
- item ordering and policy-key ordering are deterministic;
- report generation performs no write, review decision, or canonical state transition;
- no operational/sensitive military data is introduced by this increment.

## Deferred Work

1. Production review-window values require explicit editorial policy; test windows are synthetic and not adopted operational policy.
2. Source/Document freshness may be added separately; this increment evaluates Claim verification age only.
3. Scheduling and notification mechanisms remain separate architecture decisions.
4. Procurement/Exercise domain views can consume this report but should not embed their own hidden staleness rules.

## First-Pass Judgment

After fixing M2-SF01, M2-SF02, and M2-SF04 and explicitly controlling M2-SF03, no first-pass merge-blocking defect remains in the claim-staleness contract.
