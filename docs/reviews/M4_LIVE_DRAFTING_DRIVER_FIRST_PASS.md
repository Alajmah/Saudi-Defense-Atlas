# M4 Live Drafting Trial Driver — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the live drafting trial driver increment, performed before any independent second review. It is the deterministic bridge between the reviewed drafting boundary and the standing Z.ai provider edge. No live model call has been made through this driver and no entitlement has been consumed.

## Baseline and review surface

Base branch / merge base:

- `main` at `0d1ab4d76e41d75dcab307b598b7c7b6530f3052` (squash merge of PR #44), verified via `git rev-parse main`.

Implementation baseline reviewed before this review record was added:

- `m4/live-drafting-driver` at the implementation commit recorded with this branch's push.

Net surface:

1. `.github/workflows/schema-validation.yml` (one CI step; suite 41 → 42)
2. `docs/M4_LIVE_DRAFTING_TRIAL.md` (new — the driver contract)
3. `docs/ROADMAP.md`
4. `scripts/run_m4_drafting_trial.py` (new — the live driver)
5. `scripts/validate_m4_drafting_trial_driver.py` (new — the deterministic validator)
6. `tests/fixtures/m4-drafting-trial-v0.1.json` (new — the approved canonical drafting fixture)

Not changed: any service, any existing schema, any existing validator, any preserved evidence artifact, and all frozen review records.

## Architecture: thin composition of reviewed components

The driver is deliberately a thin composition, not a new boundary:

- **Context builder**: the reviewed `build_approved_drafting_context` (adapter v0.8).
- **Input renderer**: the reviewed `prepare_draft_input` (template v0.2, two blocks).
- **Provider edge**: the same `zai_invoker` transport from the extraction runner (already qualified through its own review chain and three live trial series). The driver passes the rendered two-block prompt as the model input string; the transport builds the same OpenAI-compatible request with pinned reasoning.
- **Draft-run executor**: the reviewed `build_bilingual_draft_run`.
- **Report writer**: composes the structural result with provenance and the editorial placeholder.

The only new logic is the fixture loader and the report writer — both simple, both deterministically validated.

## Evidence-standard compliance

The report separates the two dimensions as the collaborator directed:

- **Mechanical/structural acceptance** is embedded as the full `AI bilingual draft run` — every existing gate (schema, support closure, exactly-once, unknown reuse, terminology pairing, number grounding, restricted detail, authority) is enforced by the reviewed boundary, not re-implemented in the driver.
- **Human editorial assessment** is a `pending_human_review` placeholder with the six assessment dimensions listed, a `null` score, and a `null` notes field. The report explicitly states: "A mechanically accepted draft can still be editorially poor; a fluent draft cannot override a mechanical rejection. No mechanical editorial score exists in this increment."

## What the deterministic validator proves

The validator (CI-gated, suite grows to 42) proves without network access:

- the fixture loads and builds a schema-valid approved context;
- the invoker receives exactly the two-block rendered input (spy proof);
- the structural result is a schema-valid accepted `AI bilingual draft run` with exactly-once claim accounting, deterministic unknown reuse, and candidate-only authority;
- the rendered-input, registry, and delivery hashes are correct;
- the terminology file hash and the registry acceptance digest are distinct (they canonicalize different byte forms — a documented property);
- a malformed model output produces a clean schema-valid rejection with the raw-output hash;
- the report version constant is pinned;
- no network call is made.

## Findings during implementation

The fixture initially carried `"validity": null` for the manufacturer claim, which the canonically-typed context schema (from the RBD-03 round) rejects — the canonical `validity_interval` is an object, not nullable. Fixed to carry a `point_in_time` validity before the validator ran green. The fixture now matches the shape the core drafting validator already uses.

## Design notes worth recording

- **Transport reuse.** The driver imports `zai_invoker` from the extraction runner rather than duplicating the provider edge. This is deliberate: the transport is already qualified through its own review chain and three live evidence series, and duplication would create drift risk. The trade-off is a script-to-script dependency; this pattern is already established by the zai provider-edge validator.
- **Reasoning configuration.** The driver uses the same pinned reasoning configuration as the extraction trial (thinking enabled, effort max). No drafting-specific reasoning policy exists; the pin is explicit, recorded in the report, and can be revisited if the live trial shows it is inappropriate for drafting.
- **The fixture is canonical-shaped, not canonical.** It carries proper SDA-* identities, bilingual names, scope, and evidence links, but it is synthetic data for trial purposes. The fixture version (`m4-drafting-trial-v0.1`) is distinct from the extraction corpus version.
- **No retry.** A rejected draft is preserved as evidence; the driver does not retry.

## Deterministic validation evidence

Complete repository suite at the implementation head: **42/42 validators — PASS** (41 prior plus the new drafting-trial-driver validator, CI-gated).

The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- No live model has been invoked through this driver; driver effectiveness, wrapper compliance, and structural acceptance rates with a live model are all unknown until the reviewed trial runs.
- The editorial assessment dimension is structurally a placeholder; filling it is a human-review activity that follows the trial.
- Cost, latency, throughput, and model-version stability remain unqualified.
- The reasoning configuration (thinking enabled, effort max) is pinned for consistency with the extraction evidence base; whether it is appropriate for drafting is a live-trial question.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review.
