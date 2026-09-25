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

## Verification boundary after remediation

The branch must re-establish both green schema/governance validation and a green clean-stack `wikibase-verification` run at the remediation commit. Until those checks pass, fixes above are implementation changes rather than verified results.
