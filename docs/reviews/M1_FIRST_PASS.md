# M1 First-Pass Review — Vertical Slice

**Branch:** `m1/vertical-slice-f15sa`

**Review state:** ongoing implementation review; findings below were independently discovered before any M1 Codex/automated review result is used as discovery evidence.

## Review surface

M1 is being reviewed across:

- source registration and authority classification;
- HTTPS/redirect trust boundaries;
- raw retrieval identity versus canonical Document identity;
- content versioning and idempotency;
- bounded HTML parsing and page-structure drift;
- Source / Document / Evidence separation;
- Evidence locator stability;
- entity-resolution authority;
- typed Claim/Event generation;
- ChangeProposal policy/risk routing;
- exact proposal-hash approval binding;
- multi-mutation backend effects;
- ambiguous effects and retry behavior;
- project Revision creation threshold;
- backend identity versus SDA domain identity;
- project predicate semantics versus backend projection direction;
- bilingual projection and citations;
- restricted operational-detail exclusion;
- CI reproducibility and negative-path coverage.

## First-pass findings

### M1-F01 — Raw HTTP bytes are not a safe web-Document identity

**Area:** acquisition / provenance

**Finding:** The first acquisition draft used SHA-256 of the full HTTP response body as the canonical Document fingerprint.

**Evidence:** Web pages can change navigation, featured-news widgets, footer content, or other page chrome while the underlying article remains unchanged. Treating raw response bytes as canonical Document content would create false Document versions.

**Why it matters:** False versions would trigger unnecessary review, duplicate historical states, and weaken deterministic source-change semantics.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED in current branch.

The design now separates:

- `RetrievalReceipt.raw_content_sha256` — exact fetched bytes;
- `Document.content_sha256` — source-adapter canonical article content.

The USAF adapter fingerprints only the bounded article content. CI explicitly changes page chrome while asserting stable Document identity, then changes article content while requiring a new Document version.

---

### M1-F02 — Document/Evidence identity had a circular dependency

**Area:** provenance / parser lifecycle

**Finding:** An intermediate parser API required `document_id` to create Evidence while the final `document_id` itself depended on the parser-produced canonical content hash.

**Why it matters:** A caller would need a provisional identity, a double parse, or mutation of already-created Evidence IDs.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED in current branch.

Parsing is now two-phase:

```text
analyze source bytes
  -> canonical article fingerprint + Evidence candidates
  -> derive immutable Document ID
  -> materialize Evidence IDs bound to final Document ID
```

---

### M1-F03 — Page-global Evidence indexes are unstable under unrelated chrome changes

**Area:** evidence locators

**Finding:** Initial Evidence selectors used page-global HTML block indexes. Inserting an unrelated paragraph before the article would shift the selector even when the supporting article paragraph was unchanged.

**Why it matters:** Equivalent source content could produce locator churn and Evidence duplication.

**Severity:** Medium

**Confidence:** High

**Resolution:** FIXED in current branch.

Evidence selectors now use article-relative block indexes plus normalized text hashes. CI asserts selector stability across page-chrome changes.

---

### M1-F04 — Entity recognition must not become entity-resolution authority

**Area:** intelligence / identity

**Finding:** The source parser recognizes names such as F-15SA, Royal Saudi Air Force, and Boeing, but recognition alone cannot prove which canonical SDA entity should be mutated.

**Why it matters:** Hard-coding parser names directly into canonical IDs would collapse extraction and entity-resolution authority.

**Severity:** High

**Confidence:** High

**Resolution:** CONTROL IMPLEMENTED; end-to-end resolver remains future work.

The typed proposal builder requires an explicit `ResolvedF15SAEntities` input. Missing/unresolved SDA identity causes proposal construction to fail. M1 tests use the existing M0 SDA identity vocabulary only as a resolved fixture.

---

### M1-F05 — One proposal can partially affect a non-transactional backend

**Area:** canonical mutation / failure semantics

**Finding:** A ChangeProposal contains multiple mutations, while Wikibase does not provide a project-level transaction spanning every intended resource effect.

**Why it matters:** Treating a successful individual API call as proposal success could create a project Revision over only a partial backend state. Blind retry after timeout could duplicate or conflict with effects that actually occurred.

**Severity:** Critical

**Confidence:** High

**Resolution:** BACKEND-INDEPENDENT CONTROL IMPLEMENTED; Wikibase adapter proof still pending.

The M1 mutation guard now requires:

1. exact approved proposal-hash authorization;
2. full preflight inspection before new writes;
3. existing equivalent effects are skipped;
4. conflict/unknown preflight blocks all new writes;
5. each absent effect gets at most one write attempt per execution;
6. ambiguous write outcome is reconciled by reading state, never blindly retried;
7. every intended mutation is reported as `not_attempted`, `already_applied`, `applied`, `failed`, or `effect_unknown`;
8. project Revision creation is permitted only after every intended effect converges to equivalence.

A fake-backend matrix tests clean convergence, replay, preflight unknown, definitive failure, ambiguous-applied, and ambiguous-unproven paths.

---

### M1-F06 — The M0 trial projection reverses the accepted operator predicate

**Area:** ontology / backend mapping

**Finding:** The accepted ontology defines `organization.operates.equipment_variant` (organization → equipment variant), while the M0 Wikibase spike created an `operator` statement on the equipment item pointing to the organization (equipment → organization).

**Why it matters:** Reusing the M0 property merely because it already exists would let a trial backend vocabulary override project-native predicate direction and would make the M1 Claim payload semantically inconsistent with its storage projection.

**Severity:** High

**Confidence:** High

**Resolution:** M1 MAPPING DECISION RECORDED; runtime proof pending.

M1 will introduce/use a Wikibase projection property corresponding to `organization.operates.equipment_variant` and place the statement on the organization item. The legacy M0 `operator` property remains trial evidence only and is not canonical SDA predicate authority.

---

## Areas currently considered sound at this review stage

- registered source URLs are HTTPS-only;
- redirect targets are checked before following against an explicit source allowlist;
- response size and timeout are bounded;
- unchanged canonical content does not rewrite immutable Document metadata;
- source prose is not copied into Evidence excerpts by default;
- required parser patterns fail closed on zero or multiple matches;
- delivery year derivation is bounded to publication-date context rather than inferred from model memory;
- first proposal is AMBER and requires human review;
- current proposal scope avoids inventory quantity, current service state, location, readiness, and other unsupported operational inference;
- source parsing, entity resolution, policy review, and backend mutation are separate boundaries.

## Open questions / required verification

- Does the source-specific canonicalization remain stable against the live USAF page while still detecting material article edits?
- Does the Wikibase adapter implement `inspect_effect` strongly enough to distinguish equivalent/conflict/unknown for every resource type in this proposal?
- How are Source/Document/Evidence projected into Wikibase without losing project-native provenance semantics?
- Does the M1 Wikibase mapping preserve canonical SDA predicate direction rather than inheriting M0 trial direction?
- How is a fully converged proposal transformed into one schema-valid project Revision with complete backend receipts?
- How are Arabic labels introduced with explicit provenance or editorial terminology authority rather than inferred from the English source?
- Can one public bilingual page be rendered entirely from canonical SDA records with citations and no independent CMS truth copy?

## FIRST-PASS REVIEW CHECKPOINT

Known findings: M1-F01 through M1-F06 above.

Suspected findings: live-page canonicalization drift and backend inspection-strength differences by resource type require runtime verification.

Areas considered sound: deterministic trust boundaries, canonical-vs-raw identity separation, parser fail-closed behavior, proposal scope/risk policy, and backend-independent no-blind-retry semantics as currently implemented.

Areas requiring deeper verification: real Wikibase adapter convergence, Revision construction, live-source evidence artifact, and bilingual public projection.

This checkpoint must not be rewritten to manufacture agreement with a later independent reviewer. Later findings belong in a separate reconciliation/adversarial record.
