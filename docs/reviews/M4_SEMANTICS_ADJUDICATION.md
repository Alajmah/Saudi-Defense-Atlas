# M4 Semantics Adjudication — REP-01 / REP-02 Decision Record

## Status

Corrected per first-pass review 5375506680 (SA-01): the REP-02 grounding now states the rule as a chosen bounded-trial convention motivated by the current architecture, not an ontology requirement, and the "canonize nouns" phrasing is withdrawn.

Offline, contract-first adjudication of the two repeatability findings the frozen R1–R5 evidence review classified for decision (REP-01, REP-02). No live model call was made. The R1–R5 outputs were treated as observations that motivated the questions, never as normative evidence for the answers; each decision below is grounded in the merged contracts, the corpus sources, and the downstream architecture. The preserved PR #38 evidence is untouched; the historical corpus bytes were additionally frozen in place (see REP-01 mechanics) so the v0.7 downstream replay remains bound to its generation-time context.

REP-03 (delivery role bimodality) is confirmed as evidence only: the manufacturer precedence is already explicit in the contract and prompt rule 17, so the observed `supplier` outputs require no amendment here.

## REP-01 — Alpha-system typing: gold updated to `equipment_variant`

### The source

`TRIAL-AR-CONTRACT`'s synthetic source states: «في 15 مارس 2024، وقّعت شركة النور للصناعات عقداً ضمن برنامج الصقر لتوريد منظومة التدريب ألفا.» — on 15 March 2024, Al-Noor Industries signed a contract within the Saqer program **to supply** the **Alpha** training system.

### The adjudication

The merged designation rule (RRV7-01, prompt rule 13) types a named discrete product — a specific designation for a countable, deliverable, or operable item — as `equipment_variant`, whether or not the source uses the word "variant". The phrase "منظومة التدريب ألفا" carries the specific designation "ألفا" (Alpha) and appears in explicit supply/deliverability context ("لتوريد"). It is therefore a named discrete deliverable, and `equipment_variant` is the correct type. The frozen v0.3 gold's `equipment` expectation was inconsistent with the already-merged rule; the model's stable 5/5 `equipment_variant` outputs were correct readings, not five extraction failures.

### The change

Corpus fixture bumped `m4-model-extraction-eval-v0.3` → **`v0.4`** with exactly two deltas, verified by structural diff against HEAD: the version string, and `TRIAL-AR-CONTRACT` gold entity `منظومة التدريب ألفا` from `equipment` to `equipment_variant`. Prompt v0.7 needed no change for this decision (rule 13 already states the rule); adapter and evaluator behavior are unchanged.

### Mechanics: the frozen historical corpus

The v0.7 downstream replay's provenance gate binds to the corpus bytes the report was generated from. Those bytes are now frozen as `docs/evidence/m4/2026-09-30/corpus/m4-model-extraction-eval-v0.3.json` (LF blob, digest `fe9217ab…`, sidecar beside it, both representations accepted by the gate), and the replay validator reads its queue/gold context from the frozen copy. The live fixture may now evolve without breaking generation-time provenance binding.

## REP-02 — Entity-set rule: claim/event-driven, gold unchanged

### The question

When a source-supported noun phrase is representable as an Entity but is not needed as the subject, object, participant, or related entity of a scored Claim or Event, is extraction expected to be exhaustive, minimal, or otherwise governed?

### The rule

**Claim/event-driven**: an Entity record is expected only when it fills a role in the same extraction — subject or value of an emitted Claim, or participant or related entity of an emitted Event. The rule is recorded in `docs/M4_EXTRACTION_SEMANTICS_CONTRACT.md` (as a chosen trial convention with an explicit re-adjudication forcing function) and instructed as prompt rule 19 (template bumped v0.7 → **v0.8**; no other prompt text changed).

### The independent grounding

Canonical SDA Entity remains a first-class domain identity (a stable project identity for a real-world or conceptual domain thing, with its own type, naming, aliases, and lifecycle); this rule is a chosen bounded-M4 model-trial candidate-output convention and does not alter ontology semantics. What supports the choice: the current downstream proposal surface admits extracted entity semantics into proposals only through Claims and Events — the resolver/verifier (v0.4) materializes evidence, claim, and event mutations and has no standalone Entity mutation — and the trial's exact-gold evaluation target is the scored Claim/Event set. Under that surface, an unused Entity candidate has no downstream representation and only introduces entity-set noise; exhaustive extraction would emit unused Entity candidates, while abstract minimality would forbid legitimate related entities. The current architecture supports and motivates this convention; it does not dictate it. Neither the observed `trainer aircraft` outputs nor any other R1–R5 output was used to derive it. Forcing function: if M4 later gains a standalone Entity proposal/materialization path, or any other consumer of standalone extracted entities, this convention must be re-adjudicated.

### Reconciliation with gold and evaluator

The quantity case's gold (Project Cedar only) was already claim/event-driven and required **no change**; the rule states the convention the evaluator had been enforcing without a written basis. Evaluator behavior is unchanged. The rule is **evaluated, not enforced** at the boundary: an unused source-grounded entity is a scoring miss, not an integrity violation, and a whole extraction is not rejected for one. A regression added to the reconciliation validator proves the scorer fails an extraction carrying an unused extra entity (`entities-semantics`), grounding the expectation in a stated rule.

## Migration note — historical-score non-comparability

Corpus v0.4 changes one gold expectation. The following historical exact-gold results, all evaluated against v0.3 gold, are **non-comparable** against v0.4 and are preserved unchanged in their frozen evidence:

- **`TRIAL-AR-CONTRACT` exact-gold results** in every preserved live artifact: the 2026-09-29 first live trial (v0.5 report), the 2026-09-30 v0.6 rerun, the 2026-09-30 v0.7 rerun (AR **passed** under v0.3 gold because that run typed the system `equipment`), and R1–R5 (AR **failed** 5/5 because those runs typed it `equipment_variant` under the clarified prompt v0.7).
- Consequently, **aggregate rates are non-comparable across the fixture boundary**: whole-corpus, invoked, and substantive rates from those reports cannot be compared to any future v0.4-evaluated run without re-scoring, which no one has done.

**Projection, not measurement:** if the five R1–R5 AR outputs were re-scored against v0.4 gold (all else unchanged, delivery-role outcomes and the quantity extra-entity failures standing), the substantive results would project to 3/4, 3/4, 2/4, 2/4, 1/4. This is a documented counterfactual for planning only; the preserved reports and their recorded rates are unchanged and remain the evidence.

Prompt v0.8 additionally instructs the entity-set rule, so future runs are not configuration-comparable with R1–R5 either (prompt v0.7 vs v0.8). Any repeatability comparison across that boundary requires a new fixed-configuration series.

## Claim ceiling

This adjudication changes evaluation semantics for the bounded trial only. It makes no model-quality claim, attributes no correctness to the model beyond the adjudicated typing reading, and leaves the served-checkpoint unknown.
