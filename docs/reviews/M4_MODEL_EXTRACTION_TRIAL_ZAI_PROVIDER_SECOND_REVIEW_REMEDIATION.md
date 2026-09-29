# M4 Z.ai Trial Provider Edge — Second-Review Remediation Record

## Protocol

This record remediates the findings of the independent second review (Codex, via PR #29 "M4: add Z.ai local real-model trial provider edge", reviewed head `8f2bf1d2566b6ff7f964bdc736232a84fb47e833`) plus two adversarial hardening requirements added by the independent maintainer-side reviewer. Codex had been asked to address the feedback but produced no remediation commit; this remediation was implemented by the maintainer (ZCode) against the five accepted findings. Frozen records are not rewritten.

No live Z.ai request was made. No model credits were consumed. The provider-independent boundary, authority semantics, and synthetic-only restriction are unchanged: `services/intelligence/model_extraction_trial.py` remains byte-identical to `main`.

## Baselines

- Second-reviewed head (PR #29 pin): `8f2bf1d2566b6ff7f964bdc736232a84fb47e833`.
- Remediation implementation commit: `84231207fc196c822554a6ee38908ce83add4526`.
- This record's commit is the branch tip at freeze; the post-record SHA is reported out-of-band with the push, per the established exact-head protocol.

## Finding-by-finding remediation

### CS-01 (Codex P2) — linked worktrees — REMEDIATED

`read_git_head()` now follows the `commondir` file: when the runner executes in a linked worktree, refs are looked up in the per-worktree admin directory first and then in the shared common directory, where branch refs actually live; the packed-refs fallback checks both directories as well. Previously the lookup only consulted the per-worktree admin directory, so a linked worktree failed provenance collection (fail-closed) because its branch ref lives in the common dir. Regression coverage: a synthetic linked-worktree layout (`.git` file → worktree admin dir → `commondir` → main git dir) resolves both a loose ref and a packed ref from the common directory.

### CS-02 (Codex P2) — endpoint trace ambiguity — REMEDIATED

`provider_edge.endpoint_mode` is now derived from the actually resolved URL rather than copied from the `--zai-endpoint` argument, so it can no longer record a losing selection when `--base-url` or `ZAI_BASE_URL` wins. Additionally, an explicit `--zai-endpoint` that contradicts the resolved route fails closed before any request exists. Regression coverage: an environment URL overriding a contradicting endpoint flag fails closed with zero transport calls, and a run resolved through the environment records the derived mode `prepaid`.

### CS-03 (Codex P2) — Windows report hashing — REMEDIATED

The report and its sidecar are now written with `write_bytes`, and the report digest is computed from the bytes read back from disk rather than the pre-write string. Previously `write_text` could translate LF to CRLF on Windows while the sidecar hashed the LF form, so the sidecar did not hash the actual file. Regression coverage: the validator now asserts the on-disk report bytes contain no CRLF and that the sidecar digest equals the SHA-256 of the exact bytes read from disk. The prior validator gap — hashing the in-memory string instead of the file — is corrected in the same test.

### CS-04 (hardening) — exact-route overrides — REMEDIATED

`validate_zai_base_url()` accepts only the two exact documented Z.ai base routes as credential destinations; near-miss paths on the official host (trailing slash, different version, extra segments, bare `/api`) are rejected. Regression coverage: four near-miss URLs on `api.z.ai` are added to the rejection matrix alongside the existing arbitrary-host, port, scheme, userinfo, query, and fragment cases.

### CS-05 (hardening) — non-ASCII credential characters — REMEDIATED

`require_zai_api_key()` now rejects any credential containing characters outside printable ASCII (in addition to the existing control, whitespace, quote, and backslash rejection). A malformed non-ASCII key therefore can never reach a header encoding or an escaped exception message where partial disclosure could occur. Regression coverage: two non-ASCII credential shapes (Latin-1 and Cyrillic) are added to the ingestion-rejection matrix.

## Documentation

The trial document now states the exact-route override rule, the contradiction fail-closed, the non-ASCII credential rejection, and an entitlement note for the live run: this workload is structured extraction rather than a coding scenario, and Z.ai documents the Coding Plan endpoint for coding scenarios, so the general OpenAI-compatible route (`--zai-endpoint prepaid`) is the clean choice for the live trial unless Z.ai explicitly permits this workload under the Coding Plan.

## Deterministic validation evidence

- Complete repository suite at the remediation implementation commit `84231207fc196c822554a6ee38908ce83add4526`: all 38 `scripts/validate_*.py` validators — **PASS**, including the extended Z.ai provider-edge validator (commndir/packed-refs resolution, derived endpoint mode with contradiction guard, byte-exact report hashing, exact-route and non-ASCII rejections).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` on the same exact tip.
- No network call and no model credit was consumed by any validation run.

## Explicitly unverified / unresolved

- All prior open items remain: account type and permitted workload scope (operator states it by selecting the route at live time); wire acceptance of the pinned `thinking`/`reasoning_effort` fields; served model, usage, latency, cost, and quality until the reviewed live trial; socket-level versus wall-clock timeout asymmetry.
- The deployment decision — which endpoint the live trial uses — is recorded as guidance in the trial document but remains the operator's call at execution time.

## Freeze

This record completes the remediation of the second-review findings against PR #29's reviewed head. The branch tip (this record's commit), the out-of-band post-record SHA, and both exact-head validation results constitute the remediation baseline. The live GLM-5.3 trial remains blocked until the second reviewer accepts this remediation.
