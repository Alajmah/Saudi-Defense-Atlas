# M2 Relationship Graph — Exhaustive First-Pass Review

## Review Surface

Reviewed increment: backend-neutral procurement/exercise relationship projection introduced by PR #4.

Scope reviewed:

- `schemas/v0.1/relationship-graph-view.schema.json`
- `services/presentation/relationship_graph.py`
- `scripts/validate_m2_relationship_graph.py`
- `scripts/validate_m2_relationship_graph_isolation.py`
- M2 additions to `schema-validation.yml`
- interaction with the accepted M1 `EquipmentView` provenance/citation helpers
- source-admission policy as an upstream trust boundary

Explicitly out of scope for this increment:

- graph database adoption
- visualization framework adoption
- production frontend topology
- search/indexing
- live/operational location data
- generalized Wikibase graph-read adapter

## Intent and Invariants

The increment must produce a public relationship graph without becoming a second factual truth store. It must:

1. derive nodes/edges only from canonical SDA Entity/Claim/Event records;
2. keep SDA IDs as public identity and never expose backend Q/P mappings;
3. create no inferred entity-to-entity relationship;
4. require supporting Evidence for every material Claim/Event presented;
5. preserve disputed Claim state;
6. keep procurement and exercise domains independently filterable;
7. use bounded expansion so an adjacent company/unit does not recursively pull unrelated graph data;
8. preserve event temporal semantics, including an available end date;
9. remain deterministic under input ordering.

## Findings Register

### M2-F01 — Claim expansion could become order-dependent and exceed the intended bound

**Area:** correctness / graph scope

**Finding:** The initial projector compared each candidate Claim against the growing `selected_entity_ids` set. A Claim discovered early could add a new Entity that enabled another Claim later in input order, producing accidental multi-hop expansion and order-dependent output.

**Evidence:** Initial implementation mutated `selected_entity_ids` inside the same Claim-selection pass and used that same set for subsequent selection.

**Why it matters:** Public graph scope would depend on record order and could expand beyond the requested root context.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Claim admission now compares only against an immutable `root_set`. Regression validation reverses Claim/Event input order and rejects cascading contract/exercise Claims.

---

### M2-F02 — Event nodes and timeline entries initially omitted direct citations

**Area:** provenance / public presentation

**Finding:** Event-derived edges carried citations, but the Event node and timeline record themselves did not.

**Why it matters:** The public UI/API could present a dated Event without a citation at the material object being rendered, forcing consumers to infer provenance from graph edges.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. `event_node` and `timeline_event` now require citations, and regression tests require at least one `supports` Evidence relation.

---

### M2-F03 — Root-adjacent Entities could pull unrelated Events into the graph

**Area:** correctness / bounded expansion

**Finding:** The first Event-selection rule admitted an Event when any participant/related Entity intersected the full `selected_entity_ids` set. For an F-15SA root, the manufacturer Claim discovers Boeing; that rule could therefore admit an unrelated Boeing procurement Event with no F-15SA relationship.

**Why it matters:** This is semantic graph leakage. A public equipment graph could become polluted by unrelated contracts/exercises merely because a high-degree organization was adjacent to the root.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Events are admitted only when they directly reference a root Entity or explicitly reference one of the selected root-adjacent Claim IDs. `validate_m2_relationship_graph_isolation.py` adds an unrelated Boeing contract-award Event and proves it is absent from nodes, edges, and timeline.

---

### M2-F04 — Exercise/event end dates were dropped from the public projection

**Area:** temporal semantics

**Finding:** The canonical Event supports `ended_at`, but the initial M2 Event node and timeline projection retained only `occurred_at`.

**Why it matters:** Exercise duration and multi-day event intervals are meaningful public historical facts. Collapsing them to a start date loses canonical information.

**Severity:** Medium

**Confidence:** High

**Disposition:** FIXED. Event nodes and timeline entries now carry `ended_at` (nullable), schema-valid, with regression coverage for the synthetic exercise interval.

---

### M2-F05 — M2 reuses underscored M1 projection helpers

**Area:** maintainability / module ownership

**Finding:** `relationship_graph.py` imports `_citations`, `_entity_value_id`, and `_index` from `equipment_view.py`. These are module-private helpers by naming convention.

**Why it matters:** The reuse correctly keeps citation behavior consistent, but creates a brittle dependency direction between two public-view projectors. A future M1-specific refactor could unintentionally break M2.

**Severity:** Low

**Confidence:** High

**Disposition:** DEFERRED, NON-BLOCKING. If a third projector needs these helpers, promote them into a project-owned shared presentation/provenance module rather than continuing private cross-module imports. Avoid abstraction churn before a second concrete consumer pattern exists beyond M2.

---

### M2-F06 — Synthetic graph fixtures use non-production data and must not be mistaken for admission evidence

**Area:** evidence / test semantics

**Finding:** The graph fixture is explicitly synthetic and exists to test representation/projection mechanics. It does not prove that a real procurement or exercise source has passed SDA claim-admission policy.

**Why it matters:** Passing projection tests must not be interpreted as evidence that source authority, corroboration, or editorial admission has been demonstrated for M2 real-world records.

**Severity:** Informational

**Confidence:** High

**Disposition:** ACCEPTED BOUNDARY. Real-source ingestion/admission remains a separate M2 increment. The projector consumes already-canonical records and does not replace upstream source policy.

## Failure and Trust Review

Observed fail-closed behavior:

- unresolved root Entity -> projection error;
- inactive Entity selected for graph -> projection error;
- unresolved Evidence/Document/Source -> projection error through the M1 citation resolver;
- material Claim/Event with no supporting Evidence -> projection error;
- malformed participant Entity ID/role -> projection error;
- duplicate root/domain selectors -> projection error;
- duplicate node/edge IDs -> projection error;
- edge referencing a missing node -> projection error.

No authentication, secret handling, command execution, or external-network surface is added by this increment. It is a pure read-model projector plus validation code.

## Areas Reviewed With No Material Issue Found

- SDA IDs remain the graph identity boundary.
- Backend identifiers are not copied into nodes/edges.
- Disputed Claims remain visibly `disputed`; superseded/withdrawn Claims are excluded by the visible-state rule.
- Procurement and exercise filtering is explicit and deterministic.
- Claim edges remain explicit source-record projections rather than inferred graph relationships.
- Event participant and related-entity edges point to the source Event record.
- Public citations retain Evidence -> Document -> Source traceability.
- No operational location, readiness, patrol, stock, or live movement field is introduced.

## Open Questions / Deferred Work

1. When a generalized Wikibase graph reader is added, it must admit only current SDA projection markers and canonical records; arbitrary legacy Wikibase statements must not become graph edges.
2. Source staleness is an M2 roadmap outcome but is not implemented by this first relationship-projection increment.
3. A graph/visualization library remains unselected and requires APR evidence before adoption.
4. If projection helper reuse expands, extract shared citation/index/value helpers into a stable presentation utility module.

## First-Pass Judgment

After fixes M2-F01 through M2-F04, no first-pass merge-blocking defect remains in the pure relationship-projection contract. M2-F05 is a bounded maintainability debt and M2-F06 is an explicit evidence boundary rather than a production claim.

The next review step must be independent of this findings register; it should attempt to falsify the bounded-expansion, provenance, and temporal claims rather than merely restating these findings.
