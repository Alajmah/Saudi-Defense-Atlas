# M4 Terminology-Delivery Implementation — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the terminology-delivery implementation increment, performed before any independent second review. It implements the reviewed design contract (`docs/M4_BILINGUAL_DRAFTING_TERMINOLOGY_DELIVERY_DESIGN.md`, merged via PR #43) exactly. No live model call was made and no entitlement was consumed.

## Baseline and review surface

Base branch / merge base:

- `main` at `662bdba1a8b5782e50e07a282766caecb6c278c5` (squash merge of PR #43), verified via `git rev-parse main`.

Implementation baseline reviewed before this review record was added:

- `m4/terminology-delivery-implementation` at the implementation commit recorded with this branch's push.

Net surface:

1. `docs/M4_BILINGUAL_DRAFTING_CONTRACT.md` (model-input section; open question resolved)
2. `docs/ROADMAP.md`
3. `schemas/v0.1/ai-bilingual-draft-run.schema.json` (`prompt_trace` gains the two terminology hashes)
4. `scripts/validate_m4_bilingual_drafting.py` (two-block proofs; the design's delivery matrix)
5. `scripts/validate_m4_bilingual_drafting_isolation.py` (two-block recovery; metadata absence; static-segment properties)
6. `services/intelligence/bilingual_drafting.py` (template v0.2, adapter v0.8, renderer pipeline, gates)

Not changed: the context schema (the design required no change), the terminology registry file, every preserved evidence artifact, and all frozen review records.

## Implementation against the design's seventeen invariants

1. **One context token, one terminology token, fixed order** — asserted in `prepare_draft_input` (counts and index order) and by the template property checks.
2. **Round-trip context bytes** — `split_rendered_prompt` recovers the canonical context; validators recompute independently.
3. **Round-trip terminology bytes** — same split recovers the delivery payload verbatim; both validators reconstruct it independently.
4. **Payload derived only from a validated registry, only `category`/`en`/`ar`** — `derive_terminology_delivery_payload` projects from the `load_terminology` acceptance payload; the isolation validator asserts `version` and `term_id` never appear in the rendered block.
5. **Frozen category vocabulary** — `load_terminology` rejects any category outside the four; the unknown-category case is a load-time, pre-invocation failure.
6. **Version and digest match the context before rendering** — `prepare_draft_input` verifies both; three same-version mutation cases (English rendering, Arabic rendering, category) are spy-proven to fail before invocation.
7. **`terminology_registry_sha256 == context.terminology_sha256`** — the prompt trace copies the binding; asserted.
8. **`terminology_delivery_sha256` over the delivered bytes** — asserted against the validator's own reconstruction.
9. **`rendered_input_sha256` over the exact invoker string** — asserted against the captured prompt.
10. **Same-version mutation refused** — the three mutation spy cases above.
11. **Every delivered string scanned against the shared vocabulary and coordinate pattern** — the delivery gate walks `category`, `en`, and `ar` uniformly; restricted English, restricted Arabic, PW-01-only (`availability`), coordinate-like, and forbidden-category-text cases all fail before invocation (the forbidden-category case may fail at load first, which the design permits; the scan covers the field by construction because it walks all three fields uniformly).
12. **Static wrapper free of renderings, Arabic, digits, context strings, forbidden vocabulary** — the static segments (`before + mid + after`) are checked for all of these; renderings appear only inside the terminology block.
13. **Terminology digits never authorize prose numbers** — a digit-bearing registry term (`Block 2026 system`) passes its own gates, binds a valid context, and prose citing `2026` is still rejected as ungrounded: the allowlist remains context-factual-fields only.
14. **Exact registry/Entity-name collisions refused** — English case-insensitive and Arabic exact cases both fail before invocation; broader Entity-name precedence remains a prompt-and-review rule.
15. **Renderer accepts the registry explicitly and derives the payload internally** — `prepare_draft_input` is the single path; `build_bilingual_draft_run` uses it; there is no pre-rendered terminology parameter.
16. **Categories are lexical qualifiers only** — the template states an entry never authorizes mentioning its concept, never asserts applicability, and never overrides official entity names.
17. **Candidate-only authority** — unchanged and asserted.

## Design decisions recorded during implementation

- **Load-time vs. delivery-time rejection.** The frozen-category check lives in `load_terminology`, so a registry with an unapproved category fails at load — earlier than the delivery gate. The design anticipated this ("the bounded-category check may reject first"). The shared scan still walks `category` alongside `en`/`ar` uniformly, so the scan's coverage of the category field is by construction rather than by a dedicated passing case; the validator matrix records this honestly by routing load-time rejections through the original context.
- **Split disambiguation.** `split_rendered_prompt` splits the inner body on the static `mid` segment (`CONTEXT END … TERMINOLOGY BEGIN`). A pathological context or registry string containing that literal would break the split; the validators' independent reconstruction makes any such collision visible. The design's byte-recovery invariants are asserted, not assumed.
- **Version discipline.** Template v0.1 → v0.2 and adapter v0.7 → v0.8, per the design; the invoker input changed, so both identities moved.

## Deterministic validation evidence

- Complete repository suite at the implementation head: **41/41 validators — PASS**, with the two drafting validators now carrying the two-block proofs and the design's delivery matrix (three same-version mutations, unknown category, five forbidden-vocabulary/coordinate renderings, two Entity-name collisions, the digit-bearing-registry allowlist case, registry-metadata absence, static-segment rendering absence — each pre-invocation case spy-proven to fail before the invoker is called).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- No live model has seen the two-block input; wrapper and terminology effectiveness remain unknown and unclaimed until the reviewed bounded live drafting trial.
- The design's live-trial gate stands: the implementation must clear independent review before the trial consumes the standing entitlement.
- No relevance filtering exists (per the design); every validated registry term is delivered for every context.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review.
