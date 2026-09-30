# M4 Extraction Semantics Contract

## Status

Defines the three semantics the 2026-09-30 rerun review found under-specified (RRV6-01, RRV6-02, RRV6-03): Event participant-role selection, numeric-unit normalization, and the substantive-extraction quality denominator.

The role and unit rules below are **bounded-trial annotation conventions**. They are consistent with SDA's canonical vocabulary and with the pre-existing corpus gold (which predates both live runs), but the canonical contracts do not themselves imply them: the Event schema supplies the eleven-role vocabulary without precedence semantics, the ontology registers predicates without stating a role-selection law, and the canonical quantity layer has no unit vocabulary. No rule here is derived from observed model output.

The denominator definitions are report mechanics, not annotation semantics, and are marked **enforced** where checked mechanically. Rules marked **evaluated** are scored by the exact-gold evaluator but not mechanically policed at the candidate boundary.

## Event participant-role selection (RRV6-02)

### The annotation conventions

For this trial, a participant's role is annotated as follows. These conventions are chosen, not canonical:

- when the source states that the producing party **manufactured** the equipment, annotate `manufacturer` — including in delivery events, where the source often states both delivery and manufacture (a `supplier` label would discard the stated manufacture relation);
- the company party to a `contract_signature` or `contract_award` event is annotated `contractor`;
- `supplier` is used only when supply is all the source states for that participant in that event;
- exercise and training attendance without a more specific stated relation is annotated `participant`;
- `buyer`, `seller`, `operator`, `recipient`, `host`, `observer`, `other` — as stated by the source.

One role per participant per event. Where the source supports more than one stated relation, the convention prefers the more specific one; this preference mirrors the ontology's precision discipline (registered, specific predicates over generic labels) without being implied by it.

### Status

**Evaluated, not enforced.** The boundary already guarantees roles come from the canonical eleven-role vocabulary (mechanically enforced since the contract revision). Which member of that vocabulary is correct is semantic; the exact-gold evaluator scores it against gold that encodes these conventions (delivery producer = `manufacturer`, contract company party = `contractor`, training attendee = `participant` — all fixed in the corpus before any live run). Prompt template v0.6 instructs the model in these conventions.

### Provenance note

The predicate registry (`contract.awarded_to.company`, `manufacturer.manufactures.equipment`, `exercise.participant.organization`) inspired these mappings and is consistent with them, but the registry relates entities to entities; it does not by itself assign event-participant roles, and the ontology states no role-precedence law. The conventions above were fixed against the pre-existing corpus gold, not against the rerun's `supplier` outputs. They are trial annotation choices and make no claim about canonical SDA semantics; a future ontology-level role semantics would supersede them.

## Numeric-unit normalization (RRV6-03)

### The head-noun rule

The `unit` string is the **head noun of the counted-class phrase the source itself states**, with role and type modifiers removed:

- "12 trainer aircraft" → unit `aircraft` (trainer modifies the aircraft's role, not the counted class);
- a source counting "نظام تدريب" (training systems) → the head noun of the stated class phrase.

When the source counts by designation only, with no class noun (for example "84 F-15SA"), the unit is the designation exactly as stated — this rule performs no semantic entity classification. `null` remains the value when the source states no countable unit. A semantic class-to-unit mapping (designation → class noun) is deliberately **not** defined here; until one is independently justified, exact-gold scoring treats the source-stated string as normative.

### Status

**Evaluated, not enforced.** Mechanical enforcement is not possible without independently knowing the counted entity's class, which is itself model output; the evaluator scores the unit by exact equality against gold. Prompt template v0.6 instructs the rule.

### Derivation note

The canonical quantity layer carries no unit vocabulary at all (the backend stores unitless quantities), so no canonical normalization rule can be cited. This is a defined trial convention: a lexical head-noun normalization of the source's own counted-class phrase, consistent with the corpus gold, which used the bare noun (`aircraft`) before any model output existed. It deliberately performs no semantic classification. A future canonical unit vocabulary, or an independently justified class-to-unit mapping, would supersede this rule and require a corpus/evaluator version bump.

## Substantive-extraction quality denominator (RRV6-01)

### Definitions

A corpus case is:

- **substantive** when its gold expects `accepted_for_candidate_review` — the model is expected to extract substantive candidates;
- **expected-abstention** when its gold expects `rejected` — the model is expected to abstain and be rejected safely;
- **policy-gate** when its gold expects `blocked_before_invocation` — the case must never reach the model.

Bucket membership comes **solely from each case's gold expectation**, never from observed behavior: a substantive-gold case that is unexpectedly blocked before invocation remains in the substantive denominator and counts as a failure there, rather than disappearing into the policy bucket. Observed invocation is reported separately (`invoked_case_count`). Report v0.7 exposes all three denominators as first-class metrics:

- `substantive_quality_case_pass_count` / `substantive_quality_case_pass_rate` over `substantive_case_count`;
- `expected_abstention_quality_case_pass_count` / `expected_abstention_quality_case_pass_rate` over `expected_abstention_case_count`;
- `policy_gate_case_pass_count` / `policy_gate_case_pass_rate` (unchanged from v0.6);
- the retained `invoked_quality_case_pass_rate` (substantive + expected-abstention) and whole-corpus rate, each labeled as such.

`invoked_quality_case_pass_rate` is an invoked-case outcome metric and must never be described as semantic extraction accuracy. **`substantive_quality_case_pass_rate` is the only figure that measures extraction against substantive gold.**

### Status

**Enforced** (report mechanics): computed by the runner from gold expectations; deterministic validators assert the split.

## Claim ceiling

This contract defines evaluation semantics for the bounded trial. It does not qualify model quality, does not change gold, and does not grant any authority. Gold changes only if a future, independently justified contract supersedes a rule here, with the required version bumps.
