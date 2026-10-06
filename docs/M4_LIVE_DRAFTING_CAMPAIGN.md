# M4 Live Drafting Campaign Controller — Contract v0.1

## Status

Implementation increment only. The campaign controller composes over the already-reviewed single-case live drafting driver. **No live model call is authorized or performed by this increment.** A live campaign still requires a separately approved drafting entitlement bound to its route and reviewed execution head.

## Purpose

The campaign controller removes the need for chat-mediated approval between individual cases while preserving the evidence and authority boundaries of the single-case driver.

It is an **operator-started bounded campaign**, not a scheduler, daemon, recurring job, autonomous coordinator, publication workflow, or canonical writer.

The controller repeatedly invokes the reviewed `run_trial()` primitive. It does not reimplement the drafting boundary, prompt renderer, provider transport, structural evaluator, evidence writer, authority model, or route/entitlement gates.

## Authority ceiling

A campaign may:

- execute the frozen manifest cases in order;
- invoke the reviewed single-case driver at most once for each fresh case;
- preserve immutable per-case trial reports and SHA-256 sidecars;
- record a hash-chained append-only campaign ledger;
- recover an already-written case report after a process crash without invoking that case again;
- continue after an ordinary model **structural rejection**, because rejection is campaign evidence;
- stop on provider, transport, evidence, source-state, manifest, route, entitlement, or provenance failure;
- emit an immutable aggregate structural summary.

A campaign may **not**:

- retry a case automatically;
- convert editorial quality into a mechanical score;
- publish generated copy;
- mutate canonical knowledge;
- approve evidence or claims;
- schedule itself or recur after completion;
- broaden the authorized route, model, corpus, reviewed head, or invocation ceiling;
- infer production reliability, scalability, publication fitness, or model quality from campaign completion.

## Frozen manifest

Manifest version: `m4-drafting-campaign-v0.1`.

The manifest is canonical JSON for hashing purposes and contains exactly:

- `campaign_id`;
- `reviewed_head` — the exact independently reviewed execution SHA;
- `route` — `coding-plan` or `prepaid`;
- `entitlement_id` — the explicit campaign-specific drafting approval identity;
- `model`;
- `timeout_seconds`;
- `max_invocations`;
- single-case driver report version;
- drafting adapter version;
- prompt-template version;
- repository-relative terminology file path + SHA-256;
- ordered cases, each carrying `case_id`, repository-relative fixture path, and fixture SHA-256.

Unknown manifest keys are rejected. Absolute/out-of-repository fixture or terminology paths are rejected. The terminology registry and every case fixture must also be **git-tracked** in the reviewed checkout; an untracked local corpus file is not accepted merely because it is under the repository root. Every bound file hash is recomputed before the campaign begins.

The invocation ceiling must equal the number of frozen cases. There is no retry authority, so any larger ceiling would be unused authority and any smaller ceiling could not cover the frozen corpus.

The supplied runtime entitlement attestation must contain the manifest's `entitlement_id` and name the manifest route exactly enough for deterministic binding: `coding-plan` for the Coding Plan route, or `prepaid` / `general` for the prepaid/general route. The campaign controller records the entitlement identity and a SHA-256 of the attestation in the first ledger event; **every resume must supply the same attestation bytes**, proven by that SHA-256, before additional provider activity. Each single-case report still records the attestation under the reviewed driver contract.

Example shape:

```json
{
  "version": "m4-drafting-campaign-v0.1",
  "campaign_id": "M4-DRAFT-CAMPAIGN-001",
  "reviewed_head": "<40-hex reviewed controller head>",
  "route": "coding-plan",
  "entitlement_id": "M4-DRAFT-CAMPAIGN-001-AUTH",
  "model": "glm-5.3",
  "timeout_seconds": 180,
  "max_invocations": 10,
  "driver_report_version": "m4-drafting-live-trial-v0.4",
  "drafting_adapter_version": "m4-bilingual-drafting-v0.8",
  "prompt_template_version": "v0.2",
  "terminology_file": "data/terminology/bilingual-terminology-v0.1.json",
  "terminology_file_sha256": "<sha256>",
  "cases": [
    {
      "case_id": "CASE-01",
      "fixture": "tests/fixtures/example.json",
      "fixture_sha256": "<sha256>"
    }
  ]
}
```

## Long-running execution model

The controller is started once:

```bash
python scripts/run_m4_drafting_campaign.py \
  --manifest path/to/frozen-manifest.json \
  --evidence-dir path/to/new-evidence-directory \
  --entitlement-attestation "<explicit route-bound drafting campaign approval>"
```

The controller then processes the ordered corpus without returning to chat between cases.

Before any case invocation, the canonical manifest is also frozen into the evidence directory as immutable `campaign-manifest.json` + SHA-256 sidecar. Resume requires that frozen manifest to remain semantically identical to the supplied manifest.

Before each fresh case, source state is checked again. Local HEAD must remain the manifest's reviewed SHA and the tracked worktree must remain clean. The campaign therefore cannot silently continue after code/source drift during a long process.

The route remains manifest-bound. The campaign supplies exactly one route selector to the reviewed single-case driver; a conflicting `ZAI_BASE_URL` remains subject to the driver's fail-closed ambiguity gate.

## Stop/continue policy

### Continue

An ordinary model structural rejection is preserved as a valid case result and **does not stop the campaign**.

Examples include schema/grounding/accounting/terminology/restricted-detail rejection produced by the reviewed drafting boundary after a provider response was obtained.

### Stop immediately

The campaign stops without moving to the next case when:

- provider/transport execution fails;
- case evidence is incomplete, hash-invalid, or internally inconsistent;
- fixture or terminology bytes no longer match the manifest;
- reviewed HEAD or worktree cleanliness drifts;
- route/entitlement gates fail;
- the invocation ceiling would be exceeded;
- ledger integrity fails;
- an invocation-start marker exists without complete immutable case evidence;
- another live/unknown campaign process owns the campaign lock;
- an existing campaign artifact cannot be safely reconciled.

No retry is performed.

## Crash-safe resume

`case_invocation_started` is written through the single-case driver's `before_invoke` hook at the exact provider-call boundary. The hook is invoked from `execute_draft_invocation()`'s capturing invoker only after `build_bilingual_draft_run()` has completed all deterministic pre-invocation validation/rendering/accounting work, and immediately before the actual provider closure is entered. This is the conservative no-duplicate-call marker.

If the process dies after that narrow start marker and restart sees `case_invocation_started` without a complete immutable report + sidecar, the invocation is ambiguous. The campaign stops for operator reconciliation and **does not automatically retry** that case. Failures before the hook—including route/env conflict, missing credential, provider-construction failure, single-case preflight refusal, or deterministic `build_bilingual_draft_run()` work before the wrapped invoker is reached—create no invocation-start marker and therefore do not falsely consume an ambiguous case slot.

If the process dies in the narrower interval **after** the single-case report is frozen but **before** the terminal case ledger event is appended, the next campaign start:

1. requires the matching prior `case_invocation_started` event; a complete report with no campaign start marker is foreign/ambiguous evidence and is rejected;
2. finds the report + sidecar;
3. verifies their hash;
4. verifies report version, reviewed head, model, fixture hash, terminology hash, invocation count, **exact campaign attestation**, requested route, and both resolved-route fields against the manifest's official route URL;
5. recomputes the frozen rendered-input/raw-output hashes, reconstructs the context and terminology-delivery blocks, and independently rebuilds the expected context/rendered input from the manifest-bound fixture + terminology registry + frozen context `created_at`; exact equality is required even when the original provider execution failed before producing a structural result;
6. when a structural result exists, **replays the deterministic bilingual-drafting boundary** from the frozen raw response using the original structural timestamps/model trace; the replayed structural run must exactly equal the stored structural result, and candidate-only/no-publication/no-canonical authority must still hold;
7. records the case as `recovered_without_invocation: true`;
8. continues to the next case if the recovered result is not an execution failure.

It never reruns an ambiguous or already-frozen case merely because the ledger event is missing.

An incomplete report/sidecar pair is ambiguous evidence and stops the campaign.

## Concurrency lock

A campaign evidence directory carries an exclusive `.campaign.lock`.

- any existing lock blocks another controller, regardless of recorded PID/host/manifest;
- the controller never automatically unlinks or reclaims an existing lock;
- normal shutdown releases only the token-bound lock it owns;
- a crash-residue lock requires explicit operator reconciliation/removal after confirming no campaign controller is live.

This conservative policy removes stale-lock time-of-check/time-of-use races and prevents two campaign processes from independently consuming the same call budget.

## Hash-chained ledger

The append-only `campaign-ledger.jsonl` uses `m4-drafting-campaign-ledger-v0.1`.

Every event carries:

- campaign ID;
- manifest SHA-256;
- contiguous sequence number;
- previous event SHA-256;
- event type;
- event payload;
- timestamp;
- its own SHA-256 over the canonical event material.

Ledger replay verifies the complete chain before additional provider work. On every nonterminal resume, all already-recorded case-terminal events are also re-closed over their immutable report/sidecar and deterministic `verify_case_report()` boundary **before any fresh provider invocation**. A missing/corrupted recorded case therefore stops the campaign without spending additional entitlement.

If a `case_execution_failure` record exists but the process died before `campaign_stopped` was appended, resume verifies that failure evidence, finalizes `stopped_execution_failure`, and returns without invoking later cases. Any later case-terminal record after an execution failure is rejected as invalid campaign history.

Case terminal events record case ID, fixture hash, report path/hash, invocation count, structural status, execution error, and whether the event was recovered from pre-existing immutable evidence.

Terminal campaign states are:

- `completed`;
- `stopped_execution_failure`;
- `stopped_call_ceiling`.

## Aggregate summary

Terminal campaigns write immutable:

- `campaign-summary.json`;
- `campaign-summary.json.sha256`.

On every terminal rerun the controller first re-closes every case-terminal ledger event over its actual immutable per-case report: report + sidecar are required, `verify_case_report()` replays the manifest/route/attestation/evidence boundary, and the verified report hash/invocation count/structural status/execution error/path/fixture binding must match the ledger payload. Only then does the controller re-verify the summary sidecar and bytes, rebuild the expected summary from the validated ledger, and require exact semantic equality before returning it. A corrupted, missing, or replaced case artifact or summary is never trusted merely because the ledger is terminal.

Summary version: `m4-drafting-campaign-summary-v0.1`.

The summary reports only deterministic campaign evidence:

- total/recorded cases;
- invocation count;
- structural accepts;
- structural rejects;
- execution failures;
- per-case report hashes and status.

It explicitly retains:

- `editorial_quality_qualified: false`;
- `production_model_pipeline_qualified: false`;
- `publication_authority: false`;
- `canonical_mutation_authority: false`.

Arabic/English editorial review remains a separate human activity over the frozen per-case evidence.

## Deterministic validation

`scripts/validate_m4_drafting_campaign.py` runs with fake provider factories only and proves:

- manifest version/file-hash/exact call-ceiling gates;
- campaign-specific entitlement ID + route binding and exact attestation-hash continuity across resume;
- frozen campaign-manifest artifact binding;
- git-tracked corpus/terminology enforcement in addition to SHA-256 binding;
- structural rejection continues to the next case;
- success invokes exactly once per fresh case;
- provider failure stops after one call and does not continue;
- terminal rerun performs zero new calls while re-verifying every referenced per-case report against the terminal ledger;
- route/env ambiguity, missing credential, provider-construction failure, and deterministic pre-invoker boundary failure occur before `case_invocation_started` and leave zero invocations plus no ambiguous start marker;
- completed-but-unledgered case evidence is recovered without reinvocation only when a matching campaign invocation-start marker exists;
- recovered case evidence must match the exact campaign attestation and manifest route;
- recovered case evidence is deterministically replayed from its frozen input/raw-output bytes, and any re-hashed structural-result/evidence tamper is rejected;
- a standalone report without a campaign invocation-start marker is rejected as foreign/ambiguous evidence;
- an invocation-start marker without terminal evidence blocks automatic retry;
- ledger tampering is rejected before more provider activity;
- terminal summary byte/sidecar/semantic tampering is rejected before provider activity;
- any pre-existing campaign lock—including a stale/dead-PID-shaped residue—is fail-closed and never auto-reclaimed;
- nonterminal resume re-verifies recorded case evidence before fresh provider work;
- a recorded execution failure with a missing campaign-stopped event is terminalized on resume with zero later invocations;
- campaign summary authority and editorial qualification remain false.

## Relationship to the single-case driver

The single-case driver remains the authoritative live invocation primitive:

`campaign controller -> run_trial() -> reviewed drafting boundary -> provider edge -> immutable single-case report`

The campaign controller adds only campaign-level sequencing, manifest binding, call ceilings, resumability, ledger integrity, concurrency exclusion, and aggregate structural reporting.

## Claim ceiling

Passing deterministic validation means the controller implements the bounded execution mechanics described above.

It does **not** prove live provider quality, Arabic or English editorial quality, representative throughput, cost behavior, production reliability, long-duration operational reliability, scheduler suitability, or safe autonomous operation. Those require separately frozen live evidence and review.
