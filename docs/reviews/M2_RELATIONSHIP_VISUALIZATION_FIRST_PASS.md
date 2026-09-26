# M2 First Relationship Visualization — Exhaustive First-Pass Review

## Review Surface

Reviewed increment: the first bounded relationship visualization introduced by PR #8.

Scope reviewed:

- `docs/adr/ADR-0003-first-relationship-visualization.md`
- APR-007 register/decision/source evidence
- `services/presentation/relationship_visualization.py`
- `services/presentation/relationship_web.py`
- `scripts/validate_m2_relationship_visualization.py`
- interaction with the accepted `RelationshipGraphView` contract

Explicitly out of scope:

- final frontend framework selection
- large interactive graphs
- force-directed layout
- drag/pan/zoom
- graph editing
- browser-side graph analytics
- operational/geospatial tracking

## Required Invariants

1. Visualization consumes `RelationshipGraphView` and never queries canonical storage directly.
2. No visual node/edge may be invented beyond the supplied graph.
3. Every material edge remains backed by at least one `supports` Evidence citation.
4. SDA IDs remain public identity; backend Q/P IDs do not leak.
5. Layout/output is deterministic for the same graph regardless of input-array order.
6. Arabic and English use the same graph identity and localize visible node/relation labels.
7. Canonical relation codes remain available in the semantic fallback for auditability.
8. SVG has an accessible title/description and graph-scoped DOM IDs.
9. A semantic HTML fallback exposes relationships, source-record identity, and citation links.
10. The JSON API returns the accepted public graph unchanged.

## Findings Register

### M2-VIS-F01 — Renderer initially accepted any non-empty citation set

**Area:** provenance / publication safety

**Finding:** The first renderer required citations but did not independently require a `supports` role.

**Why it matters:** A malformed-but-presented graph could visually assert a relationship backed only by contextualizing/contradicting Evidence.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Every visualized edge must contain at least one `supports` citation; regression coverage changes an edge to contextual-only and requires fail-closed rejection.

---

### M2-VIS-F02 — Static SVG title/marker IDs could collide with multiple figures

**Area:** accessibility / DOM correctness

**Finding:** Initial `<title>`, `<desc>`, and marker IDs were global constants.

**Why it matters:** Multiple graphs on one page could produce duplicate DOM IDs and incorrect `aria-labelledby`/marker references.

**Severity:** Medium

**Confidence:** High

**Disposition:** FIXED. SVG accessibility/marker IDs are deterministically scoped from the sorted root SDA IDs.

---

### M2-VIS-F03 — Arabic visualization initially exposed English predicate/role codes as visible edge labels

**Area:** bilingual presentation

**Finding:** Node labels were localized, but edge text displayed canonical predicate/role codes directly.

**Why it matters:** The graphic would not be meaningfully bilingual even though the surrounding route was Arabic.

**Severity:** High

**Confidence:** High

**Disposition:** FIXED. Known M2 predicates/roles use explicit Arabic/English presentation labels in the SVG/fallback. The canonical relation code remains present in the HTML fallback for auditability and does not change graph semantics.

---

### M2-VIS-F04 — First visualization should not force a general graph runtime

**Area:** architecture / dependency scope

**Finding:** Cytoscape.js and D3 are capable graph/visualization mechanisms, but the current accepted graph is intentionally bounded and does not require physics layout or rich client interaction.

**Why it matters:** Selecting a general graph runtime now would expand dependency/interaction surface before a forcing function exists.

**Severity:** Architectural decision

**Confidence:** High

**Disposition:** ADDRESSED BY ADR-0003 / APR-007. Project-owned deterministic inline SVG is trial-authorized for this bounded M2 role. Cytoscape.js/D3 remain candidates when explicit scale/interaction forcing functions arise.

## Failure and Trust Review

The renderer fails closed when:

- graph scope/root nodes are missing;
- nodes/edges are malformed or duplicate;
- an edge references a missing node;
- an edge lacks canonical source-record identity;
- an edge has no citations;
- an edge has no supporting Evidence citation.

The visualization does not mutate the graph or canonical knowledge. The public relationship API returns the provided `RelationshipGraphView` unchanged.

## Areas Reviewed With No Material Issue Found

- Node/edge ordering is deterministic.
- Root/Event/related-entity column placement is deterministic.
- HTML/SVG output escapes graph/source strings before markup insertion.
- Visible citations remain in the semantic fallback.
- Arabic route uses RTL document direction; English uses LTR.
- Canonical relationship codes remain visible for auditability without becoming user-facing labels in the SVG.
- No Q/P identifiers or backend mapping fields are intentionally rendered.
- No geographic/live operational field is introduced.

## Deferred / Non-Blocking Work

1. The visualization WSGI shell is deliberately separate from final frontend composition; framework/router integration remains a later decision.
2. Long labels may eventually require wrapping/truncation rules; the current bounded fixture does not justify a layout engine.
3. Pan/zoom/drag and dynamic client filtering remain forcing functions for a new APR comparison, not implicit backlog for this renderer.
4. Large-graph readability is explicitly outside the APR-007 claim ceiling.

## First-Pass Judgment

After M2-VIS-F01 through M2-VIS-F03 fixes and the explicit APR-007 bounded-trial decision, no first-pass merge-blocking defect remains. Promotion from trial to accepted/verified remains gated on exact-head schema validation plus the existing Wikibase regression gate.
