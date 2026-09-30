# M4 Z.ai Standing Entitlement Approval — Governance Record

## Purpose

This additive record captures the operator's 2026-09-30 decision to replace the repository's per-run Z.ai entitlement-attestation rule with a standing approval for the bounded M4 Coding Plan extraction workload.

Base repository state at the start of this change:

- `main`: `cb841a8a85ce4812b0922c81f990dd75432b2647`
- PR #33 already closed and merged;
- no live provider call is part of this governance change.

Historical review and evidence records are not rewritten. They remain accurate records of the rule that applied when those earlier runs and reviews occurred.

## Operator decision

Immediately before this change, the operator stated:

> **Coding Plan:** I attest that, for all live rerun under prompt v0.6 / report v0.7, the account is entitled to use the Z.ai Coding Plan endpoint for all non-coding structured-extraction workload.

The operator then explicitly directed:

> Modify the repository rule to cover all cases; this constitutes my official approval.

The repository therefore records a standing, account-specific operator approval rather than requiring a new attestation for each individual live run.

## Normative effect

`docs/M4_ZAI_LIVE_RUN_ENTITLEMENT_POLICY.md` is the current normative rule. For future runs within its preserved scope:

- the Coding Plan endpoint is approved on a standing basis;
- all cases admitted by the existing pre-invocation trial policy are covered;
- a fresh per-run entitlement attestation is no longer required;
- prompt, evaluator, report, corpus, or requested-model revisions do not consume or invalidate the approval when they remain inside the reviewed bounded trial scope.

The standing approval does **not** override sensitivity gates, candidate-only authority, clean-reviewed-state requirements, evidence preservation, or any other M4 governance boundary.

## Superseded rule

The earlier reconciliation required every future live run to record a fresh run-specific operator entitlement attestation. That requirement remains visible in frozen historical records but is superseded for future execution by the standing policy.

A new approval is still required if the account/entitlement, provider endpoint, workload class, sensitivity boundary, provider-edge tool/action surface, credential destination, or model authority expands or changes as defined by the standing policy, or if the operator revokes this approval.

## Claim discipline

This record captures an operator assertion about the operator-controlled account. It does not independently verify provider commercial terms and does not make a general statement about Z.ai Coding Plan eligibility for non-coding workloads or other accounts.

## Gate

This is a documentation/governance change only. It does not modify the model-extraction runner, prompt, evaluator, candidate boundary, corpus/gold, authority model, sensitivity gate, or provider transport.

The next live rerun may rely on the standing approval only after this policy change itself is merged through the repository's normal review and exact-head CI process.
