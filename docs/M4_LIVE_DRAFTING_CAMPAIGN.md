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

Unknown manifest keys are rejected. Case IDs that alias controller artifact stems (`campaign-manifest`, `campaign-summary`, `campaign-ledger`) are reserved and rejected **case-insensitively**; Windows device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`) are also rejected case-insensitively; all case IDs must be unique under Unicode `casefold()`; and the derived `<case_id>.json.sha256` filename component must remain within the portable 255-byte component limit. Absolute/out-of-repository fixture or terminology paths are rejected. The terminology registry and every case fixture must also be **git-tracked** in the reviewed checkout; an untracked local corpus file is not accepted merely because it is under the repository root. Every bound file hash is recomputed before the campaign begins.

The invocation ceiling must equal the number of frozen cases. There is no retry authority, so any larger ceiling would be unused authority and any smaller ceiling could not cover the frozen corpus.

The supplied runtime entitlement attestation must bind the **exact campaign manifest**. It must contain the manifest's `entitlement_id`, `campaign_id`, full canonical `manifest_sha256`, and the manifest route (`coding-plan`, or `prepaid` / `general`). Reusing an entitlement ID and route with a changed model, corpus ordering, case count/call ceiling, or any other manifest field is rejected because the canonical manifest hash changes. The campaign controller preserves the supplied attestation string exactly and records a SHA-256 of those exact UTF-8 bytes in the first ledger event; validation may inspect a stripped/case-folded view, but evidence is never normalized. **Every resume must supply the same attestation bytes, including leading/trailing whitespace**, proven by that SHA-256, before additional provider activity. Each single-case report records the same exact supplied attestation under the reviewed driver contract.

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

Before each fresh case, source state is checked again. Local HEAD must remain the manifest's reviewed SHA and the tracked worktree must remain clean. At the **actual provider-call boundary**, the campaign checks source state again, recomputes the manifest-bound fixture and terminology SHA-256 values, reconstructs the expected ApprovedDraftingContext and complete rendered prompt from freshly reread bytes using the prompt's frozen `created_at`, and requires exact equality with the prompt about to be sent. This closes the interval between initial rendering and provider entry: mutated source bytes cannot be transmitted merely because post-call verification would later detect them.

The route remains manifest-bound. The campaign supplies exactly one route selector to the reviewed single-case driver; a conflicting `ZAI_BASE_URL` remains subject to the driver's fail-closed ambiguity gate.

## Stop/continue policy

### Continue

An ordinary model structural rejection is preserved as a valid case result and **does not stop the campaign**.

Examples include schema/grounding/accounting/terminology/restricted-detail rejection produced by the reviewed drafting boundary after a provider response was obtained.

### Stop immediately

The campaign stops without moving to the next case when:

- provider/transport execution fails (including exceptions whose string message is empty; those are normalized to a non-empty exception-type diagnostic);
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

`case_invocation_started` is written through the single-case driver's `before_invoke` hook at the exact provider-call boundary. The hook receives the exact rendered prompt, revalidates reviewed source state and manifest-bound fixture/terminology bytes, reconstructs the expected prompt from those fresh bytes, and only then writes the marker. It is invoked from `execute_draft_invocation()`'s capturing invoker after `build_bilingual_draft_run()` has completed deterministic pre-invocation validation/rendering/accounting work and immediately before the actual provider closure is entered. This is the conservative no-duplicate-call marker.

If the process dies after that narrow start marker and restart sees `case_invocation_started` without a complete immutable report + sidecar, the invocation is ambiguous. The campaign stops for operator reconciliation and **does not automatically retry** that case. Failures before the hook—including route/env conflict, missing credential, provider-construction failure, single-case preflight refusal, or deterministic `build_bilingual_draft_run()` work before the wrapped invoker is reached—create no invocation-start marker and therefore do not falsely consume an ambiguous case slot.

If the process dies in the narrower interval **after** the single-case report is frozen but **before** the terminal case ledger event is appended, the next campaign start:

1. requires the matching prior `case_invocation_started` event; a complete report with no campaign start marker is foreign/ambiguous evidence and is rejected;
2. finds the report + sidecar;
3. verifies their hash;
4. verifies the report's deterministic driver provenance before recovery: report/provider identity, null provider-checkpoint placeholder, top-level reviewed head, **`trial_context.git_head == reviewed_head` and `trial_context.tracked_worktree_clean == true`**, requested model, drafting/extraction adapter provenance, prompt-template version/ID/hash, provider-edge driver/transport/tools/reasoning/credential-source/route-source fields, drafting-entitlement scope flag, fixture and terminology versions/hashes, **`invocation.attempted == true` and `invocation.count == 1`**, served-model-checkpoint placeholder, claim ceiling, exact campaign attestation, requested route, and both resolved-route fields against the manifest's official route URL;
5. recomputes the frozen rendered-input/raw-output hashes, reconstructs the context and terminology-delivery blocks, and independently rebuilds the expected context/rendered input from the manifest-bound fixture + terminology registry + frozen context `created_at`; exact equality is required even when the original provider execution failed before producing a structural result;
6. requires `editorial_assessment` to remain exactly the single-case builder's unreviewed placeholder (`status = pending_human_review`, null score/notes, unchanged assessment dimensions); when a structural result exists, then requires its `model_trace` to match the reviewed single-case driver identity (`provider = zai-openai-compatible-api`, `model = manifest.model`, `model_version = provider-managed-unknown`), then **replays the deterministic bilingual-drafting boundary** from the frozen raw response using those bound trace values and the original structural timestamps; the replayed structural run must exactly equal the stored structural result, and candidate-only/no-publication/no-canonical authority must still hold;
7. records the case as `recovered_without_invocation: true`;
8. continues to the next case if the recovered result is not an execution failure.

It never reruns an ambiguous or already-frozen case merely because the ledger event is missing.

An incomplete report/sidecar pair is ambiguous evidence and stops the campaign.

## Campaign instance binding and concurrency lock

Each exact manifest has one deterministic runtime namespace under the repository's Git common directory, keyed by the canonical `manifest_sha256` and independent of `--evidence-dir`.

The first campaign start atomically creates a **persistent manifest-to-evidence-directory binding** in that namespace. The binding survives normal completion and live-lock release. A later attempt to run the same exact approved manifest with a different evidence directory is rejected before credential or provider activity. To authorize a distinct campaign run, create and approve a distinct manifest (normally with a new `campaign_id` / entitlement identity), rather than deleting the binding and replaying the old approval.

The same manifest namespace carries a transient exclusive `.campaign.lock` while a controller is live:

- the same authorized manifest cannot run concurrently into two different evidence directories in the same repository runtime namespace;
- any existing lock blocks another controller;
- the controller never automatically unlinks or reclaims an existing lock;
- normal shutdown releases only the token-bound lock it owns;
- a crash-residue lock requires explicit operator reconciliation/removal after confirming no campaign controller is live.

Together, persistent instance binding plus the transient live lock prevent one approved manifest from independently consuming its invocation ceiling twice in the supported **single-repository-runtime** scope, including sequential attempts with different evidence directories.

**Cross-host / independent-clone global exclusion is not claimed**; that would require a shared atomic coordinator.

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

Ledger replay verifies the complete chain before additional provider work. On every nonterminal resume, the controller also validates semantic history **before any fresh provider invocation**: only known nonterminal event types are allowed; invocation-start and case-terminal events must form ordered manifest prefixes; case results must follow their matching start markers; at most one unmatched start marker may exist and it must be the final event; and any recorded execution failure must be the final recorded/final ledger event awaiting terminalization. All already-recorded case-terminal events are then re-closed over their immutable report/sidecar and deterministic `verify_case_report()` boundary **before any fresh provider invocation**. A missing/corrupted recorded case therefore stops the campaign without spending additional entitlement.

If a `case_execution_failure` record exists but the process died before `campaign_stopped` was appended, resume verifies that failure evidence, finalizes `stopped_execution_failure`, and returns without invoking later cases. Any later case-terminal record after an execution failure is rejected as invalid campaign history.

Case terminal events record case ID, fixture hash, report path/hash, invocation count, structural status, execution error, and whether the event was recovered from pre-existing immutable evidence.

Terminal campaign states are:

- `completed`;
- `stopped_execution_failure`;
- `stopped_call_ceiling`.

A terminal event is trusted only after semantic history validation. There must be exactly one terminal campaign event and it must be the final ledger event; invocation-start and case-terminal events must form ordered manifest prefixes; every recorded case result must follow its matching invocation-start marker; `completed` must cover the entire frozen corpus with no execution-failure case; and `stopped_execution_failure` must bind exactly the failed final recorded case. A recomputed hash chain cannot manufacture a valid terminal state from unsupported history.

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

- manifest version/file-hash/exact call-ceiling gates, including rejection of case IDs reserved for controller artifacts, Windows device aliases, case-insensitive collisions, and case IDs whose derived evidence sidecar basename would exceed the portable 255-byte component limit;
- exact-manifest campaign authorization binding: entitlement ID + campaign ID + full canonical manifest SHA-256 + route, with exact **un-normalized attestation-byte** hash continuity across resume;
- frozen campaign-manifest artifact binding;
- git-tracked corpus/terminology enforcement in addition to SHA-256 binding;
- structural rejection continues to the next case;
- success invokes exactly once per fresh case;
- provider failure stops after one call and does not continue, including empty-message exceptions normalized to a non-empty diagnostic;
- terminal rerun performs zero new calls while re-verifying every referenced per-case report against the terminal ledger;
- route/env ambiguity, missing credential, provider-construction failure, deterministic pre-invoker failure, and provider-boundary source/prompt drift occur before `case_invocation_started` and leave zero invocations plus no ambiguous start marker;
- completed-but-unledgered case evidence is recovered without reinvocation only when a matching campaign invocation-start marker exists;
- recovered case evidence must match the exact campaign attestation and manifest route, preserve all deterministic single-case driver provenance (provider/edge/boundary/fixture/terminology/checkpoint/claim-ceiling metadata) and the pending editorial placeholder, prove execution from the reviewed clean checkout, and prove exactly one attempted provider invocation;
- aggregate-summary residue and every unrecorded case artifact state are preflighted before any fresh invocation, so stale/foreign terminal artifacts or later ambiguous evidence cannot consume entitlement on earlier cases;
- recovered case evidence is deterministically replayed from its frozen input/raw-output bytes only after provider/model/model-version provenance is bound to the campaign/driver identity; any re-hashed trace, structural-result, or evidence tamper is rejected;
- a standalone report without a campaign invocation-start marker is rejected as foreign/ambiguous evidence;
- an invocation-start marker without terminal evidence blocks automatic retry;
- ledger hash tampering and semantic nonterminal-history tampering are rejected before more provider activity, including unknown event types and out-of-order case starts;
- terminal summary byte/sidecar/semantic tampering is rejected before provider activity;
- terminal ledger semantics are validated independently of the hash chain, including rejection of `campaign_completed` without full case coverage and `stopped_execution_failure` without a matching failed case;
- one deterministic per-manifest checkout lock excludes the same manifest across different evidence directories; any pre-existing lock—including a stale/dead-PID-shaped residue—is fail-closed and never auto-reclaimed;
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
