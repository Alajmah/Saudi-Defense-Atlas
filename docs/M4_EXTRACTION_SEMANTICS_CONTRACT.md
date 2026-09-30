# M4 Extraction Semantics Contract

## Status

Defines the three semantics the 2026-09-30 rerun review found under-specified (RRV6-01, RRV6-02, RRV6-03): Event participant-role selection, numeric-unit normalization, and the substantive-extraction quality denominator. Every rule below is derived from SDA's own contracts or defined as a documented convention grounded in them; none is derived from observed model output, and the pre-existing corpus gold already conforms to each rule (that alignment predates the live runs and is the legitimacy test applied here).

This contract governs the bounded extraction trial. Where a rule is marked **enforced** it is checked mechanically; rules marked **evaluated** are scored by the exact-gold evaluator but not mechanically policed at the candidate boundary.

## Event participant-role selection (RRV6-02)

### The specificity rule

A participant's role names the relation the source explicitly states between that participant **and this event**. When the source supports more than one relation, the most specific stated relation wins. The generic roles are fallbacks, not defaults:

- `manufacturer` — the source states the participant manufactured the equipment (predicate registry: `manufacturer.manufactures.equipment`).
- `contractor` — the participant is the company party to a contract (predicate registry: `contract.awarded_to.company`; the awarded company is the contractor). This is the normative role for the company side of `contract_signature` and `contract_award` events.
- `supplier` — the source states supply and nothing more specific. When a source states both delivery and manufacture, `manufacturer` is correct for the producing party; `supplier` would discard a stated relation.
- `participant` — the generic role for exercise and training participants (predicate registry: `exercise.participant.organization`), when the source states participation without a more specific relation.
- `buyer`, `seller`, `operator`, `recipient`, `host`, `observer`, `other` — as stated by the source, under the same specificity rule.

One role per participant per event. The role reflects the participant's relation to the event, not to the equipment in general.

### Status

**Evaluated, not enforced.** The boundary already guarantees roles come from the canonical eleven-role vocabulary (mechanically enforced since the contract revision). Which member of that vocabulary is correct is semantic; the exact-gold evaluator scores it against gold that encodes this rule (delivery producer = `manufacturer`, contract company party = `contractor`, training attendee = `participant`). Prompt template v0.5 instructs the model in this rule.

### Derivation note

The canonical schema enumerates role labels without precedence; this contract supplies the selection semantics from the predicate registry's own relations plus the ontology's precision discipline ("predicates must be centrally registered; arbitrary free-text predicates are not allowed" — specificity is the norm; generic labels discard stated facts). The rule was written against the registry and the pre-existing gold, not against the rerun's `supplier` outputs.

## Numeric-unit normalization (RRV6-03)

### The counted-class rule

A quantity counts instances of a counted entity. The `unit` string is the **bare counted-class noun** — the noun naming what is counted, with role, type, and mission modifiers removed:

- "12 trainer aircraft" → unit `aircraft` (trainer modifies the aircraft's role, not the counted class);
- "84 F-15SA" → unit `aircraft` where the corpus counts aircraft;
- a source counting "نظام تدريب" (training systems) → the bare class noun of the counted system.

`null` remains the value when the source states no countable unit.

### Status

**Evaluated, not enforced.** Mechanical enforcement is not possible without independently knowing the counted entity's class, which is itself model output; the evaluator scores the unit by exact equality against gold. Prompt template v0.5 instructs the rule.

### Derivation note

The canonical quantity layer carries no unit vocabulary at all (the backend stores unitless quantities), so no canonical normalization rule can be cited. This contract defines one: the unit names the counted class, consistent with the ontology's entity typing and with the corpus gold, which used the bare noun (`aircraft`) before any model output existed. A future canonical unit vocabulary would supersede this rule and require a corpus/evaluator version bump.

## Substantive-extraction quality denominator (RRV6-01)

### Definitions

A corpus case is:

- **substantive** when its gold expects `accepted_for_candidate_review` — the model is expected to extract substantive candidates;
- **expected-abstention** when its gold expects `rejected` — the model is expected to abstain and be rejected safely;
- **policy-gate** when its gold expects `blocked_before_invocation` — the case must never reach the model.

Report v0.7 exposes all three denominators as first-class metrics:

- `substantive_quality_case_pass_count` / `substantive_quality_case_pass_rate` over `substantive_case_count`;
- `expected_abstention_quality_case_pass_count` / `expected_abstention_quality_case_pass_rate` over `expected_abstention_case_count`;
- `policy_gate_case_pass_count` / `policy_gate_case_pass_rate` (unchanged from v0.6);
- the retained `invoked_quality_case_pass_rate` (substantive + expected-abstention) and whole-corpus rate, each labeled as such.

`invoked_quality_case_pass_rate` is an invoked-case outcome metric and must never be described as semantic extraction accuracy. **`substantive_quality_case_pass_rate` is the only figure that measures extraction against substantive gold.**

### Status

**Enforced** (report mechanics): computed by the runner from gold expectations; deterministic validators assert the split.

## Claim ceiling

This contract defines evaluation semantics for the bounded trial. It does not qualify model quality, does not change gold, and does not grant any authority. Gold changes only if a future, independently justified contract supersedes a rule here, with the required version bumps.
