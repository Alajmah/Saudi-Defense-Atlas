# M4 Drafting Campaign Controller — Frozen First-Pass Review

## Protocol

This document preserves the independent first-pass review state for PR #46 before any Codex or fallback reconciliation. It records the exact findings submitted in GitHub review **5430940943** against implementation head:

`791082277100b6c956ca5bf7df0d5df04b7ee918`

Base:

`main@e81badcb57a32a6d6370b7070964e638790e9828`

This record is immutable review provenance. Later remediation may close findings but must not rewrite this baseline.

## Verdict at frozen head

**BLOCKED**

The campaign architecture was directionally sound: composition over the reviewed single-case `run_trial()`, frozen manifest/corpus hashes, structural-rejection continuation, provider/evidence/provenance stop behavior, pre-invocation ledger marker, no automatic retry of ambiguous in-flight cases, completed-but-unledgered recovery, hash-chained ledger, and no publication/canonical authority.

## Findings

### DCC-01 — HIGH / BLOCKING — unsafe Windows PID liveness probe

The lock used `os.kill(pid, 0)` on every platform. That is a POSIX liveness idiom and is not a safe Windows process-query assumption. A second controller must never risk affecting the process whose lock it is checking.

Required remediation: platform-specific non-destructive liveness query, retaining signal-0 only on POSIX; deterministic/injectable lock tests.

### DCC-02 — MEDIUM / BLOCKING — entitlement attestation could drift across resume

The first `campaign_started` event recorded the attestation SHA-256, but resumed execution only checked campaign entitlement ID and route wording. Later cases could therefore run under a different attestation while sharing one campaign identity.

Required remediation: resumed execution must require the exact original attestation SHA-256 before more provider activity.

### DCC-03 — MEDIUM / BLOCKING — untracked corpus files could satisfy manifest hashing

Manifest paths were constrained to the repository root and SHA-256-bound, but project worktree cleanliness intentionally ignores untracked files. A manifest could therefore point to an untracked local fixture not present in the independently reviewed commit.

Required remediation: require terminology and every fixture to be git-tracked as well as path/hash-bound; add an untracked-file regression.

### DCC-04 — MEDIUM / BLOCKING — terminal summary was trusted without immutable verification

On terminal rerun, if both summary and sidecar existed, the controller returned parsed summary JSON directly without checking the sidecar, manifest/review binding, or deterministic equality with the verified ledger projection.

Required remediation: verify summary bytes/sidecar and compare with a fresh deterministic summary rebuilt from the validated terminal ledger; add tamper regressions proving zero provider activity.

## Non-blocking observation

The `case_invocation_started` event is intentionally conservative. A single-case pre-provider gate failure after that marker may later look like an ambiguous attempted case. This is fail-closed with respect to duplicate-call prevention and was not a blocker at the frozen head.

## Independence

No PR comment, Codex result, remediation record, or later review was consulted before review 5430940943 was submitted.

## Live-action boundary

No live drafting model call or drafting entitlement consumption occurred during this review.
