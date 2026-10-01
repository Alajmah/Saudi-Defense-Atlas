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

### RBD-01 — support closure incomplete; global Evidence role — REMEDIATED (residual round)

The re-review (`5380611107`) found the v0.2 closure admitted partial multi-claim support and ignored Evidence roles. The context now preserves the canonical shape exactly: each claim carries `evidence_links: [{evidence_id, role}]` with `supports`/`contradicts`/`contextualizes` on the link, and the global Evidence `role` field is gone. The adapter requires every claim in a unit to have at least one **cited `supports` link**; partial multi-claim support, contradicting-only, and contextual-only citations are rejected, and a claim with no supporting link anywhere is refused at build. Regressions cover all three cases plus the empty-citation unit.

### RBD-02 — conflict detection collapsed scope and time — REMEDIATED (residual round)

Conflict fingerprints are now `(subject, predicate, canonical scope)` and values are compared only within the same validity context. Ordered-12 versus delivered-6 coexists (regression), and claims with non-identical validity objects (canonical JSON equality) coexist (regression) — note this distinguishes non-identical validity contexts; it does not itself prove temporal disjointness for overlapping intervals, which remains with upstream canonical adjudication, and the same scope and validity with different values still fails closed (regression). Deeper conflict authority is explicitly deferred to upstream canonical adjudication, per the reviewer's alternative.

### RBD-03 — context schema looser than canonical — REMEDIATED (residual round)

The context schema now reuses canonical definitions via the schema registry: `predicate_id` is the canonical enum (20 predicates), `value` is `common#$defs/claim_value` (typed oneOf), `scope.quantity_type` is the canonical procurement-stage enum, `validity` is `validity_interval` (object, not nullable — fixtures updated), `entity_type` is the canonical enum, and the Evidence locator mirrors the canonical locator shape. The builder self-validates its constructed context against this schema before returning, and the adapter's pre-invocation gate re-validates hand-assembled contexts against the same schema — so invalid predicates, invalid quantity stages, and malformed values are refused before any model invocation (regressions at build and in the schema gate). The service's schema loader builds a registry over sibling schemas so cross-file `$ref`s resolve, mirroring `validate_schemas`.

Adapter version bumped to `m4-bilingual-drafting-v0.3` (boundary behavior and schema changed). LOW metadata: the PR description now says 11 files (the remediation record itself being the eleventh).

### RBD-04 — adapter-path validation missed three builder invariants — REMEDIATED (residual round 2)

The re-review (`5380995625`) found `validate_drafting_context()` did not reject reserved-prefix Entity IDs (`SDA-CLAIM-*` / `SDA-EVID-*`, schema-pattern-legal), unresolved non-null `unknown.entity_id`, or duplicate Evidence IDs within a Claim's `evidence_links`. All three are now enforced on the adapter path (and the schema adds `uniqueItems` on `evidence_links` for identical-object duplicates), with hand-assembled-context regressions for each — including the same-evidence-different-role case only the invariant check catches. The prior remediation text claiming the adapter re-enforced "identity prefixes" and "duplicate detection" was premature for these specific invariants; it is accurate as of this round.

### RBD-05 — locator lacked canonical `minProperties: 1` — REMEDIATED (residual round 2)

The drafting-context locator now carries `minProperties: 1`, mirroring canonical Evidence; an empty locator is refused at build (self-validation) and on the adapter path, with a regression. The earlier "mirrors the canonical locator" claim is now literally true.

Adapter version bumped to `m4-bilingual-drafting-v0.4` (adapter-path validation behavior changed). The RBD-02 wording above was also narrowed per the fallback review: the comparison distinguishes non-identical validity objects; it does not prove temporal disjointness of overlapping intervals.

### RBD-06 — scope.entity_ids referentially open — REMEDIATED (residual round 3)

Every `scope.entity_ids` entry must now resolve to a context Entity at both the builder and the adapter path, so material scope never reaches the model without the resolved bilingual Entity record. Regressions at both boundaries.

### RBD-07 — context identity not content-bound on the adapter path — REMEDIATED (residual round 3)

The deterministic ID derivation is factored into `_derive_context_id`, used by the builder and recomputed by `validate_drafting_context`: a hand-built context whose ID does not match its content is refused before invocation. Regression: a valid context with modified content under the original ID is refused. (RBD-09 later narrowed this round's guarantee: the original derivation bound unknown records by ID only, so statement/aspect/entity-reference modifications could keep a stale ID; round 5 closed that - see below.)

### RBD-08 — caller-settable adapter-version trace — REMEDIATED (residual round 3)

`DraftModelTrace` no longer accepts an adapter version: the field is removed from the constructor and derived from the module constant, so the nested trace and the top-level run field cannot disagree. Regressions: constructing a trace with a `adapter_version` kwarg raises; emitted runs assert both fields equal the module version.

Adapter version bumped to `m4-bilingual-drafting-v0.5` (adapter-path validation behavior changed again).

### RBD-09 — context ID not fully content-bound — REMEDIATED (residual round 4)

The re-review (`5382524763`) found `_derive_context_id` incorporated unknown records by ID only, leaving `statement_en`, `statement_ar`, `aspect`, and the unknown's entity reference outside the identity. The derivation now incorporates the **complete** `context["unknowns"]` records — the same pre-written statements the adapter can copy verbatim into `unknowns_rendered` — so the ID binds every record the run consumes. Regressions: a modified unknown statement, a modified aspect, and a changed unknown entity reference, each under the retained original ID, are all refused before invocation. The RBD-07 section above now records that its earlier "modified content" claim was broader than that round's implementation guaranteed.

Adapter version bumped to `m4-bilingual-drafting-v0.6` (identity derivation changed).

## Deterministic validation evidence

- Complete repository suite at the remediation head: **41/41 validators — PASS**, with the rewritten core and isolation validators carrying the expanded matrices (scope grounding, claim-specific closure, exactly-once, bilingual gates, bookkeeping-digit rejection, deterministic unknown reuse, registry-byte binding, hand-assembled-context refusals, raw-output hashing).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- Still no live model call; live drafting behavior remains unknown until a reviewed live drafting increment runs.
- Translation/editorial quality and entity-name translation quality remain outside the mechanical guards, as before.
- The natural-language prompt wrapper for live drafting remains deferred to the live increment.

## Freeze

This record completes remediation of BD-01 through BD-07 and FBD-01/FBD-02. The remediated head awaits exact-head CI and re-review.
