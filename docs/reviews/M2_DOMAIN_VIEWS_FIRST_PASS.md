# M2 Procurement/Exercise Domain Views — Exhaustive First-Pass Review

## Review Surface

Reviewed increment: typed backend-neutral public `ProcurementProgramView` and `ExerciseView` projections introduced by PR #6.

Scope reviewed:

- `schemas/v0.1/procurement-program-view.schema.json`
- `schemas/v0.1/exercise-view.schema.json`
- `services/presentation/domain_views.py`
- `services/presentation/projection_support.py`
- M2 relationship-graph helper migration
- `scripts/validate_m2_domain_views.py`
- interaction with the accepted M2 staleness report contract

Explicitly out of scope for this increment:

- frontend framework adoption
- visualization library adoption
- generalized search/indexing
- scheduler/editorial workflow
- automated source admission
- live/operational data

## Required Invariants

1. Domain views are read projections, not new truth stores.
2. Procurement lifecycle history must not be collapsed into a single inferred current state.
3. Different lifecycle values at different times are not conflicts merely because they differ.
4. Explicitly disputed lifecycle Claims remain visibly disputed.
5. Material facts/events retain Evidence -> Document -> Source citations.
6. Staleness remains a review-due signal, not a truth judgment.
7. A staleness item must correspond to the exact current Claim verification state used by the view.
8. Staleness output must retain the `as_of` and review-policy context that produced it.
9. Backend Q/P identifiers must not leak into public domain views.
10. Shared presentation helpers must preserve the existing public projection error/catch boundary.

## Findings Register

### M2-DV-F01 — Lifecycle values were initially treated as competing current states

**Area:** procurement temporal semantics

**Finding:** The initial domain-view design summarized lifecycle values into a `lifecycle_state` object and treated multiple values as a dispute. This incorrectly conflated normal procurement progression (for example approval followed later by contracting) with factual conflict.

**Why it matters:** The project ontology explicitly states that procurement is not a mandatory linear FSM and that history is represented through typed Events plus temporally bounded Claims. Different lifecycle values can be valid at different points in time.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. The public contract now exposes `lifecycle_history` with individual observations and validity metadata. Multiple active historical values remain `documented`; only an explicitly `disputed` Claim makes the history disputed. No current state is inferred.

---

### M2-DV-F02 — Domain views initially detached staleness items from their report context

**Area:** staleness / provenance

**Finding:** The first design copied only selected staleness items into each domain view, dropping the report `as_of` timestamp and policy that generated their `fresh`/`due` status.

**Why it matters:** A `due` classification is meaningful only relative to an evaluation time and review window. Removing that context makes the public/editorial projection ambiguous and can turn a policy-derived status into an apparently timeless property.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Domain views now embed a filtered but schema-valid staleness report containing `as_of`, policy, recomputed summary, and selected items.

---

### M2-DV-F03 — A stale staleness report could be joined to a re-verified Claim

**Area:** consistency / version binding

**Finding:** Initial joining checked Claim ID and selected metadata but not `verified_at`. If a Claim retained its canonical ID after re-verification, an older staleness result could be attached to the newer Claim state.

**Why it matters:** The view could display a Claim as due even though it had already been re-verified, or vice versa.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. The join now compares normalized timezone-aware `verified_at` values and fails closed on mismatch. Regression coverage supplies an intentionally older verification timestamp and requires rejection.

---

### M2-DV-F04 — Shared-helper extraction could split the public projection exception boundary

**Area:** compatibility / maintainability

**Finding:** Moving citation/index/value helpers from the M1 equipment projector into `projection_support` initially risked introducing a second `ProjectionError` type while existing M1/M2 validators and callers catch the established M1 exception.

**Why it matters:** Fail-closed paths could escape expected handlers solely because helper ownership changed.

**Severity:** Medium

**Confidence:** High

**Disposition:** FIXED FOR THIS INCREMENT. `projection_support` re-exports the established M1 `ProjectionError`, so relationship/domain projections keep a single catch boundary. Full exception ownership can move to the shared module in a later dedicated compatibility refactor.

## Failure and Trust Review

The domain views fail closed when:

- the requested root entity is absent, inactive, or of the wrong type;
- canonical Entity/Claim/Evidence/Document/Source IDs are duplicated or unresolved;
- material procurement facts cannot resolve supporting Evidence;
- the staleness report omits a required current Claim;
- a staleness item disagrees with the canonical Claim on subject, predicate, state, confidence, or verification timestamp;
- staleness timestamps are malformed or timezone-naive;
- lifecycle Claims have malformed/non-string lifecycle values;
- graph construction detects missing nodes, invalid participants, unsupported evidence, or backend-ID leakage regressions through its existing contract.

## Areas Reviewed With No Material Issue Found

- Exercise views preserve bounded cited graph semantics and event intervals.
- Procurement quantity Claims remain typed facts; they are not collapsed across quantity types.
- Disputed Claims remain visible rather than silently selecting a winner.
- Domain views consume a caller-supplied staleness policy; they do not invent review windows.
- No frontend, graph database, scheduler, search engine, or operational-tracking dependency is introduced.
- SDA IDs remain public identity.

## Deferred / Non-Blocking Work

1. Lifecycle-history observations are deterministic but not advertised as a fully ordered chronology; a later presentation layer may sort by explicit temporal precision when required.
2. `ProjectionError` ownership remains physically in the M1 equipment module for compatibility; migration to the shared support module should be a separate refactor with M1 regression coverage.
3. Real procurement/exercise source admission remains upstream of these views; synthetic fixtures validate representation mechanics only.

## First-Pass Judgment

After fixes M2-DV-F01 through M2-DV-F04, no first-pass merge-blocking defect remains in the typed procurement/exercise domain-view contract. Merge remains gated on final-head schema validation and Wikibase regression workflows.
