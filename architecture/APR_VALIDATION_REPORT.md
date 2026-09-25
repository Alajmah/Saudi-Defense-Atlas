# APR Validation Report

**Date:** 2026-09-25

**Scope:** Initial Architecture Pattern Register establishment on `bootstrap/foundation`.

## Summary

The register is operational enough to govern M0. No pattern is marked VERIFIED. Wikibase is trial-authorized only. PostgreSQL remains a deferred fallback. Known authority and schema gaps are carried as explicit M0 work rather than hidden as established facts.

## Validation results

| ID | Validation | Result | Notes |
|---|---|---|---|
| V-01 | Provenance | PASS | Every initial source-derived/project-derived pattern points to a source-ledger record or project artifact. |
| V-02 | Status separation | PASS | Pattern, implementation, and planning states are independent. |
| V-03 | Forcing function | PASS | Accepted/trial patterns have project-local forcing functions. |
| V-04 | Authority | PASS WITH GAP | Architectural/planning authority is identified; concrete canonical mutation actor remains an M0 implementation decision behind the accepted proposal/review contract. |
| V-05 | Claim ceiling | PASS | Wikibase trial and schema work are explicitly bounded; no production-readiness claim is made. |
| V-06 | Vocabulary sovereignty | PASS | Wikibase/PostgreSQL remain mechanisms; project-native ontology remains independent. |
| V-07 | Negative evidence | PASS | Deferred fallback and first-pass findings are retained. |
| V-08 | Unknown handling | PASS | Unresolved storage, identity, and confidence details are explicit. |
| V-09 | Implementation proof | PASS | No pattern is marked IMPLEMENTED or VERIFIED without evidence. |
| V-10 | Historical integrity | PASS | Foundation review is frozen rather than rewritten after implementation. |
| V-11 | Effect uncertainty | NOT YET APPLICABLE | No external-effect execution mechanism exists yet. |
| V-12 | Scope creep | PASS | Register reflects already-authorized M0 work and does not add later roadmap scope. |

## Open governance gaps

### G-01 — Canonical mutation implementation

The project has adopted the `ChangeProposal -> ReviewDecision -> Revision` invariant, but M0 still needs an executable schema and adapter contract.

### G-02 — Domain identity versus store identity

M0 must decide whether canonical public IDs are project-issued and mapped to backend IDs, or whether another stable identity mechanism is used. Store-native IDs cannot silently become the domain contract.

### G-03 — Document identity and evidence locator semantics

M0 must make publisher (`Source`), retrieved artifact (`Document`), and claim-bearing locator/span (`Evidence`) non-overlapping in executable schemas.

### G-04 — Technology verification

APR-003 remains NOT-LINKED/TRIAL-AUTHORIZED until the local Wikibase spike exists. No conclusion should be drawn from product documentation alone.

## Validation disposition

**GO for M0 schema implementation and bounded Wikibase spike.**

This is not an approval for production deployment or public-data publication.