# M4 Semantics Adjudication — SA-01/SA-02 Remediation Record

## Protocol

This record remediates the two findings raised against the semantics-adjudication increment: SA-01 from first-pass review `5375506680` and SA-02 from re-review `5376366246` (corroborated by fallback second review `5376381128`, reduced reviewer independence; Codex remained quota-blocked). The maintainer first-pass record `M4_SEMANTICS_ADJUDICATION_FIRST_PASS.md` is restored byte-identical to its frozen `48a3389…` content and is not modified by this remediation; corrections live here.

## SA-01 — REP-02 grounding overstated the ontology — REMEDIATED at `6983c94`

The first-pass record's REP-02 rationale claimed the ontology defines entities as "bearers of relationships." The ontology defines Entity as "a stable project identity for a real-world or conceptual domain thing" — a first-class domain identity with its own type, naming, aliases, and lifecycle — and states no such claim. The decision record's "canonize nouns" phrasing was additionally incompatible with the candidate-only authority boundary.

The semantic correction (landed at `6983c94d3cabba5c597c74fe210aefe29166ac07` and retained): the entity-set rule is a **chosen bounded-M4 model-trial candidate-output convention**, motivated by the current claim/event-only proposal surface (the resolver materializes evidence, claim, and event mutations and has no standalone Entity mutation) and the exact-gold evaluation target — not an ontology invariant. The "canonize nouns" phrasing is withdrawn in favor of unused-Entity-candidate / entity-set-noise framing, the architecture language states "supports and motivates, does not dictate," and an explicit forcing function requires re-adjudication if M4 gains a standalone Entity proposal path or any other consumer of standalone extracted entities. The corrected framing lives in the semantics contract, the adjudication decision record, the trial document, and the ROADMAP. The reconciliation validator's extra-entity regression was strengthened to assert `entities-semantics` is specifically the failing check.

## SA-02 — the frozen first-pass record was rewritten — REMEDIATED here

The `6983c94` commit edited the frozen maintainer first-pass record in place, making the named first-pass artifact retrospectively correct instead of preserving what the maintainer concluded before external review. That broke the record's function as the immutable pre-review baseline.

Remediated by this commit: `M4_SEMANTICS_ADJUDICATION_FIRST_PASS.md` is restored byte-identical to its `48a3389…` blob — including the now-known-unsupported REP-02 ontology rationale, preserved as historical evidence, not endorsement. All post-review correction and provenance lives in this record. The corrected semantic state of the contract, decision record, trial document, ROADMAP, and validator from `6983c94` is retained unchanged.

## What changed and what did not

Changed by this remediation: the first-pass record (restored, not edited forward) and this new record. Not changed: the semantics contract, the adjudication decision record, the trial document, the ROADMAP, the reconciliation validator (all retained in their `6983c94` remediated state); prompt v0.8, corpus v0.4, the frozen historical corpus, the resolver, the evaluator, the adapter, and every preserved evidence artifact.

## Validation

The complete 39-validator suite passes at the remediation head; exact-head CI evidence accompanies the push.

## Freeze

This record completes remediation of SA-01 and SA-02. The head carrying this record awaits the final exact-head re-review before PR #39 may merge.
