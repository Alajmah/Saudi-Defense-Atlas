# M4 Extraction Semantics Contract — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the extraction semantics contract increment, performed before any independent second review. It follows the repository rule that first-pass defect finding belongs here.

## Baseline and review surface

Base branch / merge base:

- `main` at `1493d5ffd2c087c2b2c008a532ecd317bfb338e8` (squash merge of PR #32), verified via `git rev-parse main` after fast-forward pull.

Implementation baseline reviewed before this review record was added:

- `m4/extraction-semantics-contracts` at the implementation commit recorded with this branch's push (the commit preceding this record).

Net surface:

1. `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md` (new — the normative contract)
2. `docs/M4_MODEL_EXTRACTION_TRIAL.md`
3. `docs/ROADMAP.md`
4. `scripts/run_m4_model_extraction_trial.py`
5. `scripts/validate_m4_model_extraction_trial.py`
6. `scripts/validate_m4_model_extraction_trial_fallback_review.py`
7. `scripts/validate_m4_model_extraction_trial_zai_provider.py`
8. `services/intelligence/model_extraction_trial.py` (prompt template and version only)

Not changed: the corpus fixture and gold (byte-identical to `main`), the candidate/canonical schemas, the Resolver/Verifier, the boundary's enforcement logic, the evidence artifacts, and all frozen review records.

## What this increment delivers against the frozen findings

### RRV6-02 (HIGH) — role-selection semantics

The semantics contract defines the selection rule: a participant's role names the relation the source explicitly states between that participant and the event; the most specific stated relation wins; generic roles are fallbacks. Per-relation anchors come from the predicate registry itself: `contract.awarded_to.company` makes the company party to a contract signature `contractor`; `manufacturer.manufactures.equipment` makes a stated manufacturing relation `manufacturer`; `exercise.participant.organization` makes exercise/training attendance `participant`; `supplier` applies only when supply is all the source states. The rule is **evaluated, not enforced** — the boundary already guarantees the eleven-role vocabulary; which member is correct is semantic and is scored against gold. Prompt v0.5 instructs the rule.

Derivation-legitimacy check: every gold role in the corpus (delivery producer = `manufacturer`, contract company party = `contractor`, training attendee = `participant`) was fixed before any live run; the rule aligns with that pre-existing gold, not with the rerun's `supplier` outputs. The specificity principle grounds in the ontology's registered-predicates discipline.

### RRV6-03 (MEDIUM) — unit normalization

The contract defines the counted-class rule: `unit` is the bare counted-class noun with role and type modifiers removed ("12 trainer aircraft" → `aircraft`); `null` when no countable unit. The derivation note states honestly that the canonical layer carries no unit vocabulary at all (the Wikibase backend stores unitless quantities), so this is a **defined convention** grounded in the ontology's entity typing and consistent with pre-existing gold (`aircraft`), explicitly superseded by any future canonical unit vocabulary. **Evaluated, not enforced** — mechanical enforcement would require knowing the counted entity's class, which is itself model output. Prompt v0.5 instructs the rule.

### RRV6-01 (MEDIUM) — substantive-extraction denominator

Report v0.7 classifies every case by its gold expectation into substantive (expects accepted extraction), expected-abstention (expects safe rejection), and policy-gate (never invoked) — three first-class metric pairs, alongside the retained invoked-case and whole-corpus rates, each labeled. The contract states the interpretation rule outright: `substantive_quality_case_pass_rate` is the only figure that measures extraction against substantive gold; the invoked-case rate is an outcome metric, never semantic accuracy. **Enforced** as report mechanics; deterministic validators assert the split (4 substantive, 1 expected-abstention, 1 policy-gate on the current corpus, with the deterministic fake outputs passing all three).

## Deliberate non-choices

- Gold is untouched: every rule was written against the predicate registry, the ontology, and pre-existing gold; if a future contract supersedes a rule, gold changes only then, with version bumps.
- No mechanical enforcement of role selection or unit normalization: both are semantic judgments; enforcing them mechanically would encode model output as truth. The boundary continues to enforce only representation conventions.
- Prompt version bumped v0.4 → v0.5 (two new instructed rules); adapter stays `m4-model-trial-v0.3` (boundary logic unchanged); report bumped to v0.7 (new metric surface).

## Findings during implementation

1. The harness validator's first placement of the new prompt-fragment checks referenced `base_case` before its definition (`UnboundLocalError`); relocated after the definition and re-run. Caught by the suite, never pushed.
2. The fallback version-pin validator again forced the template bump (v0.4 → v0.5 refusal until updated), as designed.

## Deterministic validation evidence

- Complete repository suite at the implementation head: all 38 `scripts/validate_*.py` validators — **PASS**, including the new prompt-fragment checks for both semantics rules, the v0.5 template pin, the v0.7 report assertion, and the three-way denominator assertions on the deterministic corpus.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` and `wikibase-verification` on the same tip.

## Explicitly unverified / unresolved

- Whether GLM-5.3 follows the two newly instructed rules is unknown until the next reviewed live rerun, which additionally requires a fresh run-specific operator entitlement attestation.
- The role-selection and unit rules remain unproven as *model-quality instruments* until a rerun under prompt v0.5 is reviewed; this increment defines the semantics, it does not measure the model against them.
- RRV6-04 and RRV6-05 (causal attribution, performance representativeness) are unaffected by this increment and remain open constraints on claim wording.
- The semantics contract's evaluated rules would benefit from a future canonical home (ontology/schema annotations) if they stabilize; today they live in the trial contract deliberately.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review before the next live rerun is scheduled.
