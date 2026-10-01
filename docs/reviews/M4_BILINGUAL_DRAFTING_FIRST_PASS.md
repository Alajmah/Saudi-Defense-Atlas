# M4 Bounded Bilingual Drafting — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the bounded bilingual drafting projection increment, performed before any independent second review. It is deterministic and provider-independent: no live model call exists anywhere in this increment.

## Baseline and review surface

Base branch / merge base:

- `main` at `6c3f6f598241d710859620270e3690b9c56ecd44` (squash merge of PR #40), verified via `git rev-parse main` after fast-forward pull.

Implementation baseline reviewed before this review record was added:

- `m4/bilingual-drafting-projection` at the implementation commit recorded with this branch's push.

Net surface:

1. `.github/workflows/schema-validation.yml` (two CI steps)
2. `data/terminology/bilingual-terminology-v0.1.json` (new — the bounded registry)
3. `docs/M4_BILINGUAL_DRAFTING_CONTRACT.md` (new)
4. `docs/ROADMAP.md`
5. `schemas/v0.1/ai-bilingual-draft-run.schema.json` (new)
6. `schemas/v0.1/editorial-drafting-context.schema.json` (new)
7. `scripts/validate_m4_bilingual_drafting.py` (new — core validator)
8. `scripts/validate_m4_bilingual_drafting_isolation.py` (new — isolation validator)
9. `services/intelligence/bilingual_drafting.py` (new — context builder + drafting adapter)

Not changed: every existing service, schema, validator, fixture, prompt, and evidence artifact. The suite moved from 39 to 41 validators, both new ones CI-gated.

## Design decisions worth the reviewer's attention

**The terminology registry is a data file, not a schema-bearing service.** AI_GOVERNANCE requires a maintained registry for recurring terminology; the increment introduces a small project-owned JSON registry (`data/terminology/`), validated structurally by the builder (unique term IDs, unique English renderings, both locales non-empty, categories present) rather than by a new schema. Official bilingual entity names stay authoritative in the context entities; the registry never governs entities.

**Terminology enforcement is substring pairing, bidirectional.** If a registry term's English rendering appears in a unit's English prose, the registry Arabic rendering must appear in the same unit's Arabic prose, and vice versa. This is deliberately mechanical — no translation quality judgment — and the first implementation of the fixture itself tripped it (the happy-path prose used "approved" in English while the Arabic used a verb form that did not contain the registry's exact rendering), which is direct evidence the guard works and that the fixture was corrected to respect the registry rather than the check being loosened.

**The invented-precision guard is an allowlist over the context's canonical serialization.** Every digit run in either locale's prose — Arabic-Indic digits normalized to Western — must appear among the digit runs of the context JSON. Crude by design: it cannot judge semantics, but it cannot be fooled by a number the approved context never carried.

**Official-name precedence is documented, not mechanically policed.** The isolation validator honestly records that a unit substituting an invented Arabic entity name passes the mechanical checks: the boundary governs support sets, terminology pairing, numbers, and restricted detail — not entity-name translation quality, which the contract assigns to the registry-plus-official-names rule and future evaluation.

**Conflict handling is fail-closed at both layers.** The builder refuses `disputed` claims and detects two active claims on the same subject/predicate with different values; the adapter refuses any context carrying a non-empty `conflicts` array (and the schema pins `conflicts` to `maxItems: 0`). No synthesis is attempted.

**Abstention is accounted, invention is impossible.** A model may leave a claim undrafted (`undrafted_claim_ids`) or an unknown unrendered (`omitted_unknown_ids`), but the run is rejected unless every approved claim and every context unknown is accounted exactly once.

## Findings during implementation

1. An early design used a module-level terminology cache — a hidden global. Refactored before first run to pass the registry explicitly; the adapter now refuses a registry whose version differs from the context's.
2. The fixture-terminology collision described above (happy-path prose violating the registry pairing) — fixed in the fixture, check untouched.
3. A leftover drafting artifact in a hash assertion was removed before any run.

## Deterministic validation evidence

- Complete repository suite at the implementation head: **41/41 validators — PASS** (39 prior plus the two new, both added to `schema-validation`).
- The core validator covers: context determinism; the builder's fail-closed matrix (candidate claim/entity, disputed claim, superseded record, missing official Arabic name, orphaned evidence, conflicting actives, malformed registry term); accepted-run shape with exact canonical-input evidence (`CAND-` absent from the prompt, prompt byte-equal to the canonical serialization); identity determinism and per-invocation distinctness; the eleven-case rejection matrix with reason fragments and schema-valid rejected runs; accounted abstention acceptance.
- The isolation validator covers: model-input minimality (prompt equals the context object, no restricted or candidate markers); builder and adapter conflict refusal; authority escalation schema-impossible and adapter-refused; terminology pairing in both directions; Arabic-Indic digit coverage of the number guard; bilingual unknown preservation; terminology-version binding.

## Explicitly unverified / unresolved

- No live model has drafted anything under this contract; live-model behavior, fluency, and terminology compliance are unknown until a reviewed live drafting trial runs (a separate increment with its own entitlement scope under the standing policy).
- Translation and editorial quality are explicitly out of scope for this increment's claims.
- The natural-language prompt wrapper for a live model is deferred to the live increment; today the model input is the bare canonical context serialization.
- Entity-name translation quality is not mechanically policed (recorded above).

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review.
