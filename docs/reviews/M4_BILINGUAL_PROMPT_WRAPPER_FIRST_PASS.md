# M4 Bilingual Drafting Prompt Wrapper — Maintainer First Pass

## Review protocol

This is the maintainer's independent first-pass review of the deterministic drafting prompt-wrapper increment, performed before any independent second review. It is the first of the two deliberately separated live-drafting milestones: this increment reviews the model-input contract itself, with no provider or model behavior in the evidence. No live model call was made and no entitlement was consumed.

## Baseline and review surface

Base branch / merge base:

- `main` at `bed625ff41f97d790f566f6bf6baff7e4b4dc63e` (squash merge of PR #41), verified via `git rev-parse main` after fast-forward pull.

Implementation baseline reviewed before this review record was added:

- `m4/bilingual-prompt-wrapper` at the implementation commit recorded with this branch's push.

Net surface:

1. `docs/M4_BILINGUAL_DRAFTING_CONTRACT.md` (model-input section)
2. `docs/ROADMAP.md`
3. `schemas/v0.1/ai-bilingual-draft-run.schema.json` (`prompt_trace` added)
4. `scripts/validate_m4_bilingual_drafting.py` (wrapper-isolation proofs; prompt assertions)
5. `scripts/validate_m4_bilingual_drafting_isolation.py` (rendered-input and stripped-context proofs)
6. `services/intelligence/bilingual_drafting.py` (wrapper template, render/split, prompt trace; adapter v0.7)

Not changed: the context schema, the context builder's selection rules, the terminology registry, every preserved evidence artifact, and all frozen review records.

## What the increment delivers

### The wrapper and its trace

`DRAFT_PROMPT_TEMPLATE` (`m4-bilingual-drafting-prompt` v0.1) is an instructions-only English template with a single context token. `render_draft_prompt(context)` produces the complete model input by token replacement — never string formatting over context bytes, so context braces cannot collide with template syntax. The run now carries `prompt_trace` (template id, version, template SHA-256, rendered-input SHA-256) while `input_context_sha256` is retained unchanged over the context alone; the run-identity seed includes the rendered-input hash. The adapter version bumped to v0.7 because the invoker's input changed from the bare context serialization to the wrapped input.

### The isolation properties, mechanically proven

The validators prove the wrapper cannot introduce factual payload outside the canonical context:

1. **Round-trip.** `split_rendered_prompt` recovers the canonical context bytes exactly; the validators recompute the canonical serialization independently and compare.
2. **No numeric payload.** The template contains no digit characters — asserted directly — so every number in the model input comes from context factual fields, which the existing allowlist governs. The template uses unnumbered bullets precisely for this property.
3. **No Arabic script.** The template is English-only (asserted), so every Arabic string in the input is context data.
4. **No context strings or identities.** No entity name, entity/claim/evidence/document identity, predicate, or unknown statement from the fixture context appears in the wrapper text — asserted dynamically over every factual string the context carries.
5. **No registry renderings.** No terminology term's English or Arabic rendering appears in the wrapper — checked over the actual registry file, in both directions.

## Findings during implementation

Two template rewordings, both caught by the new checks themselves and both resolved in the template rather than by weakening the checks:

1. The word "approved" — ordinary English in "approved claims" — collided with the registry term `TERM-PROCSTATE-APPROVED`. The template now says "claims in the context" and "claims of the context."
2. The restricted-detail rule originally enumerated the sensitive vocabulary ("readiness, stocks, patrols, live units"), which both quoted operational terminology in the prompt and tripped the bilingual marker scan. The rule now states the prohibition generically ("operationally sensitive detail about availability, posture, or movement").

One recorded open question for the live trial: the context binds the registry by version and digest but does not embed the term renderings, and the wrapper deliberately carries none. How the registry reaches the model is a live-increment design decision that must be reviewed before any live call.

## Deterministic validation evidence

- Complete repository suite at the implementation head: **41/41 validators — PASS**, with the wrapper-isolation proofs running inside both drafting validators (suite count unchanged; this increment hardens existing validators rather than adding files).
- The suite is re-run at the exact frozen tip (this record's commit) immediately before push; the push triggers both workflows on the same tip.

## Explicitly unverified / unresolved

- No live model has seen the wrapped input; wrapper effectiveness (does the model follow it?) is unknown and unclaimed until the reviewed live drafting trial.
- The registry-delivery question above is open by design for the live increment.
- Translation and editorial quality remain unclaimed, as before.

## Frozen maintainer baseline

The implementation commit plus this record constitute the frozen maintainer first pass, awaiting independent review.
