# M4 Live Drafting Trial Driver — Remediation Record

## Protocol

This record remediates the five findings of the independent review of PR #45 at frozen head `e24322e7fd65f64b0fef38774695e3319bfe9b04` (primary `5389829679`; fallback `5389841333`, reduced reviewer independence — DTD-05 added during the fallback challenge; Codex quota-blocked via `5948164241`). The frozen maintainer first-pass record is preserved unchanged at blob `9fbd3d711d5d01b696f40cae33426a2f76cb4583`. No live model call was made and no entitlement was consumed.

Report version bumped to `m4-drafting-live-trial-v0.2` (the evidence surface changed materially: frozen dynamic bytes, failure path, entitlement gate, route reconciliation).

## DTD-01 — route and entitlement not fail-closed — REMEDIATED

**Entitlement:** the driver now requires an explicit `--entitlement-attestation` string for every run. The report records it verbatim alongside `standing_extraction_entitlement_covers_drafting: false`, explicitly stating that the standing extraction approval does not cover drafting.

**Route:** if both `--zai-endpoint` and `ZAI_BASE_URL` (or both `--base-url` and `ZAI_BASE_URL`) are set, the run is refused as ambiguous. The report records the actual resolved base URL and its resolution source (`resolved_base_url`, `resolved_base_url_source`), not just the requested CLI mode. A prepaid env override can no longer be reported as a Coding Plan call.

## DTD-02 — hashes preserved but not exact bytes — REMEDIATED

The report now embeds `evidence.rendered_model_input` (the exact two-block input string) and `evidence.raw_model_output` (the exact raw model response, or `null` on transport failure) alongside their SHA-256 hashes in `invocation`. The terminology section carries the registry version string alongside the acceptance digest and the delivery-payload digest. The artifact gate refuses to write if any output file already exists — no overwrite of prior evidence.

## DTD-03 — validator did not test the report writer — REMEDIATED

The validator now exercises the actual `build_trial_report` function with both a successful fake invoker and a transport-failure scenario, verifying: entitlement fields, resolved route, registry version + digests, frozen rendered input and raw output with matching hashes, editorial placeholder shape and dimensions, qualification flags, structural-result embedding, failure-report properties (error preserved, input preserved, no spurious result), sidecar format, and deterministic serialization (same report → same bytes).

## DTD-04 — transport failure exits without a report — REMEDIATED

The driver's invocation is wrapped in a try/except that catches transport and boundary errors. On failure it writes a bounded failure report preserving the exact rendered input, recording the error in `execution_error`, setting `structural_result: null`, and keeping the editorial placeholder. The process exits nonzero but the evidence is never silently discarded. No retry.

## DTD-05 — reviewed source state not a pre-invocation gate — REMEDIATED

Before any invocation: git HEAD must resolve to a non-empty SHA (unresolvable → refuse); the tracked worktree must be clean (dirty or unknown → refuse). These are hard pre-invocation gates, not recorded observations.

## LOW — PR description file count — CORRECTED

The PR description now says seven changed files (the first-pass record being the seventh).

## Deterministic validation evidence

Complete repository suite at the remediation head: **42/42 validators — PASS**, with the driver validator now exercising the actual report builder, both the success and failure paths, and the serialization round-trip.

## Explicitly unverified / unresolved

No live model has been invoked through this driver. Driver effectiveness and the structural acceptance behavior with a live model remain unknown until the reviewed trial runs. The entitlement attestation records the operator's acknowledgment; it does not constitute the reapproval itself — the collaborator's explicit start for the live trial is still required.

### DTD-01R — base-url + zai-endpoint ambiguity; attestation not route-bound — REMEDIATED (residual round)

`check_route_args` now refuses any combination of `--base-url`, `--zai-endpoint`, and `ZAI_BASE_URL` (all pairs and the triple). `check_attestation_route_binding` requires the attestation string to name the route the call would actually use (coding-plan mentions for the coding endpoint, prepaid/general mentions for the prepaid endpoint). The report records the attestation alongside the resolved base URL. All combinations are gate-tested.

### DTD-02R — artifact writer not immutable; hash chain not cross-checked — REMEDIATED (residual round)

The overwrite check moved inside `write_report_with_sidecar` itself — the function refuses if either the report or sidecar file exists, independently testable. The report builder now verifies `draft_run.raw_output_sha256` equals the frozen raw-output hash and `prompt_trace.rendered_input_sha256` equals the frozen rendered-input hash; a tampered chain raises before the report is built (regression-tested). The validator now tests determinism by writing to two different paths (not by overwriting).

### DTD-03R — gates not tested — REMEDIATED (residual round)

All four gates are factored into individually callable functions (`check_entitlement`, `check_route_args`, `check_git_state`, `check_attestation_route_binding`, plus the writer's internal overwrite check) and the validator exercises each with pass and fail cases: 14 gate assertions covering every ambiguous route combination, empty/blank attestations, empty/dirty/unknown git states, head mismatch, unbound attestation, overwrite of report, and overwrite of sidecar.

### DTD-04R — invocation attempt not proven — REMEDIATED (residual round)

The orchestration is factored into `execute_draft_invocation` (invoke + build draft run + catch), and the report carries `invocation_attempted: bool` and `invocation_count: int`. The validator runs a **failing fake invoker through the actual orchestration path** (not a manually constructed failure report) and proves the failure report has `attempted: true, count: 1` with the rendered input preserved and no spurious result. The success path proves `attempted: true, count: 1` with the correct bytes.

### DTD-05R — reviewed head not pinned — REMEDIATED (residual round)

A `--reviewed-head` argument is now required and must exactly match the current git HEAD. `check_git_state` refuses on empty HEAD, dirty/unknown worktree, **and** head mismatch. Any clean local commit that is not the reviewed SHA cannot reach the provider. The report records the reviewed head.

### Contract version — CORRECTED

`docs/M4_LIVE_DRAFTING_TRIAL.md` now says `m4-drafting-live-trial-v0.3` (the implementation version after this round).

### DTD-02RR-A — artifact existence not checked before invocation; writer not exclusive — REMEDIATED (residual round 3)

`check_artifacts_absent` is a new pre-invocation gate called in `main()` before the API key is even read, so the provider is never invoked when the report or sidecar already exists. The writer no longer uses `exists() -> write_bytes()`; both files are created exclusively via `open(path, "xb")` (`_write_exclusive`), converting `FileExistsError` into the same `TrialGateError`. The validator tests the pre-invocation gate (existing report, sidecar-only, fresh paths) and proves exclusivity survives a lost existence race by making `Path.exists` lie while the file physically exists — the write still refuses and the occupied artifact is untouched.

### DTD-02RR-B — hash chain only partially cross-checked; context check a no-op — REMEDIATED (residual round 3)

The no-op `pass` is removed. `build_trial_report` now verifies the complete chain whenever a draft run exists: `raw_output_sha256` against the frozen raw output; `rendered_input_sha256` against the frozen rendered input; `input_context_sha256` against BOTH the context block recovered from the frozen rendered input AND a fresh canonical serialization of the live context object; `prompt_trace.terminology_registry_sha256` against the registry digest recomputed from the terminology payload (which must also equal the context's `terminology_sha256`); `prompt_trace.terminology_delivery_sha256` against the delivery block recovered from the frozen rendered input. The report's `terminology.registry_acceptance_sha256` / `delivery_payload_sha256` now carry these same verified digests. All five tamper classes plus a post-invocation context mutation are regression-tested; each raises before the report is built.

### DTD-04RR — invocation counting outside the orchestration; validator hard-coded the count — REMEDIATED (residual round 3)

The attempt counter moved inside `execute_draft_invocation`: the invoker is wrapped within the orchestration, which returns `attempts` as part of its result tuple; `main()` no longer wraps or counts anything. The validator's fakes record their own calls, and the test asserts the orchestration-returned count equals the invoker-observed call count (exactly 1) on both the failing and succeeding paths. Report provenance is built from the orchestration-derived values, never hard-coded.

### Living contract — duplicated sections and misplaced field — CORRECTED (residual round 3)

`docs/M4_LIVE_DRAFTING_TRIAL.md` now has exactly one pre-invocation gate list (the stale DTD-01/02/05 list is removed), one failure-path section, one Frozen-evidence section (the duplicated failure-text block under a second heading is removed), and a field table with a `terminology` row carrying the registry/delivery digests while `invocation` carries only attempted/count/rendered-input hash/raw-output hash/elapsed. Report version bumped to `m4-drafting-live-trial-v0.4` everywhere (the builder's validation strength changed; no live report exists to migrate).

## Freeze

This record completes remediation of DTD-01 through DTD-05. The remediated head awaits exact-head CI and re-review.
