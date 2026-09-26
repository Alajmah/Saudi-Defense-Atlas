# ADR-0003 — First Relationship Visualization

- status: ACCEPTED — VERIFIED for bounded M2 role
- date: 2026-09-26
- milestone: M2
- pattern: APR-007

## Context

M2 has a verified backend-neutral `RelationshipGraphView` containing bounded Entity/Event nodes, explicit Claim/Event edges, timeline records, and Evidence -> Document -> Source citations. The roadmap requires a first relationship visualization, but the project has not selected a frontend framework or graph-visualization dependency.

The first visualization must not create a second truth store, infer additional relationships, leak Wikibase Q/P identity, or force a general graph engine before graph scale/interaction requires one.

## Forcing function

Deliver one useful, bilingual, accessible visualization of the already-bounded relationship graph while preserving deterministic tests and framework neutrality.

## Options characterized

### Option A — Project-owned deterministic inline SVG + HTML fallback

Mechanism:

- consume `RelationshipGraphView` directly;
- deterministic layered layout for the bounded graph;
- inline SVG with `<title>` / `<desc>` and visible text labels;
- semantic HTML relationship list below the graphic as the accessible/provenance fallback;
- no client-side graph runtime.

Benefits:

- no third-party dependency or frontend-framework lock-in;
- deterministic rendering suitable for exact regression tests;
- browser-native DOM/SVG output;
- easy Arabic/English labels and document direction handling;
- keeps layout strictly downstream of the canonical graph contract.

Liabilities:

- project owns the small layout/rendering code;
- unsuitable as-is for large graphs, free-form exploration, physics layout, advanced pan/zoom, compound nodes, or high interaction density.

### Option B — Cytoscape.js

Official documentation characterizes Cytoscape.js as a fully featured pure-JavaScript graph visualization/analysis library, MIT licensed, with no external dependencies and browser/module-system support.

Benefits:

- mature graph-specific renderer and interaction model;
- strong future fit for larger interactive graphs.

Liabilities for the current forcing function:

- adds a graph engine and runtime dependency before the current bounded graph requires it;
- creates more styling/layout integration work while frontend-framework selection is intentionally deferred;
- raises the test surface for a first visualization whose data contract is already bounded and deterministic.

### Option C — D3 (selection + force modules)

Official D3 documentation provides DOM data joins/selections and `d3-force` simulations that can render into SVG or Canvas.

Benefits:

- very flexible data-driven visualization toolkit;
- appropriate when custom interactive layouts become a core requirement.

Liabilities for the current forcing function:

- greater mechanism surface than needed for a small deterministic relationship slice;
- force simulation introduces layout dynamics we do not need for the first acceptance proof;
- would require more project-owned interaction/layout decisions than plain SVG while still adding a dependency.

## Decision

Accept **Option A: project-owned deterministic inline SVG + semantic HTML fallback** for the bounded M2 relationship-visualization role.

This decision does **not** reject Cytoscape.js or D3 for later milestones. It deliberately avoids promoting a general graph runtime before evidence requires one.

## Adopted invariants

1. The visualization consumes `RelationshipGraphView`; it does not query Wikibase or canonical records directly.
2. It never adds inferred nodes or edges.
3. Node/edge order and coordinates are deterministic for identical graph input.
4. SDA IDs remain identity; Q/P IDs never appear.
5. Arabic and English use the same graph identity/data, with localized visible node and relationship labels.
6. Canonical relationship codes remain available in the semantic fallback for auditability.
7. The SVG has an accessible title/description with graph-scoped DOM IDs and the page includes an HTML relationship fallback.
8. Every material rendered edge requires at least one supporting Evidence citation.
9. Citations/provenance remain available in the HTML fallback; the graphic is not treated as self-authenticating evidence.
10. No live operational geography or movement semantics are introduced.

## Accepted scope

- bounded one-root M2 procurement/exercise graph;
- server-rendered/static inline SVG;
- desktop/mobile responsive `viewBox`;
- bilingual node and relationship labels;
- semantic cited fallback;
- no client-side force simulation;
- no drag/pan/zoom requirement;
- no graph editing.

## Promotion / replacement forcing functions

Re-evaluate Cytoscape.js, D3, or another mechanism if one or more become real requirements:

- sustained graphs above roughly 100 visible nodes/edges where deterministic layered layout becomes unreadable;
- interactive pan/zoom/drag as a product requirement;
- compound/grouped nodes;
- user-driven topology filtering with frequent client-side relayout;
- graph-analysis algorithms in the browser;
- layout quality that cannot be maintained with bounded deterministic rules.

These are forcing functions, not automatic migration triggers; a new APR comparison is required.

## Verification evidence

The bounded trial passed on implementation/review head `b78564fa83bf128803205bc2a22ea88a8284ecb2`:

- schema-validation run `36260932930` / run #395 — **PASS**;
- Wikibase regression run `36260932947` / run #124 — **PASS**;
- exhaustive first-pass review: `docs/reviews/M2_RELATIONSHIP_VISUALIZATION_FIRST_PASS.md`;
- validation covers deterministic rendering under reordered input, supporting-Evidence enforcement, localized relation labels, canonical relation-code fallback, graph-scoped SVG accessibility IDs, bilingual routes, unchanged graph JSON API, and Q/P leakage rejection.

## External evidence inspected

- MDN, SVG in HTML: https://developer.mozilla.org/en-US/docs/Web/SVG/Guides/SVG_in_HTML
- MDN, SVG `<title>`: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/title
- MDN, SVG `<desc>`: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/desc
- Cytoscape.js official documentation: https://js.cytoscape.org/
- D3 `d3-force`: https://d3js.org/d3-force
- D3 `d3-selection`: https://d3js.org/d3-selection

## Claim ceiling

Verification establishes suitability for the first bounded M2 relationship visualization only. It does not establish suitability for large-scale interactive graph exploration or select the final frontend stack.
