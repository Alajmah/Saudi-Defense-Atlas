# M4 Z.ai Live Trial — Second-Review Reconciliation

## Protocol

This record reconciles the independent second review (Codex, plus maintainer-side adversarial verification) of the preserved live-trial evidence at frozen head `0bdf9229dde4aa8de528eeccad305c5e72ffb7f2` (PR #30). The frozen first-pass record (`docs/reviews/M4_ZAI_LIVE_TRIAL_FIRST_PASS.md`) is preserved unchanged as the pre-Codex baseline; all corrections below are additive and supersede the first-pass interpretation where stated.

The remediation is documentation-only: this record, `docs/ROADMAP.md`, and `docs/M4_MODEL_EXTRACTION_TRIAL.md`. The evidence JSON, its SHA-256 sidecar, the `.gitattributes` preservation guard, and the frozen first-pass record are unchanged.

## Findings register

### C2R-01 — Codex P1 — entitlement provenance was missing from repository evidence

The live report used the Coding Plan endpoint, while the provider reconciliation treats workload entitlement as an operator fact and the live-evidence gate requires an endpoint for which the operator holds valid entitlement. The evidence artifact carried no record of that operator fact.

Remediated here by the account-specific operator attestation below. The attestation is an operator statement about one account; it is not a claim about Z.ai documentation, other accounts, or the Coding Plan in general.

### C2R-02 — Codex P1 — unsupported Event roles are downstream incompatibilities, not vocabulary variation

This corrects the first-pass interpretation of `TRIAL-EN-DELIVERY`, `TRIAL-AR-CONTRACT`, and `TRIAL-PROMPT-INJECTION`. The roles `deliverer`, `signatory`, and `conducting organization` are not merely harmless exact-gold mismatches:

- the canonical Event schema (`schemas/v0.1/event.schema.json`) enumerates the participant-role vocabulary: `buyer`, `seller`, `contractor`, `operator`, `recipient`, `manufacturer`, `host`, `participant`, `observer`, `supplier`, `other`;
- the Resolver/Verifier (`services/intelligence/_resolver_verifier_core.py`, `_EVENT_ROLES`) enforces exactly that set and raises `ResolverVerifierError` on any other role;
- the candidate Event schema (`schemas/v0.1/ai-extraction-run.schema.json`) currently permits any non-empty string of up to 128 characters for a candidate participant role.

Consequence: the three accepted live runs carrying out-of-vocabulary roles would fail the downstream Resolver/Verifier boundary. The live evidence therefore does **not** demonstrate that real-model candidates preserve the entire M4 downstream path. Downstream Resolver/Verifier preservation is currently not demonstrated.

This also refines first-pass finding LTR-02: the Event-role vocabulary is not absent from SDA — it already exists canonically. The defect is that the candidate schema and prompt permit arbitrary role strings instead of exposing and enforcing the existing downstream vocabulary. The other LTR-02 items (exact-numeric-bound convention, equipment-versus-variant typing, Evidence cardinality) remain genuine under-specifications.

### C2R-03 — Codex P2 — served model identity remains unknown

The artifact proves a Z.ai provider request configured with `requested_model = glm-5.3`; `provider_checkpoint_version` is `null` and the API response metadata is intentionally not persisted. The evidence therefore does not prove the provider served an identifiable GLM-5.3 checkpoint.

Qualification wording for this trial is: **"a Z.ai provider request configured with requested model `glm-5.3`"**. Served-model and checkpoint identity remain UNKNOWN.

### C2R-04 — Codex P2 — roadmap status was stale

`docs/ROADMAP.md` still stated that no live real-model trial report had been reviewed and still listed executing/reviewing the trial as future work. Updated in this remediation.

### C2R-05 — maintainer verification P2 — trial document was stale

`docs/M4_MODEL_EXTRACTION_TRIAL.md` still stated that live model evidence is not qualified until a report is executed and reviewed, and "Until that report exists, …". Updated in this remediation.

## Operator entitlement attestation

Recorded on 2026-09-30, restating an operator decision made before execution on 2026-09-29:

- the operator (account holder) cleared the entitlement gate for the live trial and directed use of the Coding Plan endpoint (`https://api.z.ai/api/coding/paas/v4`) for this structured-extraction workload on this account;
- the attestation is specific to that account and that decision; Z.ai public documentation describes the Coding Plan endpoint as serving coding scenarios, and nothing in this repository claims otherwise;
- every future live run must record a fresh operator entitlement attestation specific to that run; any change to the account, endpoint, or workload invalidates prior attestation and must be called out explicitly.

## Precise post-remediation status

Live provider mechanics and sensitivity gating are evidenced. Extraction quality remains unqualified. Downstream Resolver/Verifier preservation is currently not demonstrated because three accepted candidates carry unsupported roles. Served model checkpoint is unknown. Scale, cost, production-provider selection, bilingual drafting, and observability remain open.

## Evidence integrity confirmation

The preserved evidence is unchanged by this documentation-only remediation: `docs/evidence/m4/2026-09-29/m4-zai-live-trial.json` retains committed-blob SHA-256 `0986279bc9812d34debffe28ff019fa87a7a342d18ae31144d2ac971539a9804`, matching the sidecar committed beside it.

## Gate

This reconciliation is complete pending a fresh Codex re-review of the remediated exact head. PR #30 must not merge before that clean re-review and reconciliation closure.
