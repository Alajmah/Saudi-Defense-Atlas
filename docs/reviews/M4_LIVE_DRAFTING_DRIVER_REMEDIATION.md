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

## Freeze

This record completes remediation of DTD-01 through DTD-05. The remediated head awaits exact-head CI and re-review.
