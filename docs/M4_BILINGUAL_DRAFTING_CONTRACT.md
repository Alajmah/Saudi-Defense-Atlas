# M4 Bounded Bilingual Drafting Contract

## Status

Deterministic, provider-independent first increment. No live model call has been made; a fake invoker proves every invariant in CI. No translation-quality, editorial-quality, or publication claim is made.

## Architecture rule

**The model drafts language; it does not choose facts.** A deterministic `ApprovedDraftingContext` (`build_approved_drafting_context`) first selects only:

- already-approved canonical Claims (`claim_state = active`, active `record_status`);
- their Evidence references (with Document identity and locator);
- resolved Entities carrying official bilingual names in **both** locales;
- explicit unknown statements (bounded, bilingual, pre-written by the pipeline);
- the project-owned terminology registry version.

Only that bounded object reaches the drafting adapter. The adapter passes exactly the canonical JSON serialization of the context as the model input — nothing else — and records its SHA-256 (`input_context_sha256`). A natural-language prompt wrapper arrives with the first live-model increment, wrapped around this same serialization.

## Bilingual structure and the parity invariant

Each factual content unit (`UNIT-*`) carries **one shared support set** — `claim_ids` + `evidence_ids` — plus paired `en`/`ar` prose. The invariant is structural: **Arabic and English may phrase the fact differently, but neither locale can introduce a fact with a different support set**, because the support set is not per-locale. Generated prose is not evidence; every citation resolves to context Evidence, and orphaned citations are rejected.

## Selection rules (fail closed at the builder)

- Candidate identities (`CAND-*`) and non-canonical IDs never enter the context.
- Claims must be `active`; `disputed` claims are refused, and two active claims on the same subject/predicate with different values are detected as unresolved conflict and refused — **no conflict-aware synthesis is attempted**. Conflict-aware prose can be a later capability once a structured, independently reviewed representation exists.
- Entities without an official name in either locale are refused: drafting never invents translations. Official bilingual canonical names outrank generated translations (governance rule); the terminology registry governs recurring **non-entity** terminology only.
- Evidence references must resolve inside the context (support closure).

## Draft-output rules (fail closed at the adapter)

- Strict finite JSON, duplicate object keys rejected (same parser discipline as the extraction trial).
- Units must carry only `unit_id`/`claim_ids`/`evidence_ids`/`prose`; support IDs must exist in the context.
- **Terminology pairing, both directions:** if a registry term's English rendering appears in a unit's English prose, the registry Arabic rendering must appear in the Arabic prose of the same unit, and vice versa.
- **Invented-precision guard:** every digit sequence in either locale's prose (Arabic-Indic digits normalized) must appear in the approved context's canonical serialization; numbers the context does not carry are rejected.
- **Restricted-detail rejection:** prose carrying restricted operational markers (readiness, patrol, stock levels, live-unit language, and similar) or uncoarsened coordinate-like numbers is rejected.
- **Full accounting:** every approved claim must be either drafted in a unit or listed in `undrafted_claim_ids` (abstention is explicit; invention is impossible); every context unknown must be rendered bilingually in `unknowns_rendered` or listed in `omitted_unknown_ids`.
- Any violation rejects the run and **clears all drafted text**.

## Terminology registry

`data/terminology/bilingual-terminology-v0.1.json` is a small project-owned bounded registry (equipment categories, procurement states, ranks, recurring technical terms). It is not an external terminology system, and it never overrides official entity names. The registry version is bound into the context and the adapter refuses a registry whose version differs.

## Authority

The drafting context is `approved_canonical_read_only` with `canonical_mutation_authority=false` and `publication_authority=false`. The draft run is `candidate_only` with the same false flags; the schema pins both constants, so an authority claim is schema-invalid, and the adapter refuses an escalated context before invocation.

## Verification

Two deterministic validators run in CI (`validate_m4_bilingual_drafting.py` core; `validate_m4_bilingual_drafting_isolation.py` isolation), covering: context determinism and schema validity; the builder's fail-closed matrix; canonical-input-only invoker evidence; rejection of unsupported IDs, orphaned citations, terminology violations (both directions), invented numbers (both locales, Arabic-Indic included), restricted detail and coordinates; full claim/unknown accounting with explicit abstention; unknown preservation per locale; terminology-version binding; authority escalation refused at both layers; deterministic per-invocation run identity.

## Claim ceiling

This increment establishes the bounded drafting projection mechanics only. It does not establish translation quality, editorial quality, fluency in either locale, live-model behavior, or any publication path. The draft artifact is downstream candidate data until human editorial review says otherwise, and no scheduler, autonomous publication, or canonical mutation exists here.
