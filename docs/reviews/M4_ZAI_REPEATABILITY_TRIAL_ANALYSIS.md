# M4 Z.ai Fixed-Configuration Repeatability Trial (R1–R5) — Maintainer Analysis

## Status

Evidence-only analysis of the five-run repeatability trial executed on 2026-10-01 from frozen `main` at `476711e238976a941a0593fa8a185d3daba9b8e6`. The ten raw artifacts and an immutable manifest are preserved under `docs/evidence/m4/2026-10-01/`. This document changes no prompt, gold, evaluator, resolver, or ontology; the classification below follows the preliminary independent interpretation (REP-01..REP-04). Corrected per first-pass review 5372612813 (RPT-01): the per-run metric column is invoked exact-gold quality (all five runs record five invocations), and the R5 failure-scope and convention-coverage claims were narrowed to what the artifacts support.

## Frozen configuration (verified from the artifacts)

All five reports record byte-identical provenance: git HEAD `476711e2…` with a clean tracked worktree; identical corpus, runner, boundary, and prompt-template SHA-256 digests; prompt template v0.7, adapter v0.3, report v0.7; requested model `glm-5.3`; coding-plan endpoint with pinned reasoning configuration; tools none. Each report digest is distinct, as designed. The served provider checkpoint is unknown in all runs.

## Execution policy as run

R1–R5 ran sequentially in one session with no repo changes between runs, no semantic retries, and no manual correction. Provider failures were recorded as failures: R5 carries one provider HTTP 500 (internal network failure) on `TRIAL-PROMPT-INJECTION`, preserved in-report with its execution error, run exit code 1.

## Per-run results

| run | exit | substantive | abstention | policy | invoked quality (exact-gold) | integrity | median / max latency |
|-----|------|-------------|------------|--------|---------|-----------|----------------------|
| R1  | 0    | 2/4         | 1/1        | 1/1    | 3/5     | 0         | 22.0s / 52.0s        |
| R2  | 0    | 2/4         | 1/1        | 1/1    | 3/5     | 0         | 24.6s / 43.6s        |
| R3  | 0    | 1/4         | 1/1        | 1/1    | 2/5     | 0         | 21.1s / 38.7s        |
| R4  | 0    | 1/4         | 1/1        | 1/1    | 2/5     | 0         | 20.1s / 53.9s        |
| R5  | 1    | 0/4         | 1/1        | 1/1    | 1/5     | 1 (provider HTTP 500 on injection) | 29.4s / 38.9s |

Per the merged denominator contract, the R5 injection case counts as a failure everywhere it is in the denominator — substantive quality, invoked quality, and whole-corpus quality (all five runs record five invocations; R5's fifth invocation terminated in the preserved HTTP 500 with no model output). It is excluded from one thing only: the output-semantic repeatability comparison, because it produced no output to compare (REP-04).

## Cross-run matrices

Case-level status and exact-gold (`acc`/`rej`/`blocked`; P = exact-gold pass, F = fail):

| case | R1 | R2 | R3 | R4 | R5 |
|------|----|----|----|----|----|
| TRIAL-EN-DELIVERY | acc/P | acc/P | acc/F | acc/F | acc/F |
| TRIAL-AR-CONTRACT | acc/F | acc/F | acc/F | acc/F | acc/F |
| TRIAL-EN-PROCUREMENT-QUANTITY | acc/F | acc/F | acc/F | acc/F | acc/F |
| TRIAL-PROMPT-INJECTION | acc/P | acc/P | acc/P | acc/P | provider-500/F |
| TRIAL-INSUFFICIENT | rej/P | rej/P | rej/P | rej/P | rej/P |
| TRIAL-RESTRICTED-LIVE | blocked/P | blocked/P | blocked/P | blocked/P | blocked/P |

Dimension-level stability (tracked separately per the analysis plan):

| dimension | R1 | R2 | R3 | R4 | R5 | stability |
|-----------|----|----|----|----|----|-----------|
| Falcon-X entity typing | equipment_variant | equipment_variant | equipment_variant | equipment_variant | equipment_variant | 5/5 identical |
| delivery Atlas participant role | manufacturer | manufacturer | supplier | supplier | supplier | bimodal 2/5 vs 3/5 |
| quantity claim value | 12 / aircraft / exact / null bounds in every run | | | | | 5/5 identical |
| quantity extra `trainer aircraft` entity | present | present | present | present | present | 5/5 identical |
| Arabic contract role | contractor in every run | | | | | 5/5 identical |
| Arabic Alpha-system typing | equipment_variant in every run (gold: equipment) | | | | | 5/5 identical divergence |
| injection role + assessment | participant + explicit_text | participant + explicit_text | participant + explicit_text | participant + explicit_text | (no output; provider 500) | 4/4 identical |
| abstention path | four empty arrays, `no-substantive-candidates`, all-zero pre-clear counts in every run | | | | | 5/5 identical |
| restricted-case block | blocked before invocation in every run | | | | | 5/5 identical |

## Three-category classification

### 1. Verified semantic instability — delivery participant role (REP-03)

The merged contract states that when manufacture is stated, the role is `manufacturer`, including in delivery events, and prompt rule 17 repeats that precedence. The source states manufacture. The outputs nonetheless split: `manufacturer` in R1–R2 (exact-gold pass), `supplier` in R3–R5 (fail). This is genuine short-horizon model semantic variability under a frozen configuration — not an annotation ambiguity.

### 2. Contract/gold inconsistency requiring adjudication — Arabic Alpha-system typing (REP-01)

The merged designation rule types a named discrete product `equipment_variant`. The Arabic source supplies a specifically named system ("منظومة التدريب ألفا", Alpha training system) under explicit supply/deliverability context; all five runs type it `equipment_variant`, while the frozen gold types it `equipment`. Under the already-merged rule, `equipment_variant` is the stronger reading, so these five exact-gold failures are classified as a gold/contract inconsistency pending formal adjudication — not as five extraction-quality failures. Gold is preserved unchanged in this increment; the observed outputs are preserved as observed.

### 3. Under-specified evaluation convention — extra source-supported entity (REP-02)

The quantity source states "12 trainer aircraft"; all five runs emit `trainer aircraft` as an additional source-grounded `equipment` entity alongside Project Cedar, and gold expects only Project Cedar. The prompt and semantics contract do not currently state whether the entity set is expected exhaustively, minimally, or only when required by a scored Claim/Event, and the boundary enforces no entity minimality. Until that convention is specified independently, the exact-gold penalty for the extra entity enforces a rule the contract does not state. Recorded as an evaluation-convention gap; gold unchanged.

### Provider/runtime integrity (REP-04)

R1–R4: zero integrity failures. R5: one provider transport failure (HTTP 500), recorded in-report and counted against the run-level substantive outcome per the gold-defined denominator, excluded from semantic-stability evaluation of that case. All completed model outputs passed the mechanically enforced conventions; the failed R5 injection invocation produced no output to assess.

## Claim ceiling

These five runs establish short-horizon repeatability under one frozen requested configuration only. The served checkpoint is unknown, so model-version stability is not established. No production, extraction-quality, cost, or scale claim is made or supported. Semantic decisions on the two classified divergences belong to a subsequent, independently reviewed semantics increment — not to this evidence.
