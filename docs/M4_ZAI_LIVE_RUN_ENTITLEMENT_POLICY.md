# M4 Z.ai Live-Run Entitlement Policy

## Status

This file is the current normative entitlement rule for live Z.ai runs in the bounded M4 model-extraction trial. It is effective from 2026-09-30 and supersedes the earlier requirement to obtain and record a fresh operator entitlement attestation for every individual run.

Historical review and evidence records remain unchanged as audit history. Where an older record, `docs/M4_MODEL_EXTRACTION_TRIAL.md`, or `docs/ROADMAP.md` says that every future run requires a fresh run-specific attestation, this policy supersedes that requirement for future execution within the scope below.

## Standing operator approval

The account operator grants standing approval to use the Z.ai Coding Plan endpoint:

`https://api.z.ai/api/coding/paas/v4`

for **all live runs of the bounded M4 Z.ai structured-extraction trial and all cases admitted by the existing pre-invocation policy gate**, without a new per-run entitlement attestation.

The approval covers current and future reviewed prompt, adapter, evaluator, report, corpus, and requested-model revisions so long as the run remains inside the scope below. It is an account-specific operator statement; it is not a claim about Z.ai documentation, other accounts, or Coding Plan entitlement in general.

## Scope preserved

Standing approval does not broaden the trial's data, safety, or authority boundaries. A run remains covered only when all of the following hold:

- the same operator-controlled Z.ai account/entitlement is used;
- the selected route is the Coding Plan endpoint above;
- the workload remains non-coding structured extraction through the reviewed SDA Z.ai provider edge;
- only cases admitted by the existing trial policy may reach the provider; `public_non_operational` and other existing pre-invocation gates remain authoritative, and restricted/operational cases remain blocked before invocation;
- model output remains candidate-only and carries no canonical-resolution, truth, canonical-mutation, publication, Resolver/Verifier, or human-review authority;
- no new model-visible tool, repository/file/shell access, retrieval, MCP, autonomous-action surface, or credential destination is introduced without separate review;
- the run is executed from the independently reviewed repository state required by the trial procedure, with the existing provenance and evidence-preservation controls intact.

Prompt, evaluator, corpus, report-version, or requested-model changes that have themselves passed the repository's normal review gates do **not** require a new entitlement attestation merely because a new live run is started.

## Re-approval triggers

A new explicit operator approval is required if any of these conditions changes:

- the Z.ai account or underlying entitlement used for the run;
- the provider endpoint or route, including a move to the prepaid/general route or any new endpoint;
- the workload class expands beyond the bounded non-coding structured-extraction trial described above;
- the pre-invocation sensitivity/data boundary is broadened;
- the provider edge gains new tools, actions, credential destinations, or authority;
- the operator revokes or replaces this standing approval.

A change matching one of these triggers invalidates this standing approval before the affected live call.

## Operator provenance

On 2026-09-30 the operator first stated a broad Coding Plan entitlement for the live rerun and non-coding structured-extraction workload, then explicitly directed that the repository rule be modified to cover all cases and stated that this direction constitutes the operator's official approval.

This policy records that decision as a standing account-specific approval. It does not retroactively alter the historical attestation requirements or evidence records that were in force for earlier runs.

## Effect on the next rerun

The pending prompt-v0.6 / adapter-v0.3 / report-v0.7 live synthetic-corpus rerun is covered by this standing approval if it otherwise satisfies the existing clean-reviewed-state, policy-gate, provider-edge, and evidence-preservation requirements. No additional run-specific entitlement statement is required before that run.
