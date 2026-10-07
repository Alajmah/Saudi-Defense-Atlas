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


## DCC-LOCK-01 residual closure after exact-head re-review 5431974629

The prior remediation moved the live lock out of the evidence directory and correctly prevented **concurrent** duplicate execution of one manifest. Exact-head re-review identified a remaining sequential replay path: after normal completion the live lock is released, so the same exact approved manifest/attestation could previously be started again with a different evidence directory and consume its full invocation ceiling a second time.

### DCC-LOCK-01 — FULLY REMEDIATED FOR THE QUALIFIED REPOSITORY-RUNTIME SCOPE

The controller now maintains two separate manifest-keyed coordination artifacts under the repository Git-common-dir runtime namespace:

1. a **persistent evidence-directory binding** for the canonical `manifest_sha256`; and
2. the existing transient live-process lock.

The persistent binding is atomically created on first start and is not removed on normal completion. The same manifest can resume or terminally re-open only against the same canonical evidence-directory path. A different evidence directory fails before credential retrieval or provider construction, including after the original campaign has completed and released its live lock.

The deterministic validator now proves both boundaries:
- while a manifest lock is live, a second evidence directory performs zero credential/provider activity;
- after a campaign completes and releases its live lock, the same manifest aimed at another evidence directory is still refused with zero credential/provider activity.

A distinct future campaign must use a distinct approved manifest rather than replaying the old manifest approval.

The qualified scope remains repository-runtime-local. Cross-host / independent-clone global exclusion is explicitly not claimed; that still requires the separately deferred shared atomic coordinator.


## Exact-head hook compatibility remediation after `9cf4e30af469e605d2330103de721ea10c54a7d1`

The provider-boundary hook was hardened to receive the exact rendered prompt, changing its contract from `Callable[[], None]` to `Callable[[str], None]`. The first exact-head CI on that interface change correctly failed at `Validate M4 drafting trial driver` because the existing validator and campaign marker still supplied zero-argument callbacks.

### Hook-interface regression — REMEDIATED

- the campaign's `mark_invocation_started` callback now accepts the rendered prompt argument while retaining the same ledger-only authority and marker-before-attempt ordering;
- the single-case deterministic validator's pre-boundary/provider-failure/success hooks now accept that argument;
- provider-failure and success regressions additionally require the hook-observed prompt to equal the provider-observed prompt exactly.

No live provider call, entitlement consumption, report-schema change, scheduler/recurrence authority, publication authority, or canonical-mutation authority is introduced.


## Codex remediation after review 5432104787

Codex review `5432068642` on `edfe5194737e7da302b02ebe08a6e838e8d95f1b` identified three additional provider-boundary/evidence issues that remained applicable after the independent-maintainer remediation. They were accepted in reconciliation review `5432104787`.

### DCC-SRC-01 — source/corpus could drift before provider entry — REMEDIATED

The single-case `before_invoke` hook now receives the exact rendered prompt that is about to be sent.

The campaign callback performs a second fail-closed source check at that exact provider boundary before writing `case_invocation_started`:

1. re-resolve reviewed HEAD / tracked-worktree cleanliness;
2. re-hash the manifest-bound case fixture and terminology file;
3. split the actual rendered prompt and recover its canonical context / frozen `created_at`;
4. freshly reread the manifest-bound fixture and terminology registry;
5. rebuild the ApprovedDraftingContext and complete rendered prompt;
6. require exact context and prompt equality.

This catches both persistent source mutation and mutate-then-restore races: the former fails manifest hashes; the latter fails exact prompt reconstruction. Only after this check succeeds is the conservative invocation-start marker appended.

Deterministic validation proves a valid prompt passes, a tampered rendered prompt fails, and source-state drift between the outer case check and the provider-boundary callback produces no marker and no provider call.

### DCC-ERR-01 — empty exception message broke failure classification — REMEDIATED

`execute_draft_invocation()` now normalizes an empty `str(exc)` to:

`<ExceptionType>: invocation failed`

before truncating/storing the execution diagnostic.

Campaign event classification now distinguishes `execution_error is not None` rather than relying on string truthiness.

The single-case validator proves `TimeoutError()` produces one attempt and a non-empty diagnostic containing `TimeoutError`. The campaign validator proves the same path freezes failure evidence and terminalizes as `stopped_execution_failure` without retry or continuation.

### DCC-ATT-01 — attestation whitespace was normalized — REMEDIATED

Both single-case and campaign entitlement gates now use a stripped copy only for validation while preserving and returning the original supplied attestation string.

The campaign-start ledger hash and single-case report therefore bind the exact supplied UTF-8 string, including leading/trailing whitespace.

Deterministic validation proves:
- a whitespace-only attestation remains invalid;
- a valid whitespace-bearing single-case attestation is preserved exactly in the report;
- resume with leading-whitespace drift from the frozen campaign attestation fails before provider activity.

### Authority boundary

These changes close provider-boundary source/evidence precision only. They do not authorize or perform a live model call and do not add retry, publication, canonical mutation, scheduler, recurrence, or cross-host coordination authority.


## Stale-Codex path-collision remediation after review 5432229919

Codex review `5432133635` on earlier head `5d2be7cde3df4996b32da6c73200d8551ca97945` identified two findings that were reconciled against later heads.

### DCC-BUDGET-01 — sequential evidence-directory replay — CLOSED BY EXISTING LATER REMEDIATION

The transient manifest-global lock alone would not have prevented replaying one authorized manifest into a new evidence directory after normal completion. Later branch code already closed this by atomically persisting a manifest-SHA-to-evidence-directory binding in the repository Git-common-dir campaign runtime namespace. The binding survives normal completion and is checked before credential/provider activity.

### DCC-PATH-01 — case IDs could alias campaign artifacts — REMEDIATED

Manifest loading now rejects controller-artifact-reserved case IDs:

- `campaign-manifest`;
- `campaign-summary`;
- `campaign-ledger`.

This prevents a derived case report path from colliding with the frozen campaign manifest or aggregate summary and reserves the ledger stem against future path-shape changes.

The deterministic validator mutates a valid manifest to each reserved case ID and proves all three fail at manifest load.

No live model call or drafting entitlement consumption occurred.


## Codex checkout-provenance remediation after review 5432388300

Codex's latest substantive review on `fe45e104d9da691ab9f01d484bd352fa7f8cee9d` identified one remaining recovery-provenance hole that still applied to the later branch head.

### DCC-PROV-01 — recovered report did not prove its actual checkout provenance — REMEDIATED

`verify_case_report()` already required the report's top-level `reviewed_head` to equal the campaign manifest, but it did not independently bind the report's own execution trace under `trial_context`.

Recovery now additionally requires:

- `trial_context.git_head == manifest.reviewed_head`;
- `trial_context.tracked_worktree_clean is true`.

A report that claims a different execution commit or a dirty tracked worktree is rejected even if an attacker or operator recomputes a matching unkeyed SHA-256 sidecar.

The deterministic validator now creates valid campaign-bound evidence, independently rewrites and re-hashes:

1. `trial_context.git_head` to another 40-hex commit; and
2. `trial_context.tracked_worktree_clean` to `false`;

and proves both are rejected by the recovery verifier without provider activity.

This closes only evidence provenance. It does not authorize or perform a live model call and does not add retry, scheduler, recurrence, publication, canonical-mutation, or cross-host coordination authority.
