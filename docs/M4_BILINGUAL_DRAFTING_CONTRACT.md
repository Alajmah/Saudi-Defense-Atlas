# M4 Bounded Bilingual Drafting Contract

## Status

Deterministic, provider-independent first increment. No live model call has been made; a fake invoker proves every invariant in CI. No translation-quality, editorial-quality, or publication claim is made.

## Architecture rule

**The model drafts language; it does not choose facts.** A deterministic `ApprovedDraftingContext` (`build_approved_drafting_context`) first selects only:

- already-approved canonical Claims (`claim_state = active`, active `record_status`), **including material Claim `scope`** (procurement `quantity_type` such as ordered/approved/contracted/delivered is never collapsed);
- their Evidence references (with Document identity and locator);
- resolved Entities carrying official bilingual names in **both** locales;
- explicit unknown statements (bounded, bilingual, pre-written by the pipeline);
- the project-owned terminology registry version.

The context is canonically typed: `predicate_id` uses the canonical enum, Claim `value` reuses `common.schema.json#$defs/claim_value`, `scope.quantity_type` uses the canonical procurement-stage enum, `validity` reuses `validity_interval`, `entity_type` uses the canonical enum, and Evidence locators mirror the canonical locator shape — so a hand-assembled context with noncanonical predicate, quantity stage, value shape, or locator fails the schema gate before invocation. Only that bounded object reaches the drafting adapter. A **deterministic drafting-eligibility gate** first rejects restricted operational detail in any factual field, in either locale, before any model invocation. The adapter **independently re-validates the full context contract** (schema plus builder invariants).

## Model input: reviewed wrapper with two typed data blocks

The complete model input is the reviewed instruction wrapper (`m4-bilingual-drafting-prompt` template **v0.2**) rendered around **two typed data blocks**: the canonical JSON serialization of the context (the only factual authority), then a **terminology block** carrying the least-privilege delivery payload (`category` + `en` + `ar` per registry term, registry order, no version/term-id/scope). The renderer owns the full registry-to-input dataflow (`prepare_draft_input`): load and freeze-check categories, verify registry version and acceptance digest against the context binding, apply the lexical-safety and Entity-name collision gates, derive the payload, and token-replace both blocks. The run records six trace values: template id/version/hash, `terminology_registry_sha256` (the context binding), `terminology_delivery_sha256` (the delivered projection), `rendered_input_sha256` (the complete input), while `input_context_sha256` continues to hash the context alone. Terminology digits never enlarge the factual-number allowlist.

The wrapper is reviewed as instructions-only. The validators mechanically prove a precise, enumerated set of properties — not a generic no-factual-payload theorem:

- **round-trip proof:** stripping the wrapper from any rendered input reproduces the canonical context bytes exactly;
- **no numeric payload:** the wrapper contains no digit characters, so every number in the model input comes from the context (whose factual fields the number allowlist governs);
- **no Arabic script in the static wrapper:** the wrapper is English-only, so every Arabic string in the model input comes from the typed data blocks — the context (names, statements) or the terminology block (registry Arabic renderings);
- **no forbidden vocabulary:** the wrapper carries none of the pinned `WRAPPER_FORBIDDEN_VOCABULARY` — every restricted marker in either locale plus the operational-domain terms (availability, posture, movement, coordinate forms) the first template draft quoted before being reworded;
- **fixture-overlap check:** no string from the context's free-text and identifier surfaces — names, identities, predicates, typed claim values, validity dates, scope notes and entity references, locator text, unknown aspects and statements — appears in the wrapper text;
- **no registry renderings:** no terminology term's English or Arabic rendering appears in the wrapper (the template was deliberately reworded when the ordinary word "approved" collided with a registry term).

The judgment that the reviewed static template is itself instruction-only is review evidence carried by the first-pass and remediation records, not a validator theorem: the checks above constrain the template's syntax and its overlap with the evaluated context and registry, and a template is a fixed, reviewed artifact rather than model output.

The registry-delivery question is resolved by the merged terminology-delivery design (`docs/M4_BILINGUAL_DRAFTING_TERMINOLOGY_DELIVERY_DESIGN.md`), implemented here: a second typed block, bounded categories, shared forbidden-vocabulary scanning over every delivered string, exact registry/Entity-name collision refusal, and separate registry/delivery hashes.

The adapter also records the SHA-256 of the exact model response (`raw_output_sha256`).

## Bilingual structure and the parity invariant

Each factual content unit (`UNIT-*`) carries **one shared support set** — `claim_ids` + `evidence_ids` — plus paired `en`/`ar` prose. The invariant is structural: **Arabic and English may phrase the fact differently, but neither locale can introduce a fact with a different support set**, because the support set is not per-locale. Generated prose is not evidence; every citation resolves to context Evidence, and orphaned citations are rejected.

## Selection rules (fail closed at the builder)

- Candidate identities (`CAND-*`) and non-canonical IDs never enter the context.
- Claims must be `active`; `disputed` claims are refused. Conflict detection is **scope- and validity-aware**: two active claims conflict only when they share subject, predicate, semantic scope (including `quantity_type`), and validity context while asserting different values. Ordered-versus-delivered quantities and the same scope at different validity contexts coexist; deeper conflict authority remains with upstream canonical adjudication. **No conflict-aware synthesis is attempted.** Conflict-aware prose can be a later capability once a structured, independently reviewed representation exists.
- Entities without an official name in either locale are refused: drafting never invents translations. Official bilingual canonical names outrank generated translations (governance rule); the terminology registry governs recurring **non-entity** terminology only.
- Evidence references must resolve inside the context (support closure).

## Draft-output rules (fail closed at the adapter)

- Strict finite JSON, duplicate object keys rejected (same parser discipline as the extraction trial).
- Units must carry only `unit_id`/`claim_ids`/`evidence_ids`/`prose`; support IDs must exist in the context.
- **Per-claim Evidence links and claim-specific support closure:** canonical SDA stores the Evidence role on each Claim→Evidence link (`evidence_links: [{evidence_id, role}]`), and the drafting projection preserves exactly that shape. A unit's `evidence_ids` must belong to the claims it cites, **and every claim in a unit must have at least one cited `supports` link** — partial multi-claim support and contradicting/contextual-only citations are rejected. A context claim with no supporting link at all is refused at build.
- **Terminology pairing, both directions:** if a registry term's English rendering appears in a unit's English prose, the registry Arabic rendering must appear in the Arabic prose of the same unit, and vice versa. The registry is bound by version AND canonical digest (`terminology_sha256`); changed bytes under the same version are refused.
- **Invented-precision guard:** every digit sequence in either locale's prose (Arabic-Indic digits normalized) must appear among the **factual fields** the draft may express — Claim values, validity, scope, and official entity names. Bookkeeping digits (IDs, timestamps, registry versions) deliberately do not authorize prose numbers.
- **Restricted-detail rejection, bilingual:** prose carrying restricted operational markers in English or Arabic, or uncoarsened coordinate-like numbers, is rejected.
- **Exactly-once accounting:** every approved claim is drafted in exactly one unit or listed exactly once in `undrafted_claim_ids` — never both, never twice; every context unknown is rendered or explicitly omitted.
- **Unknown meaning preservation:** the model never authors unknown prose. It selects which unknowns to render (`rendered_unknown_ids`); the adapter copies the pre-written bilingual statements verbatim into `unknowns_rendered`.
- Both accepted and rejected runs are runtime-validated against the run schema before the accepted status is granted.
- Any violation rejects the run and **clears all drafted text**. The mechanical guards reject the defined violations above; they do not make semantic invention impossible — human editorial review remains the authority over meaning.

## Terminology registry

`data/terminology/bilingual-terminology-v0.1.json` is a small project-owned bounded registry (equipment categories, procurement states, ranks, recurring technical terms). It is not an external terminology system, and it never overrides official entity names. The registry version AND canonical digest are bound into the context; the adapter refuses a registry whose version or bytes differ.

## Authority

The drafting context is `approved_canonical_read_only` with `canonical_mutation_authority=false` and `publication_authority=false`. The draft run is `candidate_only` with the same false flags; the schema pins both constants, so an authority claim is schema-invalid, and the adapter refuses an escalated context before invocation.

## Verification

Two deterministic validators run in CI (`validate_m4_bilingual_drafting.py` core; `validate_m4_bilingual_drafting_isolation.py` isolation), covering: context determinism and schema validity; the builder's fail-closed matrix; rendered-wrapper-input invoker evidence (template hashes, byte round-trip, and the enumerated template-property proofs); rejection of unsupported IDs, orphaned citations, terminology violations (both directions), invented numbers (both locales, Arabic-Indic included), restricted detail and coordinates; full claim/unknown accounting with explicit abstention; unknown preservation per locale; terminology-version binding; authority escalation refused at both layers; deterministic per-invocation run identity.

## Claim ceiling

This increment establishes the bounded drafting projection mechanics only. It does not establish translation quality, editorial quality, fluency in either locale, live-model behavior, or any publication path. The draft artifact is downstream candidate data until human editorial review says otherwise, and no scheduler, autonomous publication, or canonical mutation exists here.
