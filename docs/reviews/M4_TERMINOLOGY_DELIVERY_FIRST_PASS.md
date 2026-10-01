# M4 Terminology Registry Delivery Design — Maintainer First Pass

## Review protocol

Independent maintainer first-pass review of the terminology-registry delivery design, performed before Codex or fallback reconciliation. This review is frozen at the reviewed design head and must not be retroactively rewritten after remediation or second-review input.

No live model call was made and no entitlement was consumed.

## Reviewed baseline

- base: `main@c7ff095bc3e54c9b8d3b6a192d971f722b9cd21f`
- design head reviewed: `203184221b42af8d1aa264bd62a6fa2cf2b7fd77`
- reviewed artifact: `docs/M4_BILINGUAL_DRAFTING_TERMINOLOGY_DELIVERY_DESIGN.md`
- scope: deterministic terminology-delivery design only; no adapter/template/schema implementation yet

## Frozen findings

### TRD-01 — Digest wording overstates the current bound surface — MEDIUM

**Finding.** The design repeatedly describes `context.terminology_sha256` as binding the “full source registry.” The current adapter does not hash the raw registry file. `load_terminology()` projects the registry to `{version, terms}`, and `terminology_digest()` hashes that acceptance payload. The registry file's top-level descriptive `scope` field is not part of the digest.

**Evidence.** Current v0.7 code returns only `version` and `terms` from `load_terminology()` and computes `terminology_digest()` over exactly those two fields.

**Why it matters.** The terminology-delivery increment is specifically about auditable input provenance. Calling the existing hash a full-source-registry hash would make the audit claim broader than the implementation.

**Required remediation.** Use precise terminology throughout: “validated registry acceptance payload (`version` + full term records)” or equivalent. State explicitly that top-level descriptive `scope` is neither delivered nor digest-bound under the existing v0.1 registry contract.

**Confidence:** high.

### TRD-02 — Entity-name precedence is asserted but not mechanically protected against registry collision — MEDIUM

**Finding.** The design correctly states that official bilingual Entity names from `ApprovedDraftingContext` outrank terminology, and invariant 13 says the terminology payload cannot override them. But the proposed mechanics contain only prompt hierarchy plus human review; there is no deterministic cross-check for a registry lexical pair that collides with a context Entity name.

**Why it matters.** The registry is explicitly non-entity terminology. A future term whose English or Arabic rendering equals an official Entity name could create a second model-visible translation for a context-owned name. Prompt precedence is useful but is not the mechanical invariant the design text claims.

**Required remediation.** Add a pre-invocation registry/context collision gate. At minimum, fail closed when any delivered registry rendering exactly matches (English case-insensitive; Arabic exact) an official context Entity name. Do not attempt fuzzy/substring matching in this increment. Reframe the invariant to the exact collision guarantee plus prompt/human-review precedence for broader semantic cases.

**Confidence:** high.

### TRD-03 — Renderer ownership/binding is underspecified — MEDIUM

**Finding.** The design defines the delivery payload but does not freeze the API boundary that constructs the complete model input. The current `render_draft_prompt(context)` accepts only context. Without an explicit replacement contract, an implementation could render registry bytes from a global, stale, or separately loaded source after the adapter's digest check.

**Why it matters.** The exact bytes sent to the model are the object under review. Registry validation, digest matching, delivery projection, and rendering must be one deterministic dataflow rather than adjacent assumptions.

**Required remediation.** Specify that the renderer takes both `context` and the registry/terminology input (or an already validated registry object), derives the lexical payload itself, verifies registry version + digest against the context before substitution, and returns the complete rendered string. `build_bilingual_draft_run()` must invoke that path; there is no global/default registry and no caller-supplied pre-rendered terminology block.

**Confidence:** high.

### TRD-04 — Proposed terminology sensitivity gate misses the wrapper-only operational vocabulary — HIGH

**Finding.** The design says delivered renderings will be checked with “the same restricted-marker and coordinate-like rules used for drafting eligibility.” That older eligibility set does not include the four operational-domain terms introduced by PW-01 (`availability`, `posture`, `movement`, `coordinate`/`coordinates`). Those terms live in `WRAPPER_FORBIDDEN_VOCABULARY`, not `RESTRICTED_MARKERS_EN`.

**Why it matters.** A future terminology entry containing one of those words could enter the model through the new terminology block even though PR #42 deliberately prohibited the static wrapper from carrying them. The new delivery path would therefore reopen the exact lexical-priming surface PW-01 closed.

**Required remediation.** The terminology-delivery gate must reject the complete pinned model-input-forbidden vocabulary, not only the older factual restricted markers, plus the existing coordinate-like numeric pattern. The implementation should centralize or explicitly compose the vocabulary so wrapper and terminology delivery cannot drift silently.

**Confidence:** high.

## Clean areas

- A separate typed TERMINOLOGY data block is cleaner than embedding terms into `ApprovedDraftingContext`; it preserves the factual-context / lexical-guidance distinction.
- A least-privilege projection containing only bilingual lexical pairs is preferable to sending raw registry metadata.
- Avoiding heuristic “relevant term” selection is correct while the registry lacks machine-readable applicability metadata.
- Separate source-registry and delivery-payload hashes are useful and should remain distinct.
- `rendered_input_sha256` remains the correct whole-input binding and run-identity input.
- Keeping the factual-number allowlist context-only correctly prevents terminology bookkeeping/lexical digits from authorizing prose numbers.
- No context-schema authority expansion is needed.
- No live call is justified by this design review.

## Open questions

1. Whether exact Entity-name collision should reject a term even when both English and Arabic renderings happen to equal the Entity's official pair. First-pass preference: reject any exact collision because the registry is defined as non-entity terminology and has no need to duplicate Entity names.
2. Whether the run trace needs both `terminology_registry_sha256` and `terminology_delivery_sha256`. First-pass conclusion: yes; they bind different artifacts and make the model-input trace auditable without conflating source acceptance with delivery projection.

## First-pass verdict

**BLOCKED pending TRD-01 through TRD-04 remediation.**

This state is frozen before any Codex/fallback review. Do not retroactively edit it after remediation.
