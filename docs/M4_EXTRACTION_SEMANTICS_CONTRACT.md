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
- an organization that conducts or leads an exercise or training event is annotated `participant` (RRV7-02): the canonical predicate registry defines exercise involvement only as `exercise.participant.organization`, no conductor role exists in the vocabulary, and this trial does not invent one. `host` is reserved for a source-stated hosting or venue relation specifically — "conducted" does not state hosting;
- `buyer`, `seller`, `operator`, `recipient`, `host`, `observer`, `other` — as stated by the source.

One role per participant per event. Where the source supports more than one stated relation, the convention prefers the more specific one; this preference mirrors the ontology's precision discipline (registered, specific predicates over generic labels) without being implied by it.

### Status

**Evaluated, not enforced.** The boundary already guarantees roles come from the canonical eleven-role vocabulary (mechanically enforced since the contract revision). Which member of that vocabulary is correct is semantic; the exact-gold evaluator scores it against gold that encodes these conventions (delivery producer = `manufacturer`, contract company party = `contractor`, training attendee = `participant` — all fixed in the corpus before any live run). Prompt template v0.6 instructs the model in these conventions.

### Provenance note

The predicate registry (`contract.awarded_to.company`, `manufacturer.manufactures.equipment`, `exercise.participant.organization`) inspired these mappings and is consistent with them, but the registry relates entities to entities; it does not by itself assign event-participant roles, and the ontology states no role-precedence law. Unlike the delivery and contract mappings, the conducted fallback is a direct registry consequence: participation is the registry's only exercise relation, so it is the strongest-grounded convention here. The conventions above were fixed against the pre-existing corpus gold, not against the rerun's `supplier` or `host` outputs. They are trial annotation choices and make no claim about canonical SDA semantics; a future ontology-level role semantics would supersede them.

## Equipment typing convention (RRV7-01)

### The designation rule

A **named discrete equipment product** — a specific designation the source uses for a countable, deliverable, or operable item — is annotated `equipment_variant`, whether or not the source uses the word "variant". A generic equipment class or family reference is annotated `equipment`.

### Classification, not inference

The v0.7 review identified a tension: the extraction prompt requires the variant distinction while also forbidding inference of unstated facts, and the trial source calls Falcon-X an aircraft without saying "model" or "variant". This convention resolves it: entity typing is SDA's **classification of the named thing**, not a factual claim about what the source said. The recorded fact remains exactly what the source states (the source names Falcon-X); the type places that named thing in SDA's ontology. No unstated fact is inferred.

### Provenance note

Canonical SDA precedent distinguishes named discrete products as variants of families: F-15SA carries a `variant_of` relation to the F-15 family, and PAC-3 MSE's own designation names a segment enhancement within the PAC-3 family. The ontology defines EquipmentVariant as "a specific model/variant, separated from the equipment family when facts differ materially by variant." The distinguishing signal in canonical data is the presence of a specific product designation, never the literal word "variant". The corpus gold expected `equipment_variant` for Falcon-X before any live run; this convention justifies that expectation independently. **Adjudicated 2026-10-01 (REP-01):** the Arabic corpus entity "منظومة التدريب ألفا" (Alpha training system) carries the specific designation "ألفا" and appears in explicit supply context ("لتوريد", to supply), so under this rule it is a named discrete deliverable and `equipment_variant` is the correct type; corpus gold was updated accordingly in fixture `m4-model-extraction-eval-v0.4` (the single gold change in that bump, with the historical scores' non-comparability recorded in the adjudication decision record).

### Status

**Evaluated, not enforced.** Both types remain schema-valid; typing stays prompt-instructed (rule 13 of prompt v0.7 carries the clarified rule) and is scored by the exact-gold evaluator. Mechanical enforcement would require an ontology-external designation classifier and remains out of scope.

## Entity-set rule (REP-02)

### The claim/event-driven rule

An Entity record is expected **only when that entity fills a role in the same extraction** — as the subject or value of an emitted Claim, or as a participant or related entity of an emitted Event. Source-supported noun phrases that no emitted Claim or Event uses are not emitted, even when representable.

Neither exhaustive nor abstractly minimal, the rule is claim/event-driven: entities are the bearers of relationships, and this trial's downstream architecture admits entity semantics into proposals exclusively through Claims and Events — the resolver/verifier materializes evidence, claim, and event mutations and never a standalone entity mutation. An entity record with no propositional role has no downstream representation.

### Status

**Evaluated, not enforced.** The boundary does not reject an extraction for an unused entity: an extra source-grounded entity is a scoring miss, not an integrity violation. The exact-gold evaluator scores the entity set exactly, and prompt template v0.8 instructs the rule.

### Reconciliation with gold

The quantity case's gold (Project Cedar only) was already minimal and required no change; the rule independently justifies the expectation that gold previously enforced without stating. The observed `trainer aircraft` outputs from the repeatability trial (R1-R5, all five runs emitting the counted-class phrase as an extra `equipment` entity) remain exact-gold failures under this rule, now grounded in a stated convention rather than an unstated one.

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
- `policy_gate_case_count` / `policy_gate_case_pass_count` / `policy_gate_case_pass_rate` (field names from v0.6; membership is now gold-based);
- the retained `invoked_quality_case_pass_rate`, computed directly over **all observed invocations** regardless of gold expectation (an unexpectedly invoked policy-gate case counts here as a failure as well as in the policy denominator), and the whole-corpus rate, each labeled as such.

`invoked_quality_case_pass_rate` is an invoked-case outcome metric and must never be described as semantic extraction accuracy. **`substantive_quality_case_pass_rate` is the only figure that measures extraction against substantive gold.**

### Status

**Enforced** (report mechanics): computed by the runner from gold expectations, which are validated before any model invocation — unique non-empty case IDs, object-valued gold, and exactly one of the three legal expected statuses per case; deterministic validators assert the split and the preflight rejections.

## Claim ceiling

This contract defines evaluation semantics for the bounded trial. It does not qualify model quality, does not change gold, and does not grant any authority. Gold changes only if a future, independently justified contract supersedes a rule here, with the required version bumps.
