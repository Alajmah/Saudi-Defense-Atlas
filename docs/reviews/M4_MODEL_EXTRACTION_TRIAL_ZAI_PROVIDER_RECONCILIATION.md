# M4 Z.ai Trial Provider Edge — Review Reconciliation and Closure

## Protocol

This record closes the review sequence for PR #29 (`M4: add Z.ai local real-model trial provider edge`) under the repository rule: exhaustive maintainer review first, independent second review second, reconciliation and adversarial verification before merge.

No live Z.ai request was made during implementation, review, remediation, reconciliation, or deterministic validation. No model credits were consumed. The provider-independent extraction boundary and its authority semantics remain unchanged.

## Reviewed baselines

- Base `main`: `3d95b461e8c226fdf0eef69dccbd66e4e256c9f1`.
- Independent first-pass frozen head: `4cf2656dc14d9b544d8f5b472e2a441d7d35c896`.
- IRZ-01..07 remediation implementation: `78a83d3661aaf0f4548083ec444bb7e494a181a4`.
- IRZ remediation record / second-review input head: `8f2bf1d2566b6ff7f964bdc736232a84fb47e833`.
- Codex second review reviewed `8f2bf1d256` and raised three P2 findings.
- Second-review remediation implementation: `84231207fc196c822554a6ee38908ce83add4526`.
- Second-review remediation record / fresh re-review head: `618acbf3c57e27244a61274eaedd7e9267078fca`.
- Fresh Codex re-review at `618acbf3c5` returned: `Didn't find any major issues. Nice work!`

This reconciliation record is documentation-only and is committed after the clean fresh re-review. It does not alter the implementation reviewed at `618acbf3c57e27244a61274eaedd7e9267078fca`.

## Reconciliation register

### Independent first-pass findings

IRZ-01 through IRZ-07 were accepted and remediated before the Codex second review. The remediation is recorded in `M4_MODEL_EXTRACTION_TRIAL_ZAI_PROVIDER_REMEDIATION.md` and includes credential-character hardening, explicit endpoint selection, strict provider-envelope parsing, pinned reasoning configuration, source/runtime provenance, bounded response size, and documentation corrections.

Status: **CLOSED**.

### Codex second-review findings

Codex reviewed `8f2bf1d2566b6ff7f964bdc736232a84fb47e833` and raised three P2 findings:

1. linked Git worktrees were not resolved through `commondir`;
2. `provider_edge.endpoint_mode` could report a losing endpoint flag when a URL override won;
3. the report SHA-256 could hash pre-write LF text rather than exact Windows on-disk bytes.

All three were independently verified as valid and remediated in `84231207fc196c822554a6ee38908ce83add4526`, with regression coverage. The original review threads were replied to and resolved after verification on the remediated head.

Status: **CLOSED**.

### Maintainer adversarial hardening during second-review reconciliation

Two additional bounded hardening items were added during reconciliation:

1. URL overrides are restricted to the two exact documented Z.ai base routes already represented by `ZAI_ENDPOINT_URLS`;
2. Z.ai credentials containing non-ASCII characters are rejected before request construction.

Both were implemented in `84231207fc196c822554a6ee38908ce83add4526` and covered deterministically.

Status: **CLOSED**.

## Independent verification of the second-review remediation

The remediated implementation on `618acbf3c57e27244a61274eaedd7e9267078fca` was independently inspected after push. Verification confirmed:

- linked-worktree loose refs and common-directory `packed-refs` are handled;
- endpoint mode is derived from the resolved URL and contradictory explicit selections fail before transport;
- report and sidecar are written as bytes and the report digest is computed from exact bytes read from disk;
- credential destinations are constrained to the two exact documented Z.ai routes;
- credentials are constrained to printable ASCII while retaining prior whitespace/control/quote/backslash rejection;
- the deterministic validator pins each of these regressions;
- `services/intelligence/model_extraction_trial.py` remains unchanged from `main`;
- canonical mutation and publication authority remain false;
- the restricted synthetic case remains blocked before model invocation.

Exact-head `schema-validation` evidence on `618acbf3c57e27244a61274eaedd7e9267078fca`:

- push run `36588500579` — **PASS**;
- pull-request run `36588507315` — **PASS**.

## Fresh independent re-review

A fresh Codex review was explicitly requested against exact head `618acbf3c57e27244a61274eaedd7e9267078fca` after all accepted second-review findings and hardening items had been remediated.

At `2026-09-29T18:08:40Z`, the Codex connector returned a clean review against reviewed commit `618acbf3c5`: **`Didn't find any major issues. Nice work!`** No new inline findings were created.

The earlier `@codex address that feedback` request had not produced a code change because the repository did not have a Codex write environment configured; the accepted findings were therefore remediated by the maintainer and then independently re-reviewed.

## Adversarial verification result

No remaining implementation defect was identified in the bounded provider edge after the second-review remediation and fresh re-review.

The accepted limitations and unknowns are not converted into implementation defects:

- Z.ai account type and workload entitlement remain operator facts at live execution time;
- wire acceptance of the pinned `thinking` / `reasoning_effort` request fields remains unverified until a live call;
- served provider checkpoint identity remains unknown;
- model quality, latency, throughput, and monetary cost remain unqualified until live evidence exists;
- socket-level timeout versus total wall-clock timeout remains a documented limitation;
- the trial remains synthetic-only and grants no truth, approval, canonical mutation, publication, scheduler, or autonomous-worker authority.

## Closure decision

**Review reconciliation: CLOSED.**

PR #29 is merge-ready from the implementation/review perspective, subject to the final documentation-only reconciliation commit passing the repository's normal exact-head CI gates and `main` remaining at the reviewed base or being explicitly re-reconciled if it moves.

Merging this provider edge does **not** qualify live Z.ai extraction. The next evidence gate is a reviewed local live trial from a clean checkout of the merged/reviewed code using an endpoint for which the operator has valid workload entitlement. The resulting JSON report and `.sha256` sidecar must be reviewed before any model-quality, performance, scale, or production-provider claim is made.
