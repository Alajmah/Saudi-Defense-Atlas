# M4 Extraction Contract Revision — Second Remediation Record

## Protocol

This record remediates the two findings of the later Codex review that landed on frozen head `707afa185d2a716122a12fd4f41d824fd31e85a2` after the seven-item reconciliation and remained valid on `1a0464e61ba9b29ef5ccac64ed9ce244c67a3884`. The first-pass record and the first remediation record are preserved unchanged; this record is additive.

No live corpus rerun has been performed. Gold and the corpus fixture remain byte-identical to `main`.

## Findings and remediation

### CRX2-01 — P2 — abstention prompt contradiction — REMEDIATED

Prompt rule 15 unconditionally required exactly one Evidence record while rule 9 required complete abstention to return all arrays empty. A model obeying rule 15 during abstention would emit an evidence-only envelope and land on a `candidate-boundary` rejection instead of the intended `no-substantive-candidates` path — exactly the ambiguity the first live run's `TRIAL-INSUFFICIENT` case exposed.

Remediation (prompt template `v0.4`, adapter unchanged at `m4-model-trial-v0.3` because boundary logic did not change): rule 15 is now conditional — "When you emit any substantive Entity, Claim, or Event, emit exactly one document-level Evidence record … When you abstain entirely, return all four arrays empty, including evidence." The Evidence record-contract line carries the same condition. The mechanical ordering already matches: convention checks run only on substantive output, so a complete abstention still reaches `no-substantive-candidates`.

Deterministic guards added to `scripts/validate_m4_model_extraction_trial.py`:

- the rendered prompt must contain both conditional-Evidence fragments;
- a complete abstention's failed check set is exactly `{"no-substantive-candidates"}`;
- a model that violates the conditional rule (evidence-only envelope) is rejected diagnosably on the `candidate-boundary` path with pre-clear counts `{"evidence": 1, "entities": 0, "claims": 0, "events": 0}` — the previously opaque shape is now visible from counts alone.

### CRX2-02 — P2 — ROADMAP overclaimed typing enforcement — REMEDIATED

The ROADMAP stated the equipment-versus-variant typing rule was "enforced at the candidate boundary with dedicated rejection checks," but that rule is deliberately prompt-instructed: both `equipment` and `equipment_variant` remain schema-valid and no check rejects either.

Remediation: the ROADMAP bullet now separates mechanically enforced rules (role vocabulary plus participants-shape, exact-numeric bounds, and the Evidence cardinality/locator — the latter explicitly conditional on substantive output) from prompt/evaluator guidance without mechanical enforcement (typing rule, permissions-not-obligations). The trial document's convention list now marks each rule as enforced or prompt-instructed and states the conditional-Evidence behavior.

## Version note

The prompt template changed, so `PROMPT_TEMPLATE_VERSION` bumped `v0.3` → `v0.4` (the fallback-review version-pin validator forced the bump, as designed). `ADAPTER_VERSION` stays `m4-model-trial-v0.3`: the boundary's logic, checks, and diagnostics are unchanged by this remediation; only the instructed text moved. Report version stays `v0.6`.

## Deterministic validation evidence

- Complete repository suite at the remediation commit: all 38 `scripts/validate_*.py` validators — **PASS**, including the new conditional-Evidence wording, abstention-path, and evidence-only diagnosability guards, and the updated template-version pin.
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers `schema-validation` (and `wikibase-verification`) on the same tip.

## Explicitly unverified / unresolved

- Everything previously recorded remains open: no live corpus rerun under the revised contract; typing and permissions-not-obligations remain prompt-instructed; served-model identity, scale, cost, and production-provider selection remain unqualified.
- The next Z.ai live run requires a fresh run-specific operator entitlement attestation.

## Freeze

This record completes remediation of the two late findings. The remediated head awaits the genuinely fresh Codex re-review of the new exact SHA before PR #31 may merge.
