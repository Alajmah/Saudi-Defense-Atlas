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


## Residual remediation after review 5431026967

### DCC-05 — recovered evidence not bound to exact campaign authorization/route — REMEDIATED

`verify_case_report(...)` now requires the campaign's exact normalized entitlement attestation and verifies it against the single-case report.

It also verifies route provenance against the manifest:

- `provider_edge.requested_endpoint_mode` must equal the manifest route;
- `provider_edge.resolved_base_url` must equal the official URL for that route;
- `entitlement.resolved_base_url` must equal the same official URL.

The campaign-level Coding Plan wording gate was tightened from a loose `coding` substring to `coding-plan`.

The deterministic validator proves a valid recovered report passes while wrong-attestation and wrong-route variants fail closed.

### DCC-06 — out-of-band report could be absorbed without campaign start marker — REMEDIATED

Every fresh campaign case already records `case_invocation_started` before invoking the reviewed single-case driver. Recovery now requires that matching ledger event before any complete pre-existing report can be adopted.

A complete report + sidecar without a matching campaign invocation-start marker is rejected as foreign/ambiguous evidence.

The crash-recovery regression now constructs the legitimate recovery state explicitly:

1. `campaign_started`;
2. `case_invocation_started`;
3. single-case immutable report + sidecar;
4. no terminal case event.

Resume then adopts that report without reinvocation and proceeds to the next case.

A separate regression creates a standalone single-case report with no campaign start marker and proves the campaign rejects it without any new provider call.

## Residual claim ceiling

These changes only strengthen campaign provenance/recovery mechanics. They do not authorize or perform a live drafting call and do not broaden model, publication, canonical-mutation, scheduler, or recurrence authority.


### DCC-07 — recovered case report internal evidence consistency — REMEDIATED

Campaign recovery no longer treats a matching sidecar plus selected provenance fields as sufficient.

`verify_case_report()` now independently re-verifies:

- exact rendered-input SHA-256 from `evidence.rendered_model_input`;
- exact raw-output SHA-256 from `evidence.raw_model_output`;
- terminology registry digest from the manifest-bound tracked registry;
- terminology delivery digest from the frozen rendered-input block;
- report-level structural/editorial/publication/canonical qualification flags.

When `structural_result` exists, recovery reconstructs the frozen drafting context and terminology blocks, recreates the original `DraftModelTrace`, reuses the structural run's original `started_at` / `completed_at` timestamps through an injected deterministic clock, returns the frozen raw response through a no-network replay invoker, and calls the reviewed `build_bilingual_draft_run()` boundary again.

The replayed run must equal the stored structural result exactly, including validation status, units, accounting, authority, IDs, and all prompt/context/output hashes.

The validator rewrites a valid report's structural validation status, recomputes a matching report sidecar, and proves recovery still rejects the artifact. No provider call is involved in replay.


#### DCC-07 additional failure-path binding

Recovery also reconstructs the exact expected ApprovedDraftingContext and complete rendered model input from the manifest-bound tracked fixture, manifest-bound terminology registry, and the frozen context's `created_at`. The recovered rendered input must equal this deterministic reconstruction exactly.

This check applies even when `structural_result` is null because the original provider/execution path failed, so failure evidence cannot bypass fixture-to-input integrity merely because no structural run exists to replay.


## Residual remediation after review 5431227374

The exact-head collaborator review at `1cd2a2c5bd282c7c6529e514ef3cbcb883550dc5` found two additional long-running evidence-boundary residuals. The frozen first-pass artifact remains unchanged.

### DCC-08 — terminal summary did not re-close over per-case evidence — REMEDIATED

Terminal fast-path execution now re-verifies every case-terminal ledger event before trusting or returning the aggregate campaign summary.

For each recorded case the controller:

1. resolves the manifest case and expected immutable report path;
2. requires the report + sidecar pair;
3. calls `verify_case_report(...)` against the exact campaign manifest and attestation;
4. rebuilds the deterministic case payload;
5. requires report SHA-256, invocation count, structural status, execution error, fixture hash/path, and report path to equal the ledger payload;
6. validates the recovery flag type;
7. only then rebuilds and verifies the terminal aggregate summary.

Deterministic regressions now delete a terminal case report, delete its sidecar, alter report bytes without updating the sidecar, and rewrite semantic report content with a freshly recomputed sidecar. Every case fails closed with zero additional provider activity.

### DCC-09 — invocation-start marker was wider than the provider boundary — REMEDIATED

The reviewed single-case `run_trial()` primitive now accepts an optional orchestration-only `before_invoke` callback. Default behavior is unchanged.

The callback is invoked only after:

- single-case deterministic gates pass;
- context/rendering preparation succeeds;
- credential retrieval succeeds;
- provider construction succeeds;

and immediately before `execute_draft_invocation()` can enter the provider-call boundary.

The campaign now appends `case_invocation_started` and charges the conservative call ceiling from that callback instead of before calling `run_trial()`.

The ambiguity policy remains intentionally conservative after the marker: if the process dies after the marker without complete immutable evidence, automatic retry remains forbidden.

New deterministic regressions prove that:

- route/environment ambiguity;
- missing credential;
- provider-factory construction failure

all produce zero invoker calls **and no invocation-start marker**. A successful fresh case still records exactly one marker and remains one-call/no-retry bounded.

### Authority / live-action boundary

These residual fixes change only campaign provenance and recovery mechanics. They do not grant scheduler, recurrence, publication, canonical-mutation, or model authority. No live drafting call or drafting entitlement consumption is performed by this remediation.


## Residual remediation after review 5431879576

### DCC-10 — campaign start marker still preceded deterministic drafting-boundary work — REMEDIATED

The optional `before_invoke` callback moved from `run_trial()` immediately before `execute_draft_invocation()` into `execute_draft_invocation()`'s capturing invoker itself.

The exact order at the actual provider boundary is now:

1. `build_bilingual_draft_run()` completes all deterministic pre-invocation context validation, prompt preparation, terminology loading, factual-number/support/accounting setup, and structural start-time acquisition;
2. the capturing invoker is reached;
3. `before_invoke()` appends the campaign's `case_invocation_started` event and charges the conservative call ceiling;
4. the orchestration increments its provider-attempt count;
5. the provider closure is called.

If any deterministic boundary work fails before step 2, the hook does not fire, the provider attempt count remains zero, and the campaign acquires no false ambiguous invocation marker. If the hook itself fails, the provider is not called.

The single-case deterministic validator now proves:
- invalid context rejected inside `build_bilingual_draft_run()` -> zero hook calls, zero provider calls, zero attempts;
- provider failure -> exactly one hook and one attempt;
- successful provider response -> exactly one hook and one attempt.

This change does not broaden model, publication, canonical-mutation, scheduler, retry, or recurrence authority. No live model call or entitlement consumption is performed by the remediation.


## Codex P1 reconciliation after review 5431950125

The completed Codex review on commit `4408755f312e0e3ba19927b9d2a0f1ca5f5d410e` identified three additional long-running failure-mode defects. They were independently checked against current head `0a25023f2be22980cb538ad4eb6a6bc558ecc0b0` and confirmed applicable.

### DCC-11 — recorded execution failure could resume into later cases — REMEDIATED

On nonterminal resume the controller now inspects already-recorded case-terminal events before processing any fresh case.

If a recorded `case_execution_failure` exists and no campaign terminal event exists:

- the failure report is re-verified against the manifest/attestation/evidence boundary;
- any later case-terminal record after that failure is rejected as invalid history;
- the controller appends `campaign_stopped` with `stopped_execution_failure`;
- terminal evidence/summary verification runs;
- no later case is invoked.

A deterministic regression simulates the exact crash window by removing only the final `campaign_stopped` event from a real failure ledger, deleting the old summary, and resuming. The campaign re-finalizes the stop with zero provider calls.

### DCC-12 — nonterminal resume trusted recorded evidence before spending more calls — REMEDIATED

Every already-recorded `case_completed` / `case_execution_failure` event is now re-closed over its actual immutable report + sidecar immediately after ledger loading and **before any fresh invocation**.

The verified report SHA, invocation count, structural status, execution error, fixture/path binding, and report path must match the ledger payload.

A deterministic regression builds a legitimate first-case completed ledger state, removes its report sidecar, and proves resume fails closed before case 2 can reach the provider.

### DCC-13 — stale-lock auto-reclamation race — REMEDIATED BY POLICY REDUCTION

Automatic stale-lock reclamation has been removed.

Any existing `.campaign.lock` now fails closed. The controller does not inspect a dead PID and then unlink the lock, eliminating the stale-lock TOCTOU race where concurrent reclaimers could delete each other's newly created live locks.

Normal shutdown still releases its own token-bound lock. A crash-residue lock requires explicit operator reconciliation/removal after confirming no controller is live.

The deterministic validator proves:
- a second acquisition while a lock is owned fails;
- a stale/dead-PID-shaped lock also fails;
- the stale-shaped lock bytes are not modified or automatically reclaimed.

This deliberately trades automatic crash-lock recovery for a stronger no-concurrent-controller guarantee. It does not alter manifest, entitlement, model, publication, canonical-mutation, retry, scheduler, or recurrence authority.

No live model call or drafting entitlement consumption occurred.


## Independent maintainer remediation after review PRR_kwDOUrt-R88AAAABQ8Va5Q

The independent exact-head maintainer review identified three additional authorization/concurrency/recovery blockers on `0a25023f2be22980cb538ad4eb6a6bc558ecc0b0`. They remained applicable after the DCC-11..13 remediation and were accepted in reconciliation review `5432040779`.

### DCC-AUTH-01 — campaign approval was not bound to the exact manifest — REMEDIATED

`check_campaign_entitlement()` now derives the canonical manifest SHA-256 and requires the runtime attestation to contain all of:

- `entitlement_id`;
- `campaign_id`;
- the full canonical `manifest_sha256`;
- the selected route token.

Changing model, ordered corpus, case count/invocation ceiling, terminology binding, reviewed head, or any other manifest field changes the manifest hash and invalidates the old attestation before credential/provider activity.

The validator proves that an attestation for the original manifest cannot authorize:
- a changed model;
- reordered cases;
- an enlarged corpus/call ceiling.

### DCC-LOCK-01 — hard ceiling was scoped to evidence directory — REMEDIATED FOR SINGLE-HOST/SINGLE-CHECKOUT SCOPE

Campaign locking moved from:

`<evidence_dir>/.campaign.lock`

to one deterministic checkout-level namespace keyed only by the exact manifest SHA-256:

`.runtime/m4-drafting-campaign-locks/<manifest_sha256>.lock`

The same approved manifest therefore cannot obtain independent locks merely by selecting different evidence directories within the supported checkout.

The existing fail-closed lock policy remains: no automatic stale-lock reclamation; crash residue requires explicit operator reconciliation.

The validator holds the manifest lock and attempts the same manifest with a different evidence directory, proving zero credential/provider activity.

This is **not** a cross-host global lock claim. Multi-host exclusion still requires a future shared coordinator.

### DCC-REC-01 — campaign recovery admitted impossible zero-attempt provenance — REMEDIATED

`verify_case_report()` now requires every campaign-bound case report to prove exactly:

- `invocation.attempted == true`;
- `invocation.count == 1`.

Because `case_invocation_started` is emitted at the actual provider-call boundary, zero-attempt evidence cannot legitimately be adopted by campaign recovery or terminal verification.

The validator re-hashes reports after independently changing `attempted` to false and `count` to zero; both are rejected without provider activity.

### Authority boundary

These changes strengthen the exact authorization/call-budget evidence boundary only. No live model call, drafting entitlement consumption, scheduler/recurrence authority, publication authority, or canonical-mutation authority is introduced.
