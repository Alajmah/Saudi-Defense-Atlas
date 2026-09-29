# M4 Bounded Real-Model Extraction Trial — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review. It was performed before any Codex review request for this increment.

The review follows the repository rule that discovery and first-pass defect finding belong to the maintainer review; Codex is an independent second reviewer only after this baseline is frozen.

## Baseline and review surface

Base branch / merge base:

- `main` at `927e79dfcd95e3cfa25ed02dbac7cae024c6d602`.

Implementation baseline reviewed before this review record was added:

- `m4/model-extraction-trial` at `4c21a27221c4d791f32a53a39919de1d85aa5fae`.

Net implementation/documentation surface at that baseline:

1. `.github/workflows/m4-model-extraction-trial.yml`
2. `.github/workflows/schema-validation.yml`
3. `docs/M4_MODEL_EXTRACTION_TRIAL.md`
4. `docs/ROADMAP.md`
5. `scripts/run_m4_model_extraction_trial.py`
6. `scripts/validate_m4_model_extraction_trial.py`
7. `services/intelligence/model_extraction_trial.py`
8. `tests/fixtures/m4-model-extraction-eval.json`

Temporary staging/materializer files used during branch construction were removed and are not part of the net diff.

## Intent and authority boundary

The forcing function is the merged M4 roadmap requirement for one bounded real-model extraction trial before M4 can claim operating model-backed extraction.

The increment is correctly narrow:

- provider-independent SDA trial boundary;
- a manual Copilot CLI edge driver selected only for the trial;
- synthetic `public_non_operational` fixtures only;
- only claimed `candidate_extraction` queue work may reach the invoker;
- restricted/RED-style fixtures fail before invocation;
- output remains the existing candidate-only `AIExtractionRun` contract;
- model-created identities remain `CAND-*`;
- Resolver/Verifier, human review, canonical mutation, and publication authority remain separate;
- no scheduler, autonomous worker, second truth store, or production model platform is introduced.

No canonical mutation or publication authority was found in the new service, runner, corpus, or workflow.

## Multi-pass review

### Intent / architecture

PASS after remediation.

The provider-specific choice is confined to the live runner/workflow edge. Domain semantics continue to depend on `AIExtractionRun` and the existing extraction boundary rather than Copilot-specific objects. The roadmap and trial document explicitly treat the Copilot CLI choice as a scoped trial implementation, not generalized production adoption.

### Structure / data flow

PASS after remediation.

The bounded path is:

```text
synthetic evaluation case
  -> pre-invocation trial validation
  -> exact rendered prompt
  -> caller-supplied model invoker
  -> exact captured response text
  -> strict JSON envelope / case allowlist
  -> existing AIExtractionRun candidate boundary
  -> JSON Schema validation
  -> accepted candidate-review run OR isolated rejected run
  -> evaluation report
```

Rejected model output exposes empty candidate arrays. The live runner does not call Resolver/Verifier, review binding, mutation dispatch, Wikibase, or public publication paths.

### Correctness / integrity

PASS after remediation for the deterministic harness.

Verified properties include:

- exact prompt-template SHA;
- exact rendered prompt SHA in `input_sha256`;
- exact captured model-response SHA in `raw_output_sha256`;
- separate invocation identity when otherwise-identical requests/responses occur at different invocation times;
- queue lane/state/AI-authorization/provenance preconditions;
- strict four-key JSON response envelope;
- per-case Claim predicate and Event-type allowlists;
- CAND-only candidate/reference closure through the existing extraction boundary;
- out-of-scope Document rejection;
- schema-invalid candidate isolation into an empty-candidate rejected run;
- no mutation/publication authority in accepted or rejected runs.

### Failure modes

PASS for the bounded deterministic harness; live service dependency remains unverified.

Fail-closed cases exercised deterministically include:

- restricted sensitivity;
- wrong queue lane / no AI authorization;
- malformed JSON;
- unsupported model-output keys;
- non-allowlisted predicate;
- provenance escape;
- model-produced canonical identity;
- structural schema failure;
- tampered prompt argument;
- overlong model-trace fields.

The live runner records Copilot execution/timeout/trial-adapter failures as integrity failures and uploads the report before the manual workflow propagates failure.

### Security / operational sensitivity

PASS for the intended synthetic trial boundary; no production-security claim is made.

The live command narrows Copilot CLI to prompt mode with `--available-tools=ask_user`, while `--no-ask-user` disables the sole remaining model-visible tool. Read/write/shell/url/memory permission kinds are also denied; built-in MCPs, custom instructions, remote control/export, experimental features, and auto-update are disabled.

This is a command-surface control, not an air-gap claim. The workflow still depends on GitHub-hosted runner and Copilot service behavior.

The evaluation corpus contains no real live unit position, readiness, stock, patrol, or tactical-vulnerability data. The restricted case is synthetic and exists only to prove pre-invocation blocking.

### Operability

PASS for a manual trial harness, with one external prerequisite.

- workflow is `workflow_dispatch` only;
- repository workflow permission is `contents: read`;
- Copilot CLI is pinned to `@github/copilot@1.0.88`;
- a dedicated `COPILOT_GITHUB_TOKEN` repository secret is required for the live trial;
- deterministic validation runs before credential use/model invocation;
- report artifact retention is bounded to 30 days;
- the workflow contains no canonical-backend credentials.

A missing credential intentionally prevents the live trial. This PR does not establish that the repository currently has that secret configured.

### Maintainability / provider independence

PASS.

The provider-specific CLI construction lives in the runner. The SDA service accepts a text invoker and emits the existing project contract. Model provider/checkpoint uncertainty is explicit rather than invented: the requested model is recorded, while the provider checkpoint remains unknown to the harness.

### Evidence / claim ceiling

PASS after documentation remediation.

The implementation may support a future live trial, but this branch does not itself prove model quality, performance, representative throughput, production suitability, or downstream real-model passage through Resolver/Verifier and human review. Those remain explicit follow-up gates.

## First-pass findings register

All findings below were identified before Codex invocation.

### FP-01 — BLOCKING — prompt template could not render

**Observed:** the first implementation embedded literal JSON braces inside a Python `str.format` template. CI raised `KeyError('"kind"')`, so the harness could not construct a prompt and could never reach a model.

**Remediation:** removed brace-sensitive literal examples from the template while preserving the candidate-reference rule. Added/retained deterministic prompt construction coverage.

**Remediated by:** `99186120bef2323870a064ff5e431718e02199ab`.

**Status:** CLOSED. Full schema-validation subsequently passed on this implementation line.

### FP-02 — HIGH — `input_sha256` was not the exact model input

**Observed:** the first adapter hashed a reconstructed metadata object rather than the exact rendered prompt supplied to the model.

**Risk:** trace replay/audit could not prove the actual input bytes represented by the recorded hash.

**Remediation:** `input_sha256` now hashes the exact rendered prompt string, and the adapter rejects a caller-supplied prompt that differs from the approved rendering.

**Status:** CLOSED; deterministic assertion added.

### FP-03 — HIGH — raw response was altered before hashing

**Observed:** the live Copilot invoker used `.strip()` on stdout before `raw_output_sha256` was computed.

**Risk:** the recorded hash did not represent the exact captured model response.

**Remediation:** preserve `result.stdout` exactly and hash the exact returned string, including surrounding whitespace.

**Status:** CLOSED; deterministic assertion added.

### FP-04 — HIGH — repeated invocations could collapse to one run identity

**Observed:** the initial content-addressed run ID seed omitted invocation timestamps. Identical model trace/input/output could therefore mint the same `AIExtractionRun.id` across separate invocations.

**Risk:** distinct model calls could become indistinguishable as run identities.

**Remediation:** include `started_at` and `completed_at` in the run identity seed while retaining exact input/output hashes.

**Status:** CLOSED; adversarial assertion proves separate invocations receive different IDs.

### FP-05 — HIGH — CLI isolation documentation exceeded the command surface

**Observed:** broad read/write/shell/url/memory permission denial alone still left additional non-permission-kind tools visible in the normal CLI availability surface, while the documentation described the model as prompt-only.

**Risk:** documentation overstated isolation and left an unnecessarily broad visible tool surface.

**Remediation:** constrain `--available-tools` to `ask_user` and simultaneously apply `--no-ask-user`; retain broad denials as defense in depth; disable built-in MCPs, custom instructions, remote control/export, experimental features, and auto-update. Documentation now describes this as a command-surface control rather than an air gap.

**Status:** CLOSED for the pinned command construction; live service behavior remains to be exercised by the manual trial.

### FP-06 — MEDIUM — model trace/version semantics could misrepresent provider identity

**Observed:** the initial runner reused the requested model identifier as `model_version` and concatenated CLI-version text into `adapter_version`, which could both misstate provider checkpoint identity and approach the schema length ceiling.

**Remediation:** keep the adapter version stable, record CLI version separately in the report, record requested model separately, and set model checkpoint/version to explicit `provider-managed-unknown` rather than invent a provider checkpoint.

**Status:** CLOSED.

### FP-07 — HIGH — qualification flag could overstate a failed live trial

**Observed:** `candidate_only_boundary_exercised` initially became true merely when a model invocation occurred, even if no run survived schema/semantic validation.

**Risk:** an all-failure trial could be described as exercising the accepted candidate boundary.

**Remediation:** added `validated_run_count`; candidate-boundary qualification becomes true only when at least one run passes JSON Schema and semantic extraction-boundary validation. `trial_integrity_clean` is reported separately.

**Status:** CLOSED.

### FP-08 — MEDIUM — invalid trace could fail after invocation / adapter exceptions could bypass report generation

**Observed:** model-trace validation was lazy, and the live runner did not catch `ModelExtractionTrialError` inside the case loop.

**Risk:** invalid user-supplied trace input could be discovered after an external invocation; a trial-adapter error could abort before the report artifact was produced.

**Remediation:** preflight `ModelTrace.as_dict()` before constructing the live invocation loop and capture case-level `ModelExtractionTrialError` alongside subprocess/runtime failures as integrity failures.

**Remediated by:** `40da6c533c26fc74bbc9e8b6ff4a42265d6d40ab`.

**Status:** CLOSED.

### FP-09 — MEDIUM — roadmap would become stale on merge

**Observed:** the merged roadmap still stated that no real-model adapter/provider had been selected, which would become false once this trial driver/harness merged.

**Remediation:** roadmap now distinguishes the implemented trial-only driver/harness from still-unexecuted/unreviewed live evidence and from any production provider/platform adoption.

**Remediated by:** `4c21a27221c4d791f32a53a39919de1d85aa5fae`.

**Status:** CLOSED.

## Deterministic validation evidence

Relevant CI evidence before this review record was added:

- schema-validation run #726 on `99186120bef2323870a064ff5e431718e02199ab` — **PASS**, including the new bounded model-extraction validator after the blocking prompt-render fix;
- schema-validation run #728 on `40da6c533c26fc74bbc9e8b6ff4a42265d6d40ab` — **PASS**, including the trace/isolation/operability remediations;
- exact implementation-baseline run #729 on `4c21a27221c4d791f32a53a39919de1d85aa5fae` was started after the roadmap-only sync and must be green before the PR is promoted.

The review-document commit itself changes the head. Exact-head CI and a final maintainer diff review are required after this record lands.

## Explicitly unverified / unresolved

The following remain outside this increment's verified evidence and must not be generalized:

- no live Copilot trial report has yet been produced/reviewed;
- the repository secret `COPILOT_GITHUB_TOKEN` is not proven configured by this review;
- actual model quality is unknown;
- actual bounded-trial latency and observed throughput are unknown until execution;
- monetary cost is intentionally unmeasured/unknown in the harness;
- provider checkpoint/version behind the requested model is unknown to the harness;
- representative batch-volume / “at scale” extraction is unqualified;
- real-model candidates have not yet been demonstrated through Resolver/Verifier and the human review packet/decision path;
- no production model provider/platform is selected or qualified;
- no scheduler/orchestrator/autonomous worker is selected;
- no distributed writer coordinator is selected or qualified;
- no truth, approval, canonical-mutation, or publication authority is added.

## Frozen maintainer baseline

The maintainer first-pass findings above are frozen before Codex invocation. Any later Codex findings must be reconciled against this baseline rather than replacing it.

Next gate sequence:

1. exact-head CI after this review record;
2. final maintainer review of the resulting exact diff;
3. open PR and record the exact-head maintainer review;
4. only then invoke Codex as independent second reviewer;
5. reconcile/remediate any Codex findings and repeat exact-head validation before merge.
