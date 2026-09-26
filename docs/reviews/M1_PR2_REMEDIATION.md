# M1 PR #2 Remediation Record

This record captures findings discovered during the independent first-pass review of PR #2 and the remediation applied before any later independent/Codex review. It supplements `M1_FIRST_PASS.md` and `M1_FIRST_PASS_CONTINUED.md`; it does not rewrite their discovery history.

## M1-F10 — Runtime Wikibase proof fixture drifted from parser contract

**Area:** CI / runtime verification

**Finding:** `run_m1_vertical_slice.py` omitted the bounded article-end paragraph required by the USAF parser, so the real Wikibase workflow failed before backend login or mutation.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED.

The runtime fixture now contains the same bounded article-ending material used by the parser/proposal fixtures, allowing the workflow to reach the adapter and replay assertions.

---

## M1-F11 — F-15SA operator Claim exceeded the cited sentence

**Area:** evidence semantics / claim ceiling

**Finding:** The source sentence states that F-15SA is an advanced version of the F-15S currently operated by the Royal Saudi Air Force. The grammatical operation assertion applies to F-15S, while the proposal emitted `RSAF -> operates -> F-15SA` at high confidence.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED for this slice.

The operator Claim is removed. The source-backed Claim is now the directly stated Boeing/F-15SA manufacturer relationship. RSAF is represented as recipient on the dated delivery Event. A timeless/current F-15SA operator Claim remains outside this source's admitted claim ceiling.

---

## M1-F12 — Boeing `supplier` role conflated producer/manufacturer semantics

**Area:** event semantics

**Finding:** The bounded evidence identifies the aircraft as Boeing-produced; it does not establish Boeing as the FMS supplier in the event model.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED.

The Event role vocabulary now includes `recipient` and `manufacturer`; the M1 delivery Event uses RSAF/recipient and Boeing/manufacturer.

---

## M1-F13 — Revision ID could identify two different Revision payloads

**Area:** canonical identity / replay

**Finding:** Revision identity depended only on proposal ID, decision ID, and proposal hash while Revision payload also contained `applied_at` and execution-specific receipts. Rebuilding after replay could therefore reuse an ID for different content.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED.

Revision identity is now derived from the exact canonical Revision body. Byte-equivalent body content yields the same ID; changed `applied_at`, receipts, actor, or affected-record content yields a different ID.

---

## M1-F14 — Payload hash equivalence could hide an incomplete projection

**Area:** backend projection / reconciliation

**Finding:** The projection vocabulary declared capture metadata, Claim state, creation timestamps, and related Claim IDs, but the adapter omitted several of them. Equivalence inspection checked only canonical ID + payload hash, so an older incomplete projection could still be treated as equivalent.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED for the bounded M1 projection.

The adapter now projects Evidence `captured_at`/`capture_method`, Claim `claim_state`/`created_at`, Event `created_at`/`related_claim_ids`, and an explicit `m1-v1` projection version. Item/Claim equivalence requires both the exact payload hash and exact projection version. Runtime verification reads these fields back from Wikibase.

---

## M1-F15 — Sequential reconciliation does not establish concurrent-writer safety

**Area:** canonical mutation / concurrency

**Finding:** Two independent writers can both observe a canonical ID as absent before either creates it. Wikibase does not enforce uniqueness of the SDA canonical-ID property, so the current preflight/reconcile design proves sequential idempotency but not concurrent uniqueness.

**Severity:** Medium

**Confidence:** High

**Resolution:** OPEN / explicitly outside current qualification boundary.

M1 remains a local single-writer proof. Production mutation must not be authorized until a project-owned coordination or uniqueness mechanism is selected and independently verified. CI/runtime claim text now states that concurrent-writer qualification is not established.

---

## M1-F16 — Action API identity lookup assumed Items lived in namespace 0

**Area:** canonical mutation / strongly consistent reconciliation

**Finding:** The first real post-remediation adapter run reached M1 preflight but could not resolve seeded `SDA-ORG-BOEING`. M0 had created Boeing correctly; the inverse lookup enumerated `allpages` only in namespace 0 and accepted only bare `Q...` titles, while the verified M0 client addresses entity pages through the configured `Item:` namespace.

**Why it matters:** The guard correctly failed closed, but the claimed Action-API reconciliation path was not actually complete for this Wikibase configuration. A reconciliation index that misses existing canonical entities cannot prove absent/equivalent/conflict state.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED and VERIFIED.

M1 now discovers the configured Item namespace from Action API `siteinfo`, enumerates that namespace directly from MediaWiki state, and extracts Q-IDs from either bare or namespaced page titles. The clean-stack runtime test explicitly proves that the seeded RSAF, Boeing, and F-15SA canonical IDs resolve to their expected Q-IDs before proposal execution begins. WDQS remains excluded from mutation reconciliation because its index is asynchronous. The clean-stack `wikibase-verification` run passed at commit `27585c70e719d7049a4933bbf6bc2e4e3bc90bc3`.

---

## M1-F17 — Pure replay could manufacture a second project Revision

**Area:** canonical revision / replay semantics

**Finding:** A fully equivalent replay returns `converged` with every effect marked `already_applied`. The Revision builder previously accepted that execution and could construct another project Revision with a new `applied_at`, even though the replay performed no new canonical mutation.

**Why it matters:** Backend idempotency and project revision history are different concerns. A read-only replay should prove convergence and recover/reuse the existing Revision, not create a second canonical application record.

**Severity:** High

**Confidence:** High

**Resolution:** FIXED in implementation; final CI rerun pending.

`build_revision()` now requires at least one execution effect with status `applied` in addition to full convergence. A pure `already_applied` replay remains a valid convergence result but is rejected for Revision creation. The static Revision validator now proves this boundary explicitly.

## Verification boundary after remediation

All implementation fixes through M1-F17 require green `schema-validation` and clean-stack `wikibase-verification` at the final PR head. Concurrent-writer uniqueness remains intentionally unqualified under M1-F15.
