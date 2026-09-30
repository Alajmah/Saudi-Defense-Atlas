# M4 Z.ai Live Rerun v0.6 — Fallback Second Review

## Protocol status

This record is the documented maintainer fallback second review for PR #32 after the Codex connector reported code-review quota exhaustion on the PR (`5908686680`: "You have reached your Codex usage limits for code reviews."). A fresh `@codex review` request was also posted against the exact frozen head, but no independent Codex review result was available when this fallback was performed.

This fallback is intentionally labeled. It does **not** claim Codex reviewer independence and does not erase the reduced reviewer-independence limitation. It is permitted by the repository's established fallback protocol after the maintainer first-pass record has been frozen.

## Frozen review baseline

Evidence-preservation head reviewed:

- `f6608c05f3fbbb1748c156c96613232d000d75ba`

Base:

- `main` at `3c02ca0fb68e101c14f1b1d07d479cd2b40c9cfa`

PR #32 at the frozen baseline contains exactly three files:

- `docs/evidence/m4/2026-09-30/m4-zai-live-rerun-v0.6.json`
- `docs/evidence/m4/2026-09-30/m4-zai-live-rerun-v0.6.json.sha256`
- `docs/reviews/M4_ZAI_LIVE_RERUN_V06_FIRST_PASS.md`

The evidence-preservation guard on `main` remains `docs/evidence/** -text`.

Exact-head workflow evidence before this record:

- push `schema-validation` run `36698400008` — success on `f6608c05...`;
- PR `schema-validation` run `36698493105` — success on `f6608c05...`;
- operator-reported local deterministic suite: 38/38 validators pass.

The local validator statement is operator evidence; the GitHub workflow results above were independently checked through GitHub.

## Byte-preservation verification

The committed Git blob IDs match the uploaded artifacts byte-for-byte:

- report blob: `7d2e362708832b72d10217db1f969a26162ec06e`;
- sidecar blob: `9ff26c8101225e381241528fc14ea13747379b37`;
- frozen first-pass review blob: `360b1d8a09a346f9d98384078e42bad064339370`.

Independent checks of the uploaded report establish:

- exact size: 28,177 bytes;
- SHA-256: `fd24bd27a403d69015bd91cb081f9c3e1ef22fdd2ea41627590ae7ca1dd1737e`;
- sidecar matches that digest and filename exactly;
- no CRLF bytes; report ends with LF;
- JSON parses successfully.

The exact API-key value was not available to the reviewer, so exact-secret-string absence is not independently asserted. The report contains no literal `Authorization`, `Bearer `, `api_key`, `secret`, or `token` strings; `ZAI_API_KEY` appears only as the credential-source label.

## Evidence interpretation verification

### Metric semantics — first-pass RRV6-01 confirmed

The report records:

- whole-corpus exact-gold: 3/6 = 50%;
- invoked-case exact-gold: 2/5 = 40%;
- policy gate: 1/1 = 100%.

The 2/5 invoked metric combines four cases whose gold expects `accepted_for_candidate_review` with one expected complete-abstention/rejection case. Among the four substantive accepted-extraction cases, only `TRIAL-PROMPT-INJECTION` passes exact gold. The derived substantive accepted-case result is therefore **1/4 = 25%**.

That derived figure is useful for review but is not currently emitted as a first-class report metric. The first-pass warning not to describe 40% as semantic extraction accuracy is correct.

### Role-selection semantics — first-pass RRV6-02 confirmed

The candidate boundary now enforces the canonical eleven-role vocabulary, so the first live run's out-of-vocabulary downstream incompatibility is closed.

The remaining Event mismatches are in-vocabulary:

- delivery: observed `supplier`, gold `manufacturer`;
- Arabic contract signature: observed `supplier`, gold `contractor`.

The canonical Event schema enumerates the labels but does not define event-type-specific precedence or a semantic rule choosing among these in-vocabulary alternatives. Repository search did not identify a separate normative role-assignment policy that resolves these two choices.

The exact-gold failures are real benchmark failures. The current SDA contracts do **not** establish that the observed in-vocabulary choices are semantically wrong. Gold must not be loosened post hoc to fit this model output.

### Unit normalization — first-pass RRV6-03 confirmed

The quantity case now obeys the reviewed exact-number normalization:

- `value: 12`;
- `precision: exact`;
- `lower_bound: null`;
- `upper_bound: null`.

Its remaining mismatch is `unit: "trainer aircraft"` versus gold `unit: "aircraft"`. Canonical `number_value.unit` is a nullable free string; no canonical unit vocabulary or normalization rule defines one representation as mandatory. The first-pass classification as an under-specified normalization contract is therefore supported.

### Causal-claim ceiling — first-pass RRV6-04 confirmed

The rerun is observational evidence from a second provider execution. The report still has `provider_checkpoint_version: null`, and the request does not establish a controlled deterministic experiment across the two executions. The supported wording is that the revised contract **produced a better exact-gold outcome in this observed rerun**. The evidence does not establish that the contract revision caused a 40-point gain.

### Performance ceiling — first-pass RRV6-05 confirmed

The rerun has five model invocations. Median latency is lower than the first run, while tail latency is higher and observed aggregate throughput is lower. This sample cannot qualify representative batch performance, throughput, scale, or production latency.

## Contract-delta verification

The four targeted contract deltas are evidenced in this rerun:

- canonical Event-role vocabulary: no out-of-vocabulary accepted roles;
- Evidence locator/cardinality: substantive accepted outputs use the exact trial locator/cardinality convention;
- exact numeric representation: the quantity case uses null bounds for the exact scalar;
- complete abstention: `TRIAL-INSUFFICIENT` returns all arrays empty and rejects via `no-substantive-candidates` with all-zero pre-clear counts.

Additional observed improvements recorded by the first pass are also supported: the Arabic re-subjectified Claim defect did not recur; the delivery equipment variant is typed as `equipment_variant`; the prompt-injection case passes exact gold.

## Fallback finding

### FRR6-01 — MEDIUM — preserve the run-specific operator entitlement attestation itself — REMEDIATED IN THIS RECORD

The frozen first-pass record correctly says that a fresh run-specific Coding Plan attestation existed, but the standing reconciliation from the first live trial requires that **every future live run record a fresh operator entitlement attestation specific to that run**. A reviewer statement that an attestation existed is weaker provenance than preserving the operator's actual run-specific statement.

The operator supplied the following attestation before this rerun, and it is preserved here verbatim:

> **Coding Plan:** I attest that, for this live rerun, the account is entitled to use the Z.ai Coding Plan endpoint for this non-coding structured-extraction workload.

This is an account/operator statement for this run only. It is not a claim about Z.ai documentation, other accounts, other workloads, or future runs. It is spent by this rerun. Any later live run requires a new run-specific attestation.

No evidence artifact and no frozen first-pass text is modified by this remediation.

## Findings register

- RRV6-01 — confirmed.
- RRV6-02 — confirmed.
- RRV6-03 — confirmed.
- RRV6-04 — confirmed.
- RRV6-05 — confirmed.
- FRR6-01 — new provenance finding, remediated additively in this record.

No additional blocking or non-blocking evidence-interpretation finding was identified.

## Qualification ceiling

This second review does **not** qualify:

- production extraction quality;
- a semantic accuracy percentage;
- served model/checkpoint identity;
- causal attribution of the observed improvement to prompt v0.4;
- representative latency, throughput, or scale;
- cost;
- production provider/model selection;
- production scheduler/orchestration;
- autonomous canonical mutation or publication.

The evidence supports preservation as bounded live synthetic-corpus evidence only.

## Decision

Fallback second-review result for frozen evidence head `f6608c05f3fbbb1748c156c96613232d000d75ba`:

**PASS as bounded evidence preservation, with RRV6-01..05 confirmed and FRR6-01 remediated additively by preserving the exact run-specific operator attestation above.**

Because this record is a new documentation-only commit, PR #32 must receive successful exact-head CI on the commit containing this record before merge. The JSON, sidecar, and frozen first-pass review must remain byte-identical.
