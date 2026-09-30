# M4 Z.ai Standing Entitlement Policy — Fallback Review

## Protocol status

This is the documented maintainer fallback review for PR #34 after Codex code-review quota exhaustion prevented an independent Codex review.

Codex quota evidence: PR #34 issue comment `5912241395` reports that the code-review usage limit has been reached.

The fallback is explicitly lower-independence than the preferred Codex second-review path and is not represented as an independent Codex pass.

## Frozen review baseline

Reviewed policy head before this record:

- `c8ed8d33a8053c006d8930cf4955d09e132832bb`

Base:

- `main` at `cb841a8a85ce4812b0922c81f990dd75432b2647`

Scope before this record:

- `docs/M4_ZAI_LIVE_RUN_ENTITLEMENT_POLICY.md`;
- `docs/reviews/M4_ZAI_STANDING_ENTITLEMENT_APPROVAL.md`;
- no runner, prompt, evaluator, provider transport, schema, corpus/gold, sensitivity-gate, or authority change;
- no live provider call.

Exact-head `schema-validation` run `36721591065` completed successfully on `c8ed8d33a8053c006d8930cf4955d09e132832bb` before this review record was added.

## Review checks

### Operator provenance — PASS

The governance record preserves both the operator's broad Coding Plan entitlement statement and the subsequent explicit instruction to modify the repository rule to cover all cases as official approval.

The repository correctly treats the decision as an operator assertion about the operator-controlled account. It does not convert that assertion into a general claim about Z.ai public terms or other accounts.

### Normative precedence — PASS

The new policy explicitly identifies itself as the current normative entitlement rule and supersedes the earlier per-run attestation requirement for future execution within scope.

Frozen historical records remain unchanged and retain their original meaning for the runs/reviews conducted under the older rule.

### Scope preservation — PASS

The standing approval changes only how often entitlement approval must be restated. It does not broaden what can be sent to the provider:

- existing pre-invocation sensitivity/data gates remain authoritative;
- restricted/operational cases remain blocked;
- model output remains candidate-only;
- no tool/retrieval/action surface is added;
- no canonical-resolution, truth, mutation, publication, Resolver/Verifier, or human-review authority is added;
- clean-reviewed-state and evidence-preservation requirements remain intact.

Thus "all cases" means all cases admitted by the existing trial policy, not cases that the policy blocks.

### Standing duration and re-approval triggers — PASS

No fresh per-run attestation is required while the approved account, Coding Plan endpoint, bounded non-coding structured-extraction workload, safety boundary, provider-edge authority, and credential destination remain unchanged.

A new explicit operator approval is required for account/entitlement changes, endpoint changes, workload-class expansion, sensitivity-boundary expansion, new provider-edge tools/actions/credential destinations/authority, or operator revocation/replacement.

Prompt, evaluator, corpus, report, and requested-model revisions that have independently passed repository review do not consume the standing approval merely because a new run begins.

### Historical/current-document interaction — PASS with explicit precedence

`docs/M4_MODEL_EXTRACTION_TRIAL.md`, `docs/ROADMAP.md`, and historical review records still contain earlier per-run-attestation language. The new policy names those sources and explicitly supersedes that language for future execution while preserving historical auditability.

A later status-document synchronization would improve readability but is not required for rule validity because precedence is explicit and unambiguous in the normative policy.

## Findings register

**No blocking or non-blocking correctness finding was identified on policy head `c8ed8d33a8053c006d8930cf4955d09e132832bb`.**

The only readability observation is the intentionally retained older wording in status/history documents; the normative precedence clause resolves it without rewriting frozen records.

## Effect on the pending live rerun

After this policy PR merges and its merge commit receives the normal post-merge validation, the pending prompt-v0.6 / adapter-v0.3 / report-v0.7 Coding Plan rerun is covered by standing approval. No additional run-specific entitlement attestation is required unless a re-approval trigger has occurred.

## Decision

Fallback review result: **PASS**.

Merge remains gated on successful exact-head CI for the commit containing this fallback record and an unchanged expected PR head.
