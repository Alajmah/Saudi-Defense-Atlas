# M4 Drafting Prompt Wrapper — Remediation Record

## Protocol

This record remediates the three findings of the independent review of PR #42 at frozen head `cccb2fcc3860549ff843a913cd16d7000c349248` (primary `5383539815`; fallback `5383549082`, reduced reviewer independence; Codex quota-blocked per comment `5937350867`). The frozen maintainer first-pass record is preserved unchanged. No live model call was made and no entitlement was consumed.

Template version stays **v0.1 in place**: the template has never been published to any merged artifact or live run, matching the repository's corrected-in-place-when-never-published precedent. The adapter stays v0.7 (no boundary-behavior change beyond the template text itself, which the template hash tracks).

## PW-01 — wrapper quoted operational vocabulary — REMEDIATED

The first template draft prohibited sensitive detail by naming it: "availability, posture, movement, coordinates." That conflicted with the design decision to prohibit without quoting, and those terms were not all covered by the restricted-marker set. The rule now states the prohibition generically ("Do not include operationally sensitive detail of any kind, and do not include precise location data"), and the vocabulary is pinned in code: `WRAPPER_FORBIDDEN_VOCABULARY` in the service module carries every restricted marker in both locales plus the four operational terms, and both validators assert the wrapper template carries none of it.

## PW-02 — the isolation claim was too broad — REMEDIATED

The first pass claimed the validators "prove the wrapper cannot introduce factual payload." The reviewer correctly identified that the `factual_strings` traversal covered only selected fields — it omitted claim string values, `scope.note`, locator text, and `unknown.aspect` — and that even a complete traversal proves enumerated syntactic properties, not a generic theorem. Both halves are fixed:

- The traversal now walks every string-bearing surface of the context — identities, names, predicates, typed claim values and validity dates (with structural discriminator keys such as `kind`/`precision`/`role`/`entity_type` excluded so schema vocabulary is not mistaken for factual text), scope notes and scope entity references, locator text, and the full unknown records including aspect.
- The living claim is narrowed to the enumerated proven properties (round-trip, digit absence, Arabic-script absence, forbidden-vocabulary absence, fixture-overlap, registry-rendering absence), with the instructions-only judgment of the reviewed static template recorded as review evidence, not a validator theorem. (Residual round: this narrowing initially reached the contract document but not the service module docstring or the validator comments, which still said "cannot introduce factual payload"; the re-review 5384817222 caught the gap and all living commentary now carries the enumerated-property framing.)

## PW-03 — living documentation contradicted v0.7 — REMEDIATED

The service module docstring and the `build_bilingual_draft_run` docstring still described the invoker as receiving the bare canonical serialization; both now describe the rendered wrapper input. The ROADMAP's drafting bullet stated the bare-context behavior without noting supersession — it now marks that as the v0.6-baseline behavior superseded by the wrapper increment — and its stale "bilingual AI drafting remains unimplemented" line now states the true boundary: the deterministic boundary and reviewed wrapper are implemented, no live model has drafted through them, and quality/publication remain unqualified. (Residual round: three further stale statements were caught by re-review 5384817222 and corrected — the contract's Verification section still said "canonical-input-only invoker evidence," the isolation validator still described the invoker as receiving "ONLY the bounded approved context ... nothing extra," and ROADMAP step 4 still instructed defining the drafting projection that is already delivered; step 4 now names the live drafting trial and the registry-delivery decision.)

## LOW — PR description file count — CORRECTED

The PR description now says seven changed files (the first-pass record being the seventh).

## Deterministic validation evidence

Complete repository suite at the remediation head: **41/41 validators — PASS**, with both drafting validators now carrying the pinned-vocabulary assertion and the extended fixture-overlap traversal. The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

### PW-02R / PW-03R — residual statement propagation — REMEDIATED (residual round)

The re-review (`5384817222`, fallback `5384825362`) found the narrowed PW-02 claim and the PW-03 reconciliation had not reached every living statement. All corrected in this round: the service module docstring and both validator comments now use the enumerated-property/review-evidence framing; the contract's Verification section describes the rendered-wrapper-input evidence; the isolation validator's invoker description names the wrapper input; and ROADMAP step 4 now instructs the live drafting trial with the registry-delivery decision instead of defining the already-delivered projection. The earlier sections of this record overstated closure when they said PW-02 and PW-03 were fully remediated; those sections now carry residual-round notes, and this section is the correction of record.

## Explicitly unverified / unresolved

Wrapper effectiveness remains unknown and unclaimed until the reviewed live drafting trial. The registry-delivery question remains open for the live increment, as before.

## Freeze

This record completes remediation of PW-01 through PW-03. The remediated head awaits exact-head CI and re-review.
