# M0 Adversarial Second Review

**Review target:** M0 schemas, mutation-governance tests, and Wikibase trial implementation on `bootstrap/foundation`.

**Review role:** independent second/adversarial pass after the frozen foundation first-pass review.

**Codex status:** No Codex execution surface is available in the current project tool environment. Per project review policy, the project agent therefore performed the second-review role directly rather than treating unavailable Codex output as evidence.

## Review method

The frozen baseline in `docs/reviews/FOUNDATION_FIRST_PASS.md` was not rewritten. This pass challenged the implementation against:

- schema semantics and impossible states;
- provenance identity;
- proposal/review/revision authority separation;
- negative-path validation;
- adapter/backend boundaries;
- Wikibase mapping assumptions;
- CI evidence versus documentation claims;
- procurement-stage semantics;
- synthetic versus factual test data.

## Findings

### R-01 — Mutation resource type was not bound to payload schema

**Provenance:** second/adversarial review finding.

**Finding:** An early `ChangeProposal` schema allowed a mutation declaring `resource_type: entity` while supplying any payload that matched one of the unioned resource schemas, including a Claim.

**Why it mattered:** Downstream dispatch based on `resource_type` could be inconsistent with the validated payload type, creating an authority/serialization ambiguity.

**Resolution:** CONFIRMED and fixed.

- `resource_type` is now conditionally bound to exactly one corresponding payload schema.
- A negative fixture attempts to disguise a Claim as an Entity and must fail validation.

---

### R-02 — Document identity could be satisfied by a present-but-null URL

**Provenance:** second/adversarial review finding.

**Finding:** The initial `anyOf` identity rule required only property presence. Because URL fields allowed `null`, a document containing `canonical_url: null` could satisfy the branch.

**Why it mattered:** It weakened deterministic provenance/deduplication semantics.

**Resolution:** CONFIRMED and fixed.

The identity branches now require a non-null URI string or a non-empty publisher document ID. A negative fixture covers the null-URL case.

---

### R-03 — Evidence/Claim/Event audit provenance was under-constrained

**Provenance:** second/adversarial review finding.

**Finding:** Early schemas did not require Evidence capture time/method or Claim/Event creation timestamps.

**Why it mattered:** The project promises auditable AI/data transformations. Optional audit fields would allow canonical-looking records without enough transformation provenance.

**Resolution:** CONFIRMED and fixed.

- Evidence requires `captured_at` and `capture_method`.
- Claim requires `claim_state` and `created_at`.
- Event requires `created_at`.

---

### R-04 — Reviewer authorization was placed in the wrong schema layer

**Provenance:** second/adversarial review finding.

**Finding:** An early ReviewDecision schema forced all system-authored decisions to `approve`, even though actor authorization depends on the referenced proposal risk/policy outcome and a system may legitimately record rejection/denial behavior.

**Why it mattered:** Per-record schema could not correctly express cross-record authorization.

**Resolution:** CONFIRMED and fixed.

The ReviewDecision schema now validates record shape only. Authorization is enforced by the cross-record workflow validator.

---

### R-05 — A policy-pending proposal could be approved

**Provenance:** second/adversarial review finding.

**Finding:** The first cross-record validator constrained RED/AMBER actor behavior but did not explicitly prohibit an `approve` decision while `policy_outcome == pending`.

**Why it mattered:** Review could race ahead of policy evaluation and create an apparently authorized canonical revision.

**Resolution:** CONFIRMED and fixed.

Approval now requires an admission-permitting policy outcome. A dedicated negative workflow fixture covers pending-policy approval.

---

### R-06 — The datastore authority boundary was documented but not executed

**Provenance:** second/adversarial review finding.

**Finding:** The initial mapping described a governance gate, but `seed.py` necessarily writes directly to construct the representation test and no adapter proof yet demonstrated that an ordinary mutation could be held behind the project proposal/review authority boundary.

**Why it mattered:** Documentation alone was insufficient evidence that the backend could remain subordinate to the project authority contract.

**Resolution:** CONFIRMED; implementation added, runtime verification pending.

`approved-demo-bundle.json` + `apply_approved_demo.py` now exercise an AMBER synthetic proposal that must pass project schemas, exact proposal-hash binding, and cross-record human-review rules before the first backend API call. The post-write project Revision carries backend revision/statement identifiers only as receipts.

No real Saudi-defense record is modified by this adapter test.

---

### R-07 — Schema validation error sorting could compare heterogeneous path types

**Provenance:** second/adversarial review finding.

**Finding:** Sorting errors by raw `absolute_path` lists could compare string and integer path segments under Python ordering.

**Why it mattered:** A validator invoked specifically on malformed nested input could itself fail while formatting multiple errors.

**Resolution:** CONFIRMED and fixed.

Error paths are normalized to tuples of strings for deterministic sorting.

---

### R-08 — Wikibase Action API login fallback may require fresh-token handling

**Provenance:** second/adversarial review hypothesis.

**Finding:** The spike first uses `action=login`; if it does not return Success, the `clientlogin` fallback reuses the fetched login token. Whether that fallback path is valid for the tested Wikibase Suite image must be demonstrated by runtime evidence.

**Severity:** Medium

**Confidence:** Medium

**Status:** UNRESOLVED pending clean CI execution. The normal local admin login path may never enter the fallback.

**Required verification:** Inspect `wikibase-m0-spike` job evidence/logs. If authentication fails in the fallback path, implement the current supported token flow and rerun from a clean instance.

---

### R-09 — WDQS convergence is an operational dependency of the M0 query criterion

**Provenance:** second/adversarial review hypothesis.

**Finding:** The verifier polls WDQS after writes, but updater initialization/lag is external to the Action API write. A timeout could represent query-updater convergence failure rather than inability to model the data.

**Severity:** Medium

**Confidence:** High

**Status:** UNRESOLVED pending clean CI execution.

**Interpretation rule:** If WDQS alone times out while Action API representation tests pass, classify M0 as technically inconclusive for the query criterion rather than immediately rejecting the data model.

---

### R-10 — Compose/image compatibility is not established by configuration inspection

**Provenance:** second/adversarial review hypothesis.

**Finding:** The trial mirrors current upstream major images/configuration, but only an actual clean environment can prove the selected subset starts together and exposes the expected APIs.

**Status:** UNRESOLVED pending CI.

No APR/ADR verification claim may be made from the compose file alone.

---

### R-11 — Mapping inverted the proposal/decision/revision time boundary

**Provenance:** continued adversarial review finding.

**Finding:** `MAPPING.md` stated that a project Revision had to reference the exact proposal and decision before the adapter could execute a backend write. The implemented adapter instead creates the project Revision after receiving backend identifiers, which is the only coherent ordering if those identifiers are receipts for the applied effect.

**Why it mattered:** The documentation described an impossible precondition and blurred authorization evidence with post-effect audit evidence.

**Resolution:** CONFIRMED and fixed.

The mapping now defines:

- pre-write authority = admission-permitting proposal + approving decision + reviewer authority + exact proposal hash binding;
- backend mutation = execution attempt under that authority;
- post-write audit = project Revision referencing the proposal/decision and carrying backend identifiers as receipts.

The mapping also explicitly states that M0 does **not** prove production-grade exactly-once mutation or reconciliation of interrupted/ambiguous external effects.

## Clean areas after second pass

No fundamental issue was found in these reviewed areas:

- project ID is explicitly separate from Q/P backend identity;
- Source / Document / Evidence semantics are no longer collapsed;
- synthetic contradiction data is unmistakably isolated from factual defense data;
- real test records use coarse, public, officially documented facts;
- PAC-3 MSE test semantics preserve approval/notification versus contract/delivery;
- negative schema/workflow fixtures exercise rejection paths rather than only happy paths;
- host ports in the local spike are loopback-bound;
- production security, HA, backup, scaling, deployment, and exactly-once effect claims remain outside the M0 claim ceiling.

## Evidence state at time of this review

- Schema/governance validation has produced a successful GitHub Actions run on an implementation head.
- The complete Wikibase clean-run evidence, including approved-adapter execution, is still required before architectural promotion.
- ADR-0002 therefore remains `Pending Evidence`.
- APR-003 must not be marked `VERIFIED` merely because the trial code exists.

## Second-review judgment

The implementation is suitable to proceed to clean runtime verification **after the confirmed defects above were fixed**.

The remaining material uncertainties are runtime/tool-integration questions rather than known domain-model contradictions. Evidence from the clean Wikibase workflow must resolve them before the knowledge-core decision is promoted.
