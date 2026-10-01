# M4 Terminology Registry Delivery Design — Remediation Record

## Protocol

This additive record remediates the frozen maintainer first-pass findings in `M4_TERMINOLOGY_DELIVERY_FIRST_PASS.md`. The first-pass file is not modified. No Codex or fallback result was consulted before the first pass was frozen. No live model call was made and no entitlement was consumed.

Frozen first-pass reviewed design head: `203184221b42af8d1aa264bd62a6fa2cf2b7fd77`.

## TRD-01 — digest wording overstated the bound surface — REMEDIATED

The design now uses the exact current contract: `load_terminology()` accepts `version` + complete term records, and `terminology_digest()` hashes that validated acceptance payload. It explicitly records that top-level descriptive registry `scope` is not accepted into the runtime registry object, is not digest-bound, and is not delivered to the model.

All references to “full source registry” were replaced with “validated registry acceptance payload” or equivalent.

## TRD-02 — Entity-name precedence lacked a deterministic collision rule — REMEDIATED

The design now requires a pre-invocation registry/context collision gate. Any English registry rendering that case-insensitively equals a context Entity English name, or any Arabic registry rendering that exactly equals a context Entity Arabic name, fails closed before rendering/invocation.

The rule rejects even a fully matching bilingual pair because the terminology registry is explicitly non-entity terminology and does not need to duplicate context-owned Entity names. Fuzzy/substring matching remains out of scope.

The broader statement that official Entity names outrank terminology remains a prompt + human-review rule; the design no longer claims a generic mechanical semantic theorem beyond exact collisions.

## TRD-03 — renderer ownership/binding was underspecified — REMEDIATED

The design now freezes the renderer boundary conceptually as `render_draft_prompt(context, terminology) -> str`. The renderer must load/validate the supplied registry, verify its version and digest against the context, run delivery gates, derive the least-privilege lexical payload internally, canonically serialize both data blocks, and return the exact complete string supplied to the invoker.

There is no global/default registry, caller-supplied pre-rendered terminology block, or rendering path over registry bytes that have not been checked against the context binding.

## TRD-04 — delivery sensitivity gate missed PW-01 vocabulary — REMEDIATED

The design no longer proposes reusing only the older drafting-eligibility marker set. It requires one shared model-input-forbidden vocabulary covering:

- existing English restricted markers;
- existing Arabic restricted markers;
- `availability`;
- `posture`;
- `movement`;
- `coordinate`;
- `coordinates`.

Wrapper checks and terminology-delivery checks must consume the same underlying pinned vocabulary, plus the existing coordinate-like numeric pattern. This prevents terminology delivery from reopening the lexical-priming surface closed by PW-01.

## Additional precision added during remediation

The design now explicitly distinguishes static-wrapper properties from whole-input properties after terminology delivery. Arabic registry renderings are intentionally present in the typed TERMINOLOGY block, and future terminology data may contain digits; neither fact changes the context-only factual-number allowlist.

The model-facing payload remains least privilege: only ordered `terms[].en` / `terms[].ar` pairs are delivered. Registry version, term IDs, categories, and descriptive scope remain outside the model-facing payload.

## Status after remediation

TRD-01 through TRD-04 are addressed in the design at commit `713691c3b9c0744a6a050ed59ec628631e5014ae`.

Implementation remains intentionally absent. Template v0.2, adapter v0.8, schema changes, validators, and any live run are future work gated on review of this design.
