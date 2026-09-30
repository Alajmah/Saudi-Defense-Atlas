# M4 Downstream-Preservation Replay — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the downstream-preservation replay increment, performed before any independent second review.

## Baseline and review surface

Base branch / merge base:

- `main` at `bcf52a821850b38e285bc5beaa9d9de0b9de53e0` (squash merge of PR #36), verified via `git rev-parse main`.

Implementation baseline reviewed before this review record was added:

- `m4/downstream-preservation-replay` at the implementation commit recorded with this branch's push (the commit preceding this record).

Net surface:

1. `.github/workflows/schema-validation.yml` (one CI step)
2. `docs/M4_DOWNSTREAM_PRESERVATION_REPLAY.md` (new)
3. `docs/ROADMAP.md`
4. `scripts/validate_m4_downstream_replay.py` (new — the replay validator)
5. `services/intelligence/_resolver_verifier_core.py` (one predicate-signature line plus its comment)

Not changed: the corpus fixture and gold, the preserved evidence bytes, the prompt and extraction boundary, the editorial packet/decision-binding services, and all frozen review records.

## What the increment delivers

### Resolver signature reconciliation

`_ENTITY_PREDICATES["manufacturer.manufactures.equipment"]` now accepts `equipment_variant` targets alongside `equipment`. This resolves the incompatibility the PR #36 review surfaced: the M1 F-15SA proposal and the merged designation-typing convention both point the predicate at variants, while the resolver previously restricted the target to family-level `equipment` and would have raised on a correctly typed claim. No existing validator pinned the old restriction — all three resolver-dependent validators pass unchanged after the fix.

### The replay validator

`scripts/validate_m4_downstream_replay.py` loads the preserved v0.7 evidence, gates on its sidecar digest, and replays it offline through the real Resolver/Verifier, review-packet builder, and decision-binding builder. It asserts: rejection isolation for the abstained run; per-claim outcomes recorded honestly (the quantity claim blocked by corroboration policy; the actual mistyped Falcon-X claim blocked_unresolved); AMBER-only proposals with human-review-required policy outcomes; schema-valid packets, decisions, and bindings with Document provenance preserved; and zero canonical-mutation/publication authority, with no canonical backend imported or invoked anywhere in the script.

### The corrected-typing regression

Per the PR #36 obligation, the replay does not evade the variant-target question: it asserts both that the actual v0.7 delivery claim fails to resolve (the honest consequence of the model's `equipment` typing) and that the same run corrected per the merged designation convention resolves, with the manufacturer claim surviving as outcome `new` and carried in the AMBER proposal's mutations. The regression lives in the replay validator rather than the resolver-validator fixture deliberately — it proves survival against the actual preserved live-trial artifacts, not only a synthetic fixture, and it runs in CI on every push.

## Findings during implementation

1. An invented `notes` field on the replay's review decision failed schema validation (`additionalProperties: false`); replaced with the schema's `rationale`/`policy_references` shape used by the multi-source slice. Caught by the replay itself.
2. A syntax typo (`SIDE CAR_DIGEST`) was caught by the interpreter before any run. Neither left the machine.

## Design notes worth recording

- The replay's canonical registry is typed per the merged annotation conventions, with Falcon-X as `equipment_variant`. Because the resolver matches entities by exact name **and type equality**, the model's mistyped candidate lands as `unresolved` rather than matching — which is precisely the honest downstream consequence the replay is required to show.
- The replay stops at the decision binding. Canonical execution is intentionally not exercised: this increment proves preservation through the human-review boundary, and the existing multi-source slice already proves execution with a fixture backend under review authority.

## Deterministic validation evidence

- Complete repository suite at the implementation head: all 39 `scripts/validate_*.py` validators — **PASS** (38 prior plus the new replay validator, which is also added to `schema-validation` CI).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- The replay proves preservation on the synthetic corpus only; it is not a production qualification, an extraction-quality measurement, or a canonical execution.
- The resolver's quantity-corroboration policy blocks quantity claims downstream by design; whether that policy should evolve so quantity extractions can reach review is a separate, independently scoped question.
- Fixed-configuration live repeatability trials remain sequenced after this increment merges and passes review.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review.
