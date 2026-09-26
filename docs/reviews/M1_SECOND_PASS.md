# M1 Second-Pass Review — PR #2

**Branch:** `m1/vertical-slice-f15sa`

**Purpose:** independent post-remediation review of the final M1 ingestion/governance/canonical-write increment after the exhaustive first-pass findings were frozen.

## Review boundary

This pass reviewed the current PR implementation as a bounded single-writer canonical-write increment, not as completion of the whole M1 milestone. The repository roadmap still requires the public read projection/API and bilingual cited equipment page before M1 acceptance.

Reviewed areas:

- acquisition and redirect trust boundary;
- raw retrieval versus canonical Document identity;
- bounded parser/Evidence lifecycle;
- proposal semantics and claim ceiling;
- approval/hash authorization;
- multi-mutation failure accounting;
- ambiguous write reconciliation;
- replay and project Revision semantics;
- Wikibase canonical-ID lookup/projection completeness;
- CI/runtime evidence and documentation claims.

## New finding

### M1-F18 — Backend inspection exceptions escaped structured reconciliation state

The second pass found that `backend.inspect_effect()` exceptions could escape the mutation guard during preflight or post-write reconciliation. That violated the intended invariant that uncertain external effects remain explicit and auditable.

Resolution is recorded in `docs/reviews/M1_PR2_REMEDIATION.md`. The guard now converts inspection failures to explicit unknown state, blocks new writes on preflight uncertainty, and stops after an attempted effect if post-write inspection is unavailable. Static regression tests cover both positions.

## Areas reviewed with no additional material finding

After M1-F18 remediation, this pass found no additional merge-blocking issue in:

- exact proposal-hash authorization;
- same-content replay behavior;
- pure replay Revision prohibition;
- content-addressed Revision identity;
- source/document/evidence separation;
- evidence selector/hash projection;
- manufacturer Claim semantics for the bounded source;
- delivery Event participant-role semantics;
- projection-version equivalence checks;
- Action-API canonical-ID reconciliation on the verified local stack;
- exclusion of WDQS from mutation recovery;
- single-attempt ambiguous-write behavior.

## Explicitly unresolved / outside qualification

### Concurrent writer uniqueness — M1-F15

The implementation remains a **single-writer proof**. Two concurrent writers may both observe an SDA canonical ID as absent before either write becomes visible. No production automated mutation workers should be enabled until a project-owned coordination/uniqueness mechanism is selected and independently verified.

### M1 public projection is not complete

PR #2 does not satisfy the entire M1 roadmap. The following remain for the next M1 increment:

- project-owned canonical read adapter/API;
- one public F-15SA equipment view;
- Arabic and English rendering from the same SDA IDs;
- visible claim/event evidence and citations;
- related entities and timeline snippet;
- public-view unknown/missing-data behavior;
- public restricted-detail filtering;
- end-to-end traceability from rendered fact back to Source/Document/Evidence/Claim or Event.

## Review judgment

PR #2 is suitable to merge as the **M1 ingestion, governance, and canonical-write increment** once its final-head static and clean-stack workflows are green. It must not be represented as full M1 acceptance, and it does not qualify concurrent production mutation.
