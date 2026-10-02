# M4 Terminology-Delivery Implementation — Remediation Record

## Protocol

This record remediates the three findings of the independent review of PR #44 at frozen head `62757fb051181a068524c3b3de94853ffd09aa3d` (primary `5388740899`; fallback `5388746915`, reduced reviewer independence — TDI-03 added during the fallback challenge; Codex quota-blocked via `5946189678`). The frozen maintainer first-pass record is preserved unchanged at blob `94f5a842164dd45b91d3dc398fc357b77fb905b4`. No live model call was made and no entitlement was consumed.

Adapter version stays **v0.8** and template stays **v0.2** — all three findings are documentation, comments, or validator-oracle changes; no executable boundary behavior changed.

## TDI-01 — two whole-input assertions became false — REMEDIATED

The contract's wrapper-isolation section still said every number in the model input comes from the context and every Arabic string in the model input is context data. Both became false when the terminology block entered the input: registry Arabic renderings are now intentionally present, and registry terms may carry digits. Both assertions are now scoped to the **static wrapper**: the wrapper introduces no digits and no Arabic script, while complete-input digits and Arabic may come from the typed data blocks — the context (whose factual fields alone govern the prose allowlist) or the terminology block (whose digits never authorize prose numbers). (Residual round: the first remediation attempt replaced the Arabic assertion but the numeric replacement was lost to a mid-script crash before the file was written — the re-review `5389014732` caught the surviving original numeric claim, and this round corrected it. The earlier version of this section overstated closure by describing both assertions as corrected.)

## TDI-02 — v0.8 descriptions not fully propagated — REMEDIATED

Four living statements still described the superseded bare-context input contract. All corrected: the `build_bilingual_draft_run()` docstring now names the rendered two-block input; the core validator success text names the context block plus terminology delivery block; the isolation validator's comment and success text name the two-block input and the per-term oracle; and the ROADMAP now marks both the bare-context entry and the v0.1/v0.7 wrapper entry as historical baselines superseded by the v0.2/v0.8 terminology-delivery increment, accurate for their heads. (Residual round: the isolation validator's module-level docstring still described the superseded single-context input — the re-review `5389014732` caught it, and this round corrected it. The earlier version of this section treated propagation as complete while that docstring remained stale.)

## TDI-03 — the delivery oracle was not independent — REMEDIATED

Both validators used the production `derive_terminology_delivery_payload()` helper to construct the expected terminology data, so a regression swapping valid categories or Arabic renderings between terms could have evaded the matrix. Both validators now construct the expected `{category, en, ar}` records locally from the loaded registry in registry order — the production helper is no longer imported by either validator — and the comparison is per-term equality of the parsed terminology block against the locally constructed list, not just English-order matching. The core validator also independently reconstructs the canonical delivery bytes from its local oracle for the hash assertion.

## LOW — PR description file count — CORRECTED

The PR description now says seven changed files (the first-pass record being the seventh).

## Deterministic validation evidence

Complete repository suite at the remediation head: **41/41 validators — PASS**, with both drafting validators now carrying the independent per-term delivery oracle alongside the existing two-block recovery, metadata-absence, spy, and digit-allowlist proofs. The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

### TDI-01R / TDI-02R — residual wording sites — REMEDIATED (residual round)

The re-review (`5389014732`, fallback `5389018104`) found the TDI-01 numeric correction was never written to disk (a mid-script crash lost it) and the isolation module docstring still carried the superseded single-context description. Both corrected in this round; the sections above now carry residual-round notes owning the earlier overstatement. LOW metadata: the PR description now says eight files (this record being the eighth).

## Explicitly unverified / unresolved

Wrapper and terminology effectiveness remain unknown and unclaimed until the reviewed bounded live drafting trial. The design's live-trial gate stands.

## Freeze

This record completes remediation of TDI-01 through TDI-03. The remediated head awaits exact-head CI and re-review.
