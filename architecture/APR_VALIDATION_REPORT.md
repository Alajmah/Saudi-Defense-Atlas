# APR Validation Report

**Date:** 2026-09-25

**Scope:** M0 architecture/governance state after schema, mutation-governance, and Wikibase verification on `bootstrap/foundation`.

## Summary

The register is consistent with the completed M0 evidence. Wikibase is now accepted and `VERIFIED` only for the bounded knowledge-core representation/query/governance contract established by ADR-0002. PostgreSQL remains a deferred fallback. The review-gated mutation pattern is verified for the tested M0 adapter boundary, while production effect reconciliation remains explicitly unresolved.

## Validation results

| ID | Validation | Result | Notes |
|---|---|---|---|
| V-01 | Provenance | PASS | Architecture claims link to project artifacts and exact M0 workflow/artifact evidence. |
| V-02 | Status separation | PASS | Pattern, implementation, and planning states remain independent; bounded verification is not presented as production qualification. |
| V-03 | Forcing function | PASS | Accepted patterns have concrete project-local need. PostgreSQL stays deferred because no forcing function currently activates it. |
| V-04 | Authority | PASS | Canonical mutation authority is explicit: proposal + policy + review bind the exact payload before backend execution; Revision records the resulting effect/receipt. |
| V-05 | Claim ceiling | PASS | ADR-0002 and APR entries explicitly exclude production security, HA, scale, backup, exactly-once, and ambiguous-effect recovery from M0 claims. |
| V-06 | Vocabulary sovereignty | PASS | SDA IDs/domain semantics remain canonical; Q/P IDs and Wikibase vocabulary remain implementation mappings. |
| V-07 | Negative evidence | PASS | PostgreSQL fallback, unresolved production properties, and adversarial findings are retained. |
| V-08 | Unknown handling | PASS | Unverified production properties remain explicit rather than inferred from local M0 success. |
| V-09 | Implementation proof | PASS | `VERIFIED` statuses cite exact current-head CI evidence and are bounded to tested contracts. |
| V-10 | Historical integrity | PASS | Foundation first-pass remains frozen; later adversarial findings are appended separately. |
| V-11 | Effect uncertainty | PASS WITH GAP | M0 establishes authorization-before-effect and receipt-after-effect. Interrupted/ambiguous-effect reconciliation and retry semantics remain unverified production work. |
| V-12 | Scope creep | PASS | Promotion authorizes the already-planned M1 knowledge-core role only; production infrastructure work is not silently authorized. |

## Closed M0 governance gaps

### G-01 — Canonical mutation implementation — CLOSED for M0

Executable schemas and cross-record validation now implement `ChangeProposal -> ReviewDecision -> Revision`. The adapter proof demonstrates exact proposal-hash binding and AMBER human approval before the backend call.

### G-02 — Domain identity versus store identity — CLOSED

SDA project-issued IDs are canonical and explicitly mapped to backend Q/P IDs. The current-head Wikibase verification demonstrates `SDA-ORG-RSAF` and Q1 as distinct identities.

### G-03 — Document identity and evidence locator semantics — CLOSED for schema v0.1

`Source`, `Document`, and `Evidence` have separate executable schemas and provenance responsibilities.

### G-04 — Knowledge-core technology verification — CLOSED for M0

Wikibase passed the bounded M0 acceptance matrix on implementation head `e3d08935907d85c20da12531a81a22d43e23f597` in workflow run `36178040438`; evidence artifact `10883261546` records the passing representation/query/adapter checks.

## Open post-M0 governance/verification gaps

### G-05 — Ambiguous external-effect reconciliation

A production canonical adapter must define idempotency keys, retry semantics, reconciliation after interrupted requests, and how `unknown effect` differs from success/failure. M0 does not establish exactly-once semantics.

### G-06 — Production Wikibase qualification

Separate decisions/evidence are required for authentication/authorization, backup/recovery, deployment topology, upgrades, target-scale performance, observability, and availability.

### G-07 — Actual AI extraction boundary

Typed candidate/proposal schemas are implemented and mechanically verified, but M1 must prove that a real extraction path produces schema-bound proposals and cannot bypass canonical governance.

### G-08 — Source-to-public-view traceability

M1 must demonstrate one authoritative source flowing through Document/Evidence/Claim into Wikibase and a bilingual public page without copying facts into an independent CMS truth store.

## Evidence summary

- Schema/mutation governance: run `36178033709` — success.
- Wikibase M0 current-head run: `36178040438`, job `108213344752` — success.
- Verification artifact: `10883261546` — status `PASS` for the bounded M0 representation mechanics and approved synthetic adapter proof.
- Decision: `docs/adr/ADR-0002-knowledge-core.md` — Wikibase accepted for M1 knowledge-core role.

## Validation disposition

**GO for M1 first vertical slice.**

This is not approval for production deployment or unrestricted public-data publication. M1 remains governed by the source policy, AI publication policy, operational-sensitivity boundary, and the unresolved gaps above.
