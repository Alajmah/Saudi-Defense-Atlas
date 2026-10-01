# M4 Bilingual Drafting — Remediation Record

## Protocol

This record remediates the findings of the independent first-pass review `5380092774` (BD-01 through BD-07) and the fallback second review `5380124011` (FBD-01, FBD-02) on PR #41 at frozen head `9983d413d45527941e53e9fb8bdbc1a8a10843d8`. The frozen maintainer first-pass record `M4_BILINGUAL_DRAFTING_FIRST_PASS.md` is preserved unchanged; corrections live here. Notably, that record's claims of "exactly once" accounting and "invention is impossible" were overclaims (BD-07) — the first pass asserted properties the v0.1 implementation did not have. This record corrects them; the implementation now provides the properties.

No live model call; adapter version bumped to `m4-bilingual-drafting-v0.2` because the boundary behavior changed.

## Finding-by-finding remediation

### BD-01 — Claim scope dropped — REMEDIATED

The context builder now carries canonical Claim `scope` through verbatim (including `quantity_type` and its ordered/approved/contracted/delivered distinctions), the schema requires it on every context claim, and the fixture claim carries `scope.quantity_type = "contracted"` so the fixture prose's "contracted quantity" is now grounded in the model input. Entity-valued Claim targets must resolve to context Entities at both the builder and the adapter. The contract document and this record stop claiming the guards make semantic invention impossible: they reject defined violations, and human editorial review remains the authority over meaning.

### BD-02 — context-wide support closure — REMEDIATED

A unit's `evidence_ids` must now support the claims that unit cites: the adapter computes the union of the cited claims' own evidence sets and rejects any evidence ID outside it. The core validator proves it — a unit citing the valid but unrelated Falcon-X evidence for the Cedar quantity claim is rejected with the claim-specific-support-closure reason.

### BD-03 — English-only denylist and missing pre-invocation gate — REMEDIATED

Restricted-detail rejection is now bilingual: Arabic markers (جاهزية readiness, دورية patrol, مخزون stock, وحدة عاملة live unit, وتيرة العمليات operational tempo, ذخيرة ammunition) are checked against Arabic text in both prose and context fields. A deterministic drafting-eligibility gate now runs **before any model invocation** over every factual field the draft may express (entity names both locales, claim predicate/value/validity/scope, unknown statements both locales) and fails closed on any restricted marker or coordinate-like number — at the builder and again in the adapter's independent context validation. Validators prove the gate catches restricted English and Arabic in context fields, and restricted Arabic in output prose.

### BD-04 — adapter trusted hand-assembled contexts — REMEDIATED

The adapter now calls `validate_drafting_context` before invocation: full schema validation against `editorial-drafting-context.schema.json` plus the builder-level invariants (identity prefixes, active claims, resolved subjects and entity targets, evidence closure, duplicate detection, conflict refusal, and the bilingual eligibility gate). Accepted output is runtime-validated against `ai-bilingual-draft-run.schema.json` before the accepted status is granted (a schema failure converts the run to rejected); rejected runs are schema-validated too, with a schema-invalid rejected run raising rather than emitting a broken artifact. Validators prove hand-assembled contexts with a flipped claim state, a missing terminology digest, injected candidate entities, non-empty conflicts, and authority escalation are all refused before invocation.

### BD-05 — unknown preservation by ID only — REMEDIATED

The model can no longer author unknown prose at all: the output contract carries `rendered_unknown_ids` (a selection), and the adapter constructs `unknowns_rendered` by copying the context's pre-written bilingual statements verbatim. Meaning preservation is now exact deterministic reuse. The isolation validator proves model-authored unknown prose is rejected as an unsupported key and that accepted runs carry the pre-written statements byte-for-byte.

### BD-06 — number allowlist included bookkeeping digits — REMEDIATED

The allowlist is now derived only from the factual fields a draft may express: Claim values, validity, scope, and official entity names — deliberately excluding IDs, timestamps, versions, and authority/bookkeeping fields. The core validator proves the context-creation year (2026, previously authorizable) is now rejected as ungrounded while the factual 12/2024-03-15 remain accepted.

### BD-07 — accounting was not exactly-once; first pass overclaimed — REMEDIATED

Claim usage is now counted: a claim drafted in two units is rejected, a claim both drafted and listed as undrafted is rejected, and coverage remains required. The frozen first-pass record's "exactly once" and "invention is impossible" claims were wrong for v0.1; this record is the correction of record, and the contract document now states the accurate claim (guards reject defined violations; review remains the authority).

### FBD-01 — no raw-output hash — REMEDIATED

Every run now carries `raw_output_sha256` over the exact model response text, included in the run-identity seed so output bytes distinguish run identity. Raw text itself remains deliberately unpersisted; the hash proves which exact response was evaluated.

### FBD-02 — terminology bound by version only — REMEDIATED

The context now carries `terminology_sha256` (canonical digest over registry version and terms), and the adapter recomputes and refuses a registry whose bytes differ from the context's digest even under the same version string. Both validators prove changed-bytes-same-version is refused.

### LOW — PR description file count — CORRECTED

The PR description now says 10 changed files (the workflow modification included).

## Deterministic validation evidence

- Complete repository suite at the remediation head: **41/41 validators — PASS**, with the rewritten core and isolation validators carrying the expanded matrices (scope grounding, claim-specific closure, exactly-once, bilingual gates, bookkeeping-digit rejection, deterministic unknown reuse, registry-byte binding, hand-assembled-context refusals, raw-output hashing).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- Still no live model call; live drafting behavior remains unknown until a reviewed live drafting increment runs.
- Translation/editorial quality and entity-name translation quality remain outside the mechanical guards, as before.
- The natural-language prompt wrapper for live drafting remains deferred to the live increment.

## Freeze

This record completes remediation of BD-01 through BD-07 and FBD-01/FBD-02. The remediated head awaits exact-head CI and re-review.
