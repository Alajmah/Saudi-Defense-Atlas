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
- `model`;
- `timeout_seconds`;
- `max_invocations`;
- single-case driver report version;
- drafting adapter version;
- prompt-template version;
- repository-relative terminology file path + SHA-256;
- ordered cases, each carrying `case_id`, repository-relative fixture path, and fixture SHA-256.

Unknown manifest keys are rejected. Absolute/out-of-repository fixture or terminology paths are rejected. Every bound file hash is recomputed before the campaign begins.

The invocation ceiling must be at least the number of frozen cases. There is no retry authority, so the controller has no legitimate reason to exceed one call per fresh case.

Example shape:

```json
{
  "version": "m4-drafting-campaign-v0.1",
  "campaign_id": "M4-DRAFT-CAMPAIGN-001",
  "reviewed_head": "<40-hex reviewed controller head>",
  "route": "coding-plan",
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
- another live/unknown campaign process owns the campaign lock;
- an existing campaign artifact cannot be safely reconciled.

No retry is performed.

## Crash-safe resume

Each successful or failed single-case invocation first produces the single-case immutable report and sidecar. The campaign then records the case in its ledger.

If the process dies in the narrow interval **after** the single-case report is frozen but **before** the ledger event is appended, the next campaign start:

1. finds the report + sidecar;
2. verifies their hash;
3. verifies report version, reviewed head, model, fixture hash, terminology hash, and invocation count;
4. records the case as `recovered_without_invocation: true`;
5. continues to the next case if the recovered result is not an execution failure.

It never reruns an ambiguous or already-frozen case merely because the ledger event is missing.

An incomplete report/sidecar pair is ambiguous evidence and stops the campaign.

## Concurrency lock

A campaign evidence directory carries an exclusive `.campaign.lock`.

- a live same-host PID blocks another controller;
- a lock from another host fails closed;
- a same-host lock whose recorded PID is demonstrably dead is treated as a crash residue and may be reclaimed for the same manifest;
- a lock bound to another manifest is rejected.

This lock prevents two campaign processes from independently consuming the same call budget.

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

Ledger replay verifies the complete chain before additional provider work.

Case terminal events record case ID, fixture hash, report path/hash, invocation count, structural status, execution error, and whether the event was recovered from pre-existing immutable evidence.

Terminal campaign states are:

- `completed`;
- `stopped_execution_failure`;
- `stopped_call_ceiling`.

## Aggregate summary

Terminal campaigns write immutable:

- `campaign-summary.json`;
- `campaign-summary.json.sha256`.

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

- manifest version/file-hash/call-ceiling gates;
- structural rejection continues to the next case;
- success invokes exactly once per fresh case;
- provider failure stops after one call and does not continue;
- terminal rerun performs zero new calls;
- completed-but-unledgered case evidence is recovered without reinvocation;
- ledger tampering is rejected before more provider activity;
- campaign summary authority and editorial qualification remain false.

## Relationship to the single-case driver

The single-case driver remains the authoritative live invocation primitive:

`campaign controller -> run_trial() -> reviewed drafting boundary -> provider edge -> immutable single-case report`

The campaign controller adds only campaign-level sequencing, manifest binding, call ceilings, resumability, ledger integrity, concurrency exclusion, and aggregate structural reporting.

## Claim ceiling

Passing deterministic validation means the controller implements the bounded execution mechanics described above.

It does **not** prove live provider quality, Arabic or English editorial quality, representative throughput, cost behavior, production reliability, long-duration operational reliability, scheduler suitability, or safe autonomous operation. Those require separately frozen live evidence and review.
