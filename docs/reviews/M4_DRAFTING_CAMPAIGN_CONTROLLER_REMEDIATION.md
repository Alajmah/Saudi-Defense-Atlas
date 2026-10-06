# M4 Drafting Campaign Controller — Remediation Record

## Protocol

This additive record remediates the frozen first-pass review of PR #46:

- reviewed implementation head: `791082277100b6c956ca5bf7df0d5df04b7ee918`
- frozen primary review: **5430940943 — BLOCKED**
- frozen first-pass artifact: `docs/reviews/M4_DRAFTING_CAMPAIGN_CONTROLLER_FIRST_PASS.md`

The first-pass artifact remains unchanged. No live drafting model call was made and no drafting entitlement was consumed.

## DCC-01 — Windows PID liveness probe — REMEDIATED

The controller no longer uses `os.kill(pid, 0)` unconditionally.

- POSIX retains signal-0 probing.
- Windows uses `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess` and closes the process handle.
- `acquire_lock(..., pid_alive=...)` accepts an injectable liveness function so deterministic validation can prove live-lock refusal and stale-lock reclaim without relying on host-specific process manipulation.

## DCC-02 — resume entitlement drift — REMEDIATED

The campaign manifest now requires an explicit `entitlement_id`. The runtime attestation must contain that campaign-specific identity and the manifest route.

The leading `campaign_started` event freezes `entitlement_attestation_sha256`. Every later resume requires the newly supplied attestation bytes to hash to the same value before additional provider activity.

The frozen campaign summary also carries the `entitlement_id`.

## DCC-03 — untracked corpus admission — REMEDIATED

The controller now requires the terminology registry and every case fixture to be git-tracked with:

`git ls-files --error-unmatch`

in addition to repository-root path confinement and exact SHA-256 binding.

The live campaign still rechecks reviewed HEAD + tracked-worktree cleanliness before each fresh case.

The deterministic validator creates an untracked fixture under the repository root and proves manifest loading fails closed.

## DCC-04 — terminal summary verification — REMEDIATED

Terminal reruns no longer trust an existing `campaign-summary.json` merely because the file and sidecar exist.

The controller now:

1. validates the ledger/hash chain;
2. deterministically rebuilds the expected summary;
3. verifies the stored summary sidecar against exact bytes;
4. parses the stored JSON;
5. requires exact semantic equality with the rebuilt summary before returning it.

The validator tampers with terminal summary bytes and proves the controller rejects the artifact without any new provider invocation.

## Additional long-running hardening added before re-review

The campaign now freezes the canonical manifest itself as immutable:

- `campaign-manifest.json`
- `campaign-manifest.json.sha256`

A `case_invocation_started` ledger event is written before each fresh single-case execution sequence. If a process dies with that start marker but without a complete immutable case report + sidecar, restart treats the call as ambiguous and **does not automatically reinvoke it**.

This is conservative by design: preventing duplicate external calls takes precedence over automatic recovery when provider-side effect is unknowable.

The invocation ceiling is now required to equal the frozen case count because retry authority is absent.

## Deterministic validation coverage

The campaign validator now covers:

- manifest version, exact call ceiling, route, entitlement ID, and file hashes;
- git-tracked corpus admission;
- frozen manifest artifact;
- entitlement attestation continuity across resume;
- structural rejection continuation;
- provider failure stop/no retry;
- orchestration count bounded to one call per fresh case;
- ambiguous in-flight marker blocks automatic reinvocation;
- completed-but-unledgered case report recovery without duplicate invocation;
- hash-chained ledger tamper detection;
- terminal summary tamper detection;
- live/stale lock behavior through injected liveness decisions;
- zero publication/canonical authority and editorial quality unqualified.

## Claim ceiling

These remediations qualify only deterministic campaign-control mechanics if exact-head CI and re-review pass. They do not qualify live model quality, editorial quality, production reliability, representative throughput, scheduler operation, publication, or canonical mutation.
