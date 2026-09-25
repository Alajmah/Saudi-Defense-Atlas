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

**Resolution:** CONFIRMED and verified.

`approved-demo-bundle.json` + `apply_approved_demo.py` exercise an AMBER synthetic proposal that must pass project schemas, exact proposal-hash binding, and cross-record human-review rules before the first backend API call. The post-write project Revision carries backend revision/statement identifiers only as receipts.

Current-head Wikibase run `36178040438` executed this adapter path successfully. No real Saudi-defense record is modified by the adapter test.

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

**Finding:** The spike first uses `action=login`; if it does not return Success, the `clientlogin` fallback reuses the fetched login token.

**Resolution:** NOT EXERCISED / NOT AN M0 BLOCKER.

Clean CI runs authenticated successfully through the tested normal path. The fallback path itself remains unverified and must not be described as supported merely because normal authentication passed. Production authentication design is deferred.

---

### R-09 — WDQS convergence is an operational dependency of the M0 query criterion

**Provenance:** second/adversarial review hypothesis.

**Finding:** WDQS is eventually updated separately from Action API writes; convergence behavior is an operational dependency.

**Resolution:** M0 criterion PASSED, operational caveat retained.

Current-head run `36178040438` successfully resolved an SDA canonical ID through WDQS. This demonstrates the tested query path, not a production latency/SLA guarantee.

---

### R-10 — Compose/image compatibility is not established by configuration inspection

**Provenance:** second/adversarial review hypothesis.

**Finding:** Static Compose inspection cannot prove the selected service images start and interoperate.

**Resolution:** CONFIRMED by runtime for the tested configuration.

Current-head run `36178040438` started the clean stack, passed health checks, seeded, queried, wrote, uploaded evidence, and tore down successfully. This does not qualify upgrades or production topology.

---

### R-11 — Mapping inverted the proposal/decision/revision time boundary

**Provenance:** continued adversarial review finding.

**Finding:** `MAPPING.md` stated that a project Revision had to reference the exact proposal and decision before the adapter could execute a backend write. The implemented adapter instead creates the project Revision after receiving backend identifiers, which is the coherent ordering when those identifiers are receipts for the applied effect.

**Why it mattered:** The documentation described an impossible precondition and blurred authorization evidence with post-effect audit evidence.

**Resolution:** CONFIRMED and fixed.

The mapping now defines:

- pre-write authority = admission-permitting proposal + approving decision + reviewer authority + exact proposal hash binding;
- backend mutation = execution attempt under that authority;
- post-write audit = project Revision referencing the proposal/decision and carrying backend identifiers as receipts.

The mapping explicitly states that M0 does **not** prove production-grade exactly-once mutation or reconciliation of interrupted/ambiguous external effects.

---

### R-12 — Cross-record governance did not enforce temporal ordering

**Provenance:** continued adversarial review finding.

**Finding:** Earlier workflow fixtures verified identity, hash binding, risk authority, and approval/rejection semantics but did not reject a decision dated before its proposal or a Revision dated before its approving decision.

**Why it mattered:** An internally inconsistent audit chain could pass cross-record governance validation even when each standalone record was schema-valid.

**Resolution:** CONFIRMED and fixed.

`validate_workflow.py` now enforces temporal ordering when the relevant timestamps are present, and fixtures cover:

- valid proposal → decision → Revision ordering;
- invalid decision-before-proposal;
- invalid Revision-before-decision.

Schema/governance run `36178033709` passed the updated tests.

## Clean areas after second pass

No fundamental issue was found in these reviewed areas:

- project ID is explicitly separate from Q/P backend identity;
- Source / Document / Evidence semantics are no longer collapsed;
- synthetic contradiction data is unmistakably isolated from factual defense data;
- real test records use coarse, public, officially documented facts;
- PAC-3 MSE test semantics preserve approval/notification versus contract/delivery;
- negative schema/workflow fixtures exercise rejection paths rather than only happy paths;
- host ports in the local spike are loopback-bound;
- decision binds to the exact proposal payload hash;
- project Revision is distinct from backend MediaWiki revision receipts;
- production security, HA, backup, scaling, deployment, and exactly-once effect claims remain outside the M0 claim ceiling.

## Final evidence state

Exact implementation head verified: `e3d08935907d85c20da12531a81a22d43e23f597`.

### Schema/governance

GitHub Actions run `36178033709` completed successfully, including schema fixtures and mutation-governance tests.

### Wikibase trial

GitHub Actions run `36178040438`, job `108213344752`, completed successfully on the same implementation head. It passed:

- clean Wikibase stack startup and health;
- M0 fixture seeding;
- representation/query verification;
- approved synthetic proposal through the adapter gate;
- verification artifact upload;
- cleanup.

Artifact `10883261546` reports `PASS` and records:

- Arabic/English/alias resolution;
- SDA domain ID distinct from Q-ID;
- qualified multi-reference claim;
- simultaneous synthetic conflicting quantities;
- procurement-stage separation;
- backend revision history;
- WDQS lookup;
- Action API read;
- post-write project Revision with backend receipt for the approved synthetic adapter proof.

## Remaining uncertainty

M0 intentionally does not establish:

- production authentication/authorization;
- target-scale performance;
- HA or backup/recovery;
- long-term upgrade compatibility;
- exactly-once mutation;
- retry/reconciliation behavior after interrupted or ambiguous external effects;
- production observability/operations.

These are later verification surfaces, not reasons to inflate or reject the M0 claim.

## Second-review judgment

**M0 knowledge-core and governance acceptance criteria are satisfied at the bounded claim level.**

ADR-0002 may promote Wikibase to the accepted M1 canonical knowledge-core implementation while retaining the production limitations above and keeping PostgreSQL as a deferred fallback.
