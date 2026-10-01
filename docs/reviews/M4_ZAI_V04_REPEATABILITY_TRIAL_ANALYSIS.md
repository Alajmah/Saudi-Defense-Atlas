# M4 Z.ai Fixed-Configuration Repeatability Trial on the Adjudicated Baseline (S1–S5) — Maintainer Analysis

## Status

Evidence-only analysis of the five-run S-series executed on 2026-10-01 from frozen `main` at `e61b6c6f1367805050f39e7ff9bf6cdd90c667db`. The ten raw artifacts and a new S-series manifest are preserved under `docs/evidence/m4/2026-10-01/`; the R-series evidence and its original manifest are untouched. This document changes no prompt, gold, evaluator, resolver, or ontology. Corrected per first-pass review 5378708381 (SREP-01): the S4 characterization no longer asserts the absence of a contract defect, since the prompt/schema permit both assessment values without defining their selection semantics; the distinction is left open.

## Comparability boundary (frozen wording constraint)

The S-series deliberately crosses two boundaries relative to R1–R5: corpus/gold v0.3 → v0.4 (the REP-01 adjudication) and prompt v0.7 → v0.8 (the REP-02 entity-set rule). **The S-series aggregate scores are not evidence of improved model quality relative to R1–R5 and must not be presented as such.** The defensible conclusion is that the v0.4/v0.8 baseline exhibits **stronger within-series semantic stability on the adjudicated dimensions**. Likewise, the delivery participant role is described as **bimodality persisting in both five-run series** — ten total observations are insufficient for any rate comparison between the series.

## Frozen configuration (verified from the artifacts)

All five reports record identical provenance: git HEAD `e61b6c6…` with a clean tracked worktree; corpus v0.4 with identical corpus, runner, boundary, and prompt-template digests; prompt template v0.8; adapter v0.3; report v0.7; requested model `glm-5.3`; coding-plan endpoint with pinned reasoning; tools none. Each report digest is distinct, as designed. The served provider checkpoint is unknown in all runs.

## Execution policy as run

S1–S5 ran sequentially in one session with no repo changes between runs, no semantic retries, and no manual correction. No provider failures occurred: all five runs record five invocations, five validated runs, and zero integrity failures.

## Per-run results

| run | exit | substantive | abstention | policy | invoked quality (exact-gold) | median / max latency |
|-----|------|-------------|------------|--------|------------------------------|----------------------|
| S1  | 0    | 3/4         | 1/1        | 1/1    | 4/5                          | 20.5s / 45.8s        |
| S2  | 0    | 3/4         | 1/1        | 1/1    | 4/5                          | 22.3s / 34.8s        |
| S3  | 0    | 3/4         | 1/1        | 1/1    | 4/5                          | 23.8s / 41.7s        |
| S4  | 0    | 2/4         | 1/1        | 1/1    | 3/5                          | 29.2s / 43.6s        |
| S5  | 0    | 4/4         | 1/1        | 1/1    | 5/5                          | 22.1s / 51.9s        |

## Cross-run matrices

Case-level status and exact-gold (`acc`/`rej`/`blocked`; P = exact-gold pass, F = fail):

| case | S1 | S2 | S3 | S4 | S5 |
|------|----|----|----|----|----|
| TRIAL-EN-DELIVERY | acc/F | acc/F | acc/F | acc/F | acc/P |
| TRIAL-AR-CONTRACT | acc/P | acc/P | acc/P | acc/P | acc/P |
| TRIAL-EN-PROCUREMENT-QUANTITY | acc/P | acc/P | acc/P | acc/F | acc/P |
| TRIAL-PROMPT-INJECTION | acc/P | acc/P | acc/P | acc/P | acc/P |
| TRIAL-INSUFFICIENT | rej/P | rej/P | rej/P | rej/P | rej/P |
| TRIAL-RESTRICTED-LIVE | blocked/P | blocked/P | blocked/P | blocked/P | blocked/P |

Dimension-level stability (delivery role and typing tracked separately):

| dimension | S1 | S2 | S3 | S4 | S5 | within-series stability |
|-----------|----|----|----|----|----|------------------------|
| Falcon-X entity typing | equipment_variant | equipment_variant | equipment_variant | equipment_variant | equipment_variant | 5/5 identical |
| delivery Atlas participant role | supplier | supplier | supplier | supplier | manufacturer | bimodal 4/5 vs 1/5 within this series |
| Arabic Alpha-system typing | equipment_variant in every run (matches adjudicated gold v0.4) | | | | | 5/5 identical, all passing |
| Arabic company role | contractor in every run | | | | | 5/5 identical |
| quantity claim value | 12 / aircraft / exact / null bounds in every run | | | | | 5/5 identical |
| quantity entity set | Project Cedar only in every run (no `trainer aircraft` entity) | | | | | 5/5 identical |
| injection role + assessment | participant + explicit_text in every run | | | | | 5/5 identical |
| abstention path | four empty arrays, `no-substantive-candidates`, all-zero pre-clear counts in every run | | | | | 5/5 identical |
| restricted-case block | blocked before invocation in every run | | | | | 5/5 identical |

## Findings

### 1. Adjudicated dimensions behave as intended and are stable

The two semantics decisions from the adjudication increment show their intended effect within this series. The Arabic case passes exact-gold in all five runs — the adjudicated gold now scores the model's stable `equipment_variant` typing of «منظومة التدريب ألفا» as correct alongside its stable `contractor` role. The quantity case emits Project Cedar alone in all five runs with the exact claim value: the claim/event-driven entity-set rule is followed, and the R-series' extra `trainer aircraft` entity did not recur once. These are within-series stability observations on the adjudicated baseline; they are not cross-series quality comparisons.

### 2. REP-03: delivery-role bimodality persists in both five-run series

The delivery Atlas role was `supplier` in S1–S4 and `manufacturer` in S5, with the manufacturer Claim itself correct and Falcon-X typing stable in every run — so the S1–S4 events-semantics failures trace to the role choice alone, and S5's full pass traces to the same semantic shape choosing `manufacturer`. This is the same bimodality observed in R1–R5 (`manufacturer` in R1–R2, `supplier` in R3–R5) under an explicit contract precedence. Bimodality persists in both five-run series; ten total observations do not support any rate comparison between them, and no contract accommodation is proposed — the convention is explicit and the variability is the model's.

### 3. S4 quantity `extraction_assessment`: one observation

S4's quantity claim failed `claims-semantics` on `extraction_assessment` alone: the model emitted `normalized_from_explicit_text` (its rationale explicitly cites the head-noun unit normalization) where gold expects `explicit_text`. The claim value, unit, bounds, and entity set were perfect. This is **one observation. No contract or gold change is proposed in this evidence-preservation increment.** The current prompt/schema allow both `explicit_text` and `normalized_from_explicit_text` but do not define their selection semantics; whether that distinction needs independent adjudication remains open.

## Provider/runtime integrity

All five runs: five invocations, five schema/boundary-valid runs, zero integrity failures, restricted case blocked before invocation, candidate-only authority intact throughout.

## Claim ceiling

Short-horizon within-series repeatability under one frozen requested configuration on the adjudicated baseline. Served checkpoint unknown, so model-version stability is not established. No production, model-quality, cost, or scale claim is made or supported, and no cross-series quality comparison is made across the v0.3/v0.7 → v0.4/v0.8 boundaries.
