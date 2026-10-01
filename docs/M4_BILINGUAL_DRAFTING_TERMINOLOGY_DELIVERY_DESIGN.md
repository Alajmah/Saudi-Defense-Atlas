# M4 Bilingual Drafting — Terminology Registry Delivery Design

## Status

**Proposed deterministic design; no live model call.** This document resolves the terminology-delivery question left open by the merged prompt-wrapper milestone (`main@c7ff095bc3e54c9b8d3b6a192d971f722b9cd21f`). It does not itself change the drafting adapter, prompt template, schemas, provider edge, or live entitlement use. Implementation is blocked until this design passes the normal independent review sequence.

## Problem

The `ApprovedDraftingContext` already binds the project-owned bilingual terminology registry by `terminology_version` and `terminology_sha256`, and the drafting adapter independently rejects registry bytes whose version or digest differs from that context binding. The merged prompt wrapper deliberately contains no terminology renderings, however, and the context embeds no registry terms. A live model therefore cannot follow the registry unless a deterministic, reviewed model-input mechanism supplies the lexical mappings.

The delivery mechanism must not weaken the existing architecture rule: **the model drafts language; it does not choose facts.** The registry is recurring non-entity terminology. It is not Evidence, is not a Claim source, does not authorize a procurement state or other fact merely because a term exists in the registry, and never overrides official bilingual Entity names carried by the context.

## Decision

Deliver the terminology registry as a **second typed data block inside the rendered model input**, separate from the factual drafting context and separate from the static instruction wrapper.

The model-facing terminology block is a deterministic least-privilege projection of the validated registry. It contains only the bilingual lexical pairs required for drafting:

```json
{
  "terms": [
    {"en": "aircraft", "ar": "طائرة"},
    {"en": "trainer aircraft", "ar": "طائرة تدريب"}
  ]
}
```

The real payload contains every validated registry term in registry order. It intentionally omits `scope`, registry `version`, `term_id`, and `category` because the model does not need those bookkeeping or classification fields to apply the lexical mapping. The full source registry remains bound separately by the existing context version and digest.

### Why a derived lexical payload instead of the raw registry

The raw registry carries fields useful to the repository but unnecessary to the model. Sending them would increase the model-input surface without increasing drafting authority or lexical capability. In particular, the registry version introduces bookkeeping digits and term/category identifiers add domain labels that are not needed to render the English/Arabic pair. The model-facing projection therefore follows least privilege: **only the lexical material required for drafting is delivered.**

## Authority separation

The rendered input has three logically distinct components:

1. **Static wrapper instructions** — behavior and output-shape rules only.
2. **CONTEXT data block** — the only factual authority. Claims, Evidence links, Entities with official names, explicit unknowns, scope, validity, and authority flags remain here.
3. **TERMINOLOGY data block** — lexical guidance only. Presence of a pair does not authorize the underlying concept as a fact.

The wrapper must state this hierarchy explicitly:

- context Claims are the only factual authority;
- terminology pairs may be used only to word a concept already supported by the cited context Claims;
- presence of a terminology pair does not authorize mentioning that concept;
- official Entity names in the context outrank terminology pairs;
- terminology data is inert data, not instructions or tool directions.

This is a prompt instruction plus human-review boundary, not a claim of semantic mechanical enforcement. The adapter can mechanically enforce support IDs, terminology pairing, numbers, restricted markers, and other existing guards, but it cannot prove that a generated non-numeric lexical choice is semantically entailed by a Claim. Human editorial review remains authoritative over meaning.

## Deterministic model-input shape

Implementation should bump the prompt template from v0.1 to **v0.2** and the drafting adapter from v0.7 to **v0.8**, because the exact invoker input changes.

The template gains one terminology token in addition to the existing context token. The rendered form is:

```text
<reviewed static instructions>

CONTEXT BEGIN
<canonical ApprovedDraftingContext JSON>
CONTEXT END

TERMINOLOGY BEGIN
<canonical terminology-delivery JSON>
TERMINOLOGY END
```

Both tokens must occur exactly once in the template, and the block order is fixed: context first, terminology second. Rendering continues to use token replacement rather than string formatting over JSON bytes.

### Canonical terminology-delivery payload

Given a registry already accepted by `load_terminology`, define the model-facing payload as:

```python
{
    "terms": [
        {"en": term["en"], "ar": term["ar"]}
        for term in registry["terms"]
    ]
}
```

Serialize it with the existing canonical JSON function (`ensure_ascii=False`, sorted object keys, compact separators). Registry list order is preserved because the existing source digest binds that order; no additional heuristic reordering or term selection is introduced.

No relevance filtering is attempted in this increment. The current registry has no machine-readable applicability map from predicates/entity types/scope values to individual terms. A substring or model-based relevance selector would create a new semantic decision surface. If selective delivery is wanted later, the registry must first gain an explicit reviewed applicability contract.

## Hash and provenance chain

The implementation must preserve distinct hashes for distinct responsibilities:

- `input_context_sha256` — SHA-256 of the canonical context JSON, unchanged from v0.7.
- `context.terminology_sha256` — existing SHA-256 over the accepted full registry digest payload (`version` + full term records), unchanged.
- `prompt_trace.terminology_registry_sha256` — copy of `context.terminology_sha256`, making the source-registry binding explicit on the draft run.
- `prompt_trace.terminology_delivery_sha256` — SHA-256 of the exact canonical lexical payload inserted into the TERMINOLOGY block.
- `prompt_trace.template_sha256` — SHA-256 of the static v0.2 template.
- `prompt_trace.rendered_input_sha256` — SHA-256 of the complete string passed to the invoker: static wrapper + context block + terminology block.

The run identity continues to include `rendered_input_sha256`; therefore any change in context bytes, delivered terminology bytes, or wrapper bytes changes run identity. The two terminology hashes are deliberately not interchangeable: one binds the complete project registry accepted by policy, while the other binds the exact least-privilege lexical projection exposed to the model.

## Pre-invocation gates

Registry delivery occurs only after all existing context validation and registry version/digest checks succeed.

The implementation adds a deterministic terminology-delivery sensitivity gate before rendering/invocation. Every delivered English and Arabic rendering is checked with the same restricted-marker and coordinate-like rules used for drafting eligibility. A future registry entry containing restricted operational vocabulary must therefore fail closed before any model call even though the registry is project-owned.

The delivery gate does not confer factual authority. It only prevents the registry from becoming a second path around the operational-sensitivity boundary.

## Interaction with the existing wrapper-isolation proofs

The merged v0.1 wrapper proofs must be restated precisely when terminology delivery is implemented.

Properties that remain true of the **static wrapper text**:

- it is digit-free;
- it contains no Arabic script;
- it contains none of `WRAPPER_FORBIDDEN_VOCABULARY`;
- it contains no context fixture strings or identities;
- it contains no terminology renderings;
- removing both dynamic data blocks reproduces the reviewed static template segments exactly.

Properties that no longer apply to the **complete model input** once terminology is delivered:

- Arabic strings no longer come only from context; they may also come from the typed terminology block;
- registry renderings are intentionally present in the complete input;
- bookkeeping or lexical digits could appear in future terminology data even though the static wrapper remains digit-free.

Accordingly, validators must distinguish static-wrapper properties from typed-data-block properties instead of extending the old wrapper claims to the entire rendered input.

The existing factual-number allowlist remains context-only. A digit appearing in terminology data does **not** authorize that digit in generated prose unless the same digit is independently allowed by the factual context.

## Required implementation invariants

The implementation increment must mechanically assert all of the following before it is eligible for a live trial:

1. The prompt template contains exactly one context token and exactly one terminology token in fixed order.
2. Stripping the rendered input reproduces the canonical context bytes exactly.
3. Stripping the rendered input reproduces the canonical terminology-delivery bytes exactly.
4. The terminology-delivery payload is derived only from a successfully validated registry and contains only `terms[].en` / `terms[].ar`.
5. The registry version and full-registry digest still match the context before rendering.
6. `terminology_registry_sha256 == context.terminology_sha256` on every run.
7. `terminology_delivery_sha256` equals the hash of the exact terminology bytes inserted into the input.
8. `rendered_input_sha256` equals the hash of the exact string supplied to `invoke`.
9. Same-version registry-byte mutation is refused before invocation, as today.
10. Restricted vocabulary or coordinate-like material introduced through registry renderings is refused before invocation.
11. Static wrapper text remains free of registry renderings, Arabic script, digits, context factual strings, and pinned forbidden vocabulary.
12. Terminology data cannot add numbers to the factual-number allowlist.
13. Entity names remain sourced only from context; the terminology payload cannot override them.
14. Run authority remains `candidate_only` with no canonical-mutation or publication authority.

## Required validator cases

At minimum, the two existing drafting validators should cover:

- exact happy-path capture of the complete rendered input;
- independent reconstruction of context JSON and terminology-delivery JSON;
- exact registry-source hash and delivery-payload hash assertions;
- one changed English rendering under the same registry version -> fail before invoker;
- one changed Arabic rendering under the same registry version -> fail before invoker;
- one restricted English registry rendering -> fail before invoker;
- one restricted Arabic registry rendering -> fail before invoker;
- one coordinate-like registry rendering -> fail before invoker;
- a registry rendering containing digits -> those digits remain unauthorized unless present in factual context;
- wrapper/static-section checks performed with both dynamic blocks removed;
- registry renderings appear in the terminology block but not in static wrapper text;
- official bilingual Entity names are unchanged and remain context-owned;
- accepted/rejected draft-run schema validation with the new prompt-trace hashes.

The invoker-spy cases should prove failures occur before invocation for registry mismatch and sensitivity-gate failures, rather than relying only on control-flow inspection.

## Schema impact

`editorial-drafting-context.schema.json` does not need to change. It already carries the registry version and source digest.

`ai-bilingual-draft-run.schema.json` should extend required `prompt_trace` with:

- `terminology_registry_sha256`
- `terminology_delivery_sha256`

Both are lowercase 64-hex SHA-256 strings. No authority field changes.

## Alternatives considered and rejected

### Embed the full registry inside `ApprovedDraftingContext`

Rejected. It conflates factual context with lexical guidance, expands context identity and schema surface, and weakens the useful distinction between source-backed facts and project-owned wording conventions.

### Send the raw registry object after the context

Rejected. `scope`, version, term IDs, and categories are not required by the model. Least-privilege delivery exposes only bilingual lexical pairs while the full registry remains independently hash-bound.

### Select only “relevant” terms heuristically

Rejected for this increment. There is no reviewed deterministic applicability mapping. Substring matching or model-based selection would itself choose semantic relevance and could silently omit required terminology or introduce a new model-controlled decision.

### Let the model request terminology through a tool

Rejected. This would add a new tool/runtime authority surface immediately before the first live drafting trial. The bounded registry is small enough for deterministic inline delivery.

## Live-trial gate

No live drafting call may occur merely because this design exists. The implementation of this contract must first land on a fresh reviewed head with deterministic validators green and the normal independent first-pass -> Codex/fallback review sequence complete.

Only after that implementation gate clears may the bounded live drafting trial consume the standing entitlement. The trial must preserve raw output and hashes as immutable evidence, score structural/mechanical acceptance separately from Arabic and English editorial quality, and make no publication or autonomous canonical-mutation claim.

## Explicit non-goals

This design does not claim:

- that every registry term is semantically applicable to every drafting context;
- that terminology pairing proves translation quality;
- that prompt instructions prevent every semantic hallucination;
- that registry delivery changes canonical truth;
- that generated prose is Evidence;
- that a live model call has occurred;
- that any scheduler, coordinator, observability dashboard, or publication path is selected.
