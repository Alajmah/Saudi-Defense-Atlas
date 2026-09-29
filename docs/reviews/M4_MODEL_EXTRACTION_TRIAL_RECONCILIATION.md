# M4 Bounded Real-Model Extraction Trial — Codex Reconciliation

## Review provenance

The maintainer first-pass was completed and frozen before Codex invocation in:

- `docs/reviews/M4_MODEL_EXTRACTION_TRIAL_FIRST_PASS.md`;
- reviewed Codex baseline: `8013ea91ae9f8d3a833ede612a7d314a6c9a12cd`;
- Codex review submission: `5350963915` on PR #28.

This document does not rewrite the first-pass record. It records the independent second-review findings, the maintainer's reconciliation of those findings, additional maintainer verification after remediation, and the final claim ceiling.

## Codex findings reconciliation

All four Codex findings were independently checked against the reviewed implementation and accepted as valid.

### CX-01 — P1 — workflow-dispatch shell injection / secret exposure

**Codex observation:** `workflow_dispatch` inputs were interpolated directly into a Bash `run:` block while `COPILOT_GITHUB_TOKEN` was in the step environment. A crafted string input could therefore alter shell syntax rather than remain data.

**Maintainer reconciliation:** VALID.

**Remediation:** bind `inputs.model` and `inputs.max_cases` to step-level environment variables, then pass quoted shell variables to Python. The dedicated token remains step-scoped, and user-controlled dispatch values no longer become Bash source text.

**Regression:** the reconciliation validator asserts both environment binding and absence of direct `${{ inputs.* }}` interpolation in the Python command.

**Status:** CLOSED.

### CX-02 — P1 — quality score compared presence rather than factual semantics

**Codex observation:** the original scorer could pass a schema-valid Claim/Event merely because the predicate/event type existed, even when the quantity value/unit, event date, participant relation, or extra allowlisted records were wrong.

**Maintainer reconciliation:** VALID.

**Remediation:** the gold corpus now encodes exact Claim and Event semantics and exact record counts. The scorer resolves candidate references through extracted entity names and checks:

- Claim predicate, subject, value, temporal scope, and extraction assessment;
- Event type, occurrence date, end semantics, participants/roles, related entities, and extraction assessment;
- no extra Claim/Event records beyond the gold expectation.

**Regression:** deterministic checks mutate quantity value/unit, add an extra allowlisted Claim, change Event date/end, and change participant role; every mutation must turn a quality pass into a miss.

**Status:** CLOSED.

### CX-03 — P2 — malformed JSON could pass the insufficient-evidence gold case

**Codex observation:** when a case expected generic `rejected`, malformed JSON and a valid empty structured extraction were indistinguishable to the quality scorer.

**Maintainer reconciliation:** VALID.

**Remediation:** the insufficient-evidence gold case now requires the specific `no-substantive-candidates` rejection check. A valid four-array empty JSON response satisfies that expectation; syntax/envelope/boundary/schema failures do not.

**Regression:** deterministic checks prove the structured empty response passes its gold expectation while `not-json` fails quality with `strict-json-envelope`.

**Status:** CLOSED.

### CX-04 — P2 — Python JSON parsing admitted non-finite numbers

**Codex observation:** Python's default `json.loads` accepts `NaN` and `Infinity`, which violates the trial's strict-JSON contract and could allow non-interoperable values into an accepted/reportable run.

**Maintainer reconciliation:** VALID and slightly broader than the original example.

**Remediation:** the strict envelope rejects `NaN`, `Infinity`, `-Infinity`, and finite-overflow numeric spellings such as `1e999`. Report serialization also uses `allow_nan=False` as defense in depth.

**Regression:** each non-finite spelling must be rejected by `strict-json-envelope` with zero candidate leakage.

**Status:** CLOSED.

## Additional maintainer post-Codex finding

### MR-10 — HIGH — Entity/Evidence semantics and unsupported temporal scope could still inflate quality

**Observed after the Codex fixes:** even after exact Claim/Event value checks, the scorer could still award a quality pass when:

- an extracted entity had the right name but the wrong `entity_type`;
- an entity gained invented aliases/subtype semantics;
- extra Evidence records were emitted;
- Evidence capture assessment differed from the gold expectation;
- an otherwise-correct manufacturer Claim carried an unsupported point-in-time inferred from a neighboring delivery sentence.

The last case conflicted with the trial prompt's rule to use only facts explicitly stated in source text and with the project doctrine that unknown or unsupported scope remains unknown.

**Remediation:** corpus version `m4-model-extraction-eval-v0.3` now carries exact Evidence and Entity gold semantics in addition to Claim/Event semantics. The live scorer compares exact counts and semantic fields for all four candidate arrays. The manufacturer Claim gold explicitly requires no validity interval; invented validity therefore becomes a quality miss rather than rewarded output.

The scorer also checks Event end semantics so an invented end date cannot pass.

**Regression:** deterministic reconciliation checks cover wrong entity type, invented alias, extra Evidence, changed Evidence capture assessment, unsupported manufacturer validity, and invented Event end date.

**Status:** CLOSED.

## Post-remediation architecture/authority review

The remediations do not expand the trial's authority or architecture role:

- Copilot CLI remains a manual trial edge, not a production model-platform adoption;
- the SDA adapter remains provider-independent;
- only synthetic `public_non_operational` cases can reach the invoker;
- restricted work remains pre-invocation blocked;
- accepted output remains candidate-only `AIExtractionRun` data with `CAND-*` identities;
- quality evaluation changes only report/evaluation semantics and grants no truth, approval, canonical-mutation, or publication authority;
- Resolver/Verifier, human review, canonical mutation, and publication remain separate and unexercised by this live runner;
- no scheduler, autonomous worker, second truth store, or shared writer coordinator is introduced.

## Verification evidence

The implementation head immediately before this reconciliation record was added was:

- `b95e6e3a64df0bcdcacac57132b56109cfb8852c`.

On that exact implementation head:

- schema-validation workflow run `36558128209` — **PASS**;
- original maintainer model-trial validator — **PASS**;
- dedicated model-trial review-reconciliation validator — **PASS**;
- all prior M1–M4 schema/governance regression validators in the same job — **PASS**.

The repository-wide Wikibase regression was still running when this record was drafted and must also finish successfully before merge.

This review-document commit changes HEAD. Exact-head CI must therefore be green again after this file lands before the PR can be considered reconciled.

## Remaining unverified / claim ceiling

Nothing in the reconciliation changes the live-evidence ceiling. The following remain unverified:

- no live Copilot trial report has yet been produced and reviewed;
- repository configuration of `COPILOT_GITHUB_TOKEN` is not established by code review;
- actual model extraction quality is unknown until a live trial executes;
- actual latency and bounded-run throughput are unknown until execution;
- monetary cost remains intentionally unknown/unmeasured by the harness;
- provider checkpoint/version behind the requested model remains unknown;
- representative batch-volume or extraction “at scale” remains unqualified;
- real-model candidates have not yet been demonstrated through Resolver/Verifier and the human review packet/decision path;
- no production model provider/platform, scheduler/orchestrator, or distributed writer coordinator is selected or qualified;
- no truth, approval, canonical-mutation, or publication authority is added.

## Reconciliation gate

Before merge:

1. exact-head schema-validation must pass after this review record;
2. repository-wide Wikibase regression must pass on the exact PR head;
3. maintainer must reply to and resolve the four original Codex threads with the concrete remediation evidence;
4. Codex must be asked to perform a fresh second review on the new exact head;
5. any new Codex findings must be reconciled rather than assumed superseded by the first Codex pass.
