# Foundation First-Pass Review

**Review target:** `bootstrap/foundation` before M0 implementation

**Review method:** independent project review before any external/code-agent second review.

**Status:** FIRST-PASS REVIEW COMPLETE

## Review surface

Reviewed:

- `README.md`
- `docs/VISION.md`
- `docs/ARCHITECTURE.md`
- `docs/ONTOLOGY.md`
- `docs/SOURCE_POLICY.md`
- `docs/AI_GOVERNANCE.md`
- `docs/ROADMAP.md`

Review dimensions:

- product intent and scope
- canonical truth model
- authority and governance boundaries
- ontology semantics
- source/evidence semantics
- AI mutation boundaries
- lifecycle/state modeling
- failure and ambiguity handling
- M0/M1 acceptance criteria
- implementation neutrality

## Findings register

### F-01 — Canonical mutation authority is not explicit enough

**Area:** architecture / governance

**Finding:** The documents correctly state that AI is not canonical authority and that some changes require human review, but they do not yet define the authoritative mutation actor/process for the knowledge core.

**Evidence:** `ARCHITECTURE.md` contains a Governance Gate and `AI_GOVERNANCE.md` defines GREEN/AMBER/RED authority levels, but neither names the canonical write contract or authority owner.

**Why it matters:** M0 will test machine writes and human approval. Without an explicit write boundary, a prototype can accidentally encode tool-specific authority semantics.

**Severity:** High

**Confidence:** High

**Required action:** Define a project-native `ChangeProposal -> ReviewDecision -> CanonicalRevision` contract before choosing the knowledge-store implementation.

---

### F-02 — `Source`, `Document`, and `Evidence` overlap semantically

**Area:** ontology

**Finding:** `Source` is described as publisher/origin, `Document` is an entity type for source artifacts, and `Evidence` also carries source locator/URI and publication metadata. The identity boundary between publisher, artifact, and supporting span is not yet strict.

**Why it matters:** Provenance, deduplication, corrections, and claim-level citations depend on stable separation of these concepts.

**Severity:** High

**Confidence:** High

**Required action:** Define:

- `Source` = publisher/origin authority;
- `Document` = immutable-or-versioned retrieved artifact;
- `Evidence` = bounded locator/span/structured observation within a document that bears on a claim.

---

### F-03 — Procurement lifecycle is presented too linearly

**Area:** ontology

**Finding:** The procurement diagram uses a downward linear sequence even though the text correctly notes that not every program traverses every state.

**Why it matters:** Real procurement histories branch, repeat, suspend, split by tranche, and may have simultaneous states for approval, contracting, delivery, and operationalization.

**Severity:** Medium

**Confidence:** High

**Required action:** Treat procurement facts primarily as typed events plus bounded status claims. Do not encode the diagram as a mandatory finite-state transition order.

---

### F-04 — Candidate technologies are listed without explicit adoption state

**Area:** architecture governance

**Finding:** `ARCHITECTURE.md` correctly labels open-source components as candidates, but there is no durable register distinguishing observation, candidate status, trial authorization, implementation, and verification.

**Why it matters:** The project explicitly intends to evaluate Wikibase. Without independent status axes, a successful spike can be mistaken for automatic adoption, or implementation can be mistaken for verification.

**Severity:** Medium

**Confidence:** High

**Required action:** Establish an Architecture Pattern Register before the Wikibase spike.

---

### F-05 — M0 requires an implementation-neutral proposal schema that is not yet defined

**Area:** data contract

**Finding:** The roadmap requires AI extraction to be representable as a proposal before admission, but there is no typed proposal/review/revision contract yet.

**Why it matters:** This contract is the main protection against a knowledge-store API becoming the de facto governance model.

**Severity:** High

**Confidence:** High

**Required action:** Add implementation-neutral schemas for entities, claims, documents/evidence, events, change proposals, review decisions, and canonical revisions before the Wikibase adapter.

## Open questions

1. Will canonical IDs be project-issued opaque IDs, store-native IDs, or both?
2. Should source documents be content-addressed, URL-versioned, or both?
3. What is the exact claim identity/deduplication key?
4. How will confidence be represented without implying false numeric precision?
5. Which M0 facts are test fixtures versus claims suitable for later public publication?
6. How will source licensing/access constraints affect retained excerpts?

## Potential failure modes

- store-native identifiers leak into the public/domain contract;
- a retrieval URL is mistaken for immutable document identity;
- a newer claim destructively replaces a differently scoped older claim;
- one status field collapses procurement approval, contract, delivery, and service state;
- AI writes directly through a store API without proposal/review semantics;
- a successful technology spike is treated as architectural adoption without a decision record.

## Areas reviewed with no fundamental issue found

- knowledge-first product thesis;
- bilingual canonical identity requirement;
- claim-level evidence requirement;
- preservation of conflicting claims;
- explicit unknown values and rejection of invented precision;
- deterministic-before-generative preference;
- idempotent ingestion requirement;
- restricted-operational-information boundary;
- M0-before-public-site sequencing;
- fallback from Wikibase to PostgreSQL without changing domain semantics.

## Frozen first-pass view

### Known findings

F-01 through F-05 above.

### Suspected findings

No additional material defect is asserted without implementation evidence.

### Areas considered sound

The product boundary, knowledge-first architecture, source-first policy, AI authority principle, and M0 decision gate are coherent and mutually reinforcing.

### Areas requiring deeper verification

- concrete schema semantics;
- claim/document identity and idempotency;
- Wikibase mapping ergonomics;
- reviewable proposal workflow;
- revision/audit behavior;
- query/API suitability for a custom frontend.

This file is intentionally preserved as the pre-implementation review baseline and should not be retroactively rewritten to match later findings.