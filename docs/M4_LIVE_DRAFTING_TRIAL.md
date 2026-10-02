# M4 Live Drafting Trial — Driver Contract

## Status

Driver implemented and deterministically validated in CI. No live model call has been made through this driver. The bounded live trial runs only after this driver increment clears independent review.

## Purpose

The driver is the deterministic bridge between the reviewed drafting boundary (adapter v0.8, template v0.2) and the standing Z.ai provider edge (transport already qualified through the extraction trial chain). It exists to produce evidence — not to draft production copy, not to publish, and not to qualify any model.

## Architecture

The driver is a thin, reviewable composition of already-reviewed components:

1. **Fixture** (`tests/fixtures/m4-drafting-trial-v0.1.json`) — approved canonical drafting inputs (entities with official bilingual names, claims with scope and per-claim evidence links, evidence records, and pre-written bilingual unknown statements). Synthetic; not canonical SDA data.
2. **Context builder** (from the drafting service) — validates the fixture into an `ApprovedDraftingContext`.
3. **Input renderer** (from the drafting service) — produces the reviewed v0.2 two-block model input (static instructions + context block + terminology block).
4. **Provider edge** (reused from the extraction runner) — the same `zai_invoker` transport: stdlib HTTPS, env-only credential, fail-closed error handling, shared forbidden-vocabulary discipline.
5. **Draft-run executor** (from the drafting service) — converts the raw model output into a candidate-only `AI bilingual draft run` through the full mechanical acceptance boundary.
6. **Report writer** — captures the structural result with hash provenance and a separate editorial placeholder.

## Evidence standard

The report separates two independent dimensions, per the collaborator's direction:

### Mechanical/structural acceptance (deterministically scored)

- schema validity of the context, the draft run, and the report's embedded artifacts;
- claim-specific support closure with per-claim cited `supports` links;
- exactly-once claim accounting with explicit abstention;
- deterministic unknown reuse (the model selects; the adapter copies the pre-written statements);
- terminology pairing in both directions;
- number grounding against context factual fields only;
- restricted-detail and coordinate rejection in both locales;
- authority preservation (candidate-only, no canonical mutation, no publication);
- raw-output hash, rendered-input hash, context hash, registry hash, and delivery hash all recorded.

### Human editorial assessment (placeholder, no mechanical score)

The report carries an `editorial_assessment` section with `status: pending_human_review`, a `null` score, and a `null` notes field listing the six assessment dimensions: Arabic fluency, English fluency, factual faithfulness of phrasing, bilingual adequacy, terminology quality, and awkward or misleading wording. A mechanically accepted draft can still be editorially poor; a fluent draft cannot override a mechanical rejection. No mechanical editorial score exists in this increment and none is implied.

## Driver report fields

| field | content |
|-------|---------|
| `report_version` | `m4-drafting-live-trial-v0.1` |
| `fixture_version` | drafting fixture version |
| `provider` / `requested_model` | provider-edge trace |
| `provider_edge` | endpoint, credential source, transport, tools, pinned reasoning |
| `drafting_boundary_versions` | drafting adapter, extraction adapter, prompt template id/version/hash |
| `trial_context` | git HEAD, ref, worktree cleanliness, Python version, fixture hash, terminology file hash |
| `invocation` | rendered-input hash, delivery-payload hash, elapsed seconds |
| `structural_result` | the full `AI bilingual draft run` |
| `editorial_assessment` | pending-human-review placeholder with dimensions |
| `qualification` | structural acceptance, editorial unqualified, no production/publication/canonical-mutation, served checkpoint unknown |
| `claim_ceiling` | bounded-evidence-only statement |

## What the driver does not do

- no editorial scoring of any kind;
- no publication;
- no canonical mutation;
- no scheduler, orchestration, or autonomous workflow;
- no retry of semantically rejected drafts;
- no claim about model quality, reliability, scalability, cost, or wrapper effectiveness.

## Claim ceiling

This driver, once reviewed and merged, makes the bounded live drafting trial executable. The trial's first run supports only this claim: a live model can be invoked through the reviewed two-block drafting boundary, and the structural result — accepted or rejected — can be captured with full hash provenance and a separate editorial-review placeholder. Nothing more.
