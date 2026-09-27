# ADR-0005 — Public Map Renderer Trial

- status: TRIAL-AUTHORIZED
- date: 2026-09-27
- milestone: M3
- pattern: APR-009 (pending bounded verification)

## Context

M3 now has an accepted public-map data/sensitivity boundary: only allowlisted fixed public facilities may enter `PublicMapView`; coordinates are already coarsened to two decimals; supporting Evidence is required; operational/movement geography is excluded. The renderer must consume that public projection rather than canonical/raw geography.

The next forcing function is an interactive atlas renderer. Renderer selection must remain separate from tile-provider, geocoder, frontend-framework, and deployment decisions.

## Candidates characterized

### Option A — MapLibre GL JS 6.11.2

Primary evidence inspected on 2026-09-27:

- official MapLibre repository/release metadata identifies MapLibre GL JS as an open-source browser map renderer using GPU-accelerated vector-tile rendering;
- current release inspected: `6.11.2`, published 2026-09-24;
- license: BSD-3-Clause;
- package is an ES module and includes `bidi-js`, relevant to bidirectional text handling;
- style sources are configured separately from the renderer, allowing a provider-independent empty/local style during trial.

Strength for SDA: clear path from the current point-only map to future vector layers/filtering while keeping provider/style sources replaceable.

Liability: materially larger browser/runtime surface than Leaflet or project-owned SVG; WebGL/browser behavior requires an actual browser trial; production accessibility and tile/provider behavior remain separate work.

### Option B — Leaflet

Primary evidence inspected on 2026-09-27:

- official project describes Leaflet as a mobile-friendly interactive-map JavaScript library;
- stable release metadata still identifies `1.9.4`; the `main` package currently identifies `2.0.0-alpha.1`;
- license: BSD-2-Clause;
- official FAQ explicitly separates Leaflet itself from map imagery/tile services.

Strength for SDA: smaller/simpler map API and strong fit for conventional markers/raster tiles.

Current trial disadvantage: the Atlas roadmap anticipates service/equipment/manufacturer/status filtering and likely richer styled vector layers; proving those future paths would require more plugin/composition decisions than MapLibre's native style/source model.

Leaflet is not rejected and remains a fallback if the MapLibre trial shows unacceptable runtime complexity.

### Option C — Project-owned SVG/HTML map

Strength: zero map-library dependency and deterministic server rendering.

Current disadvantage: implementing pan/zoom, geographic projection, clustering, vector styling, hit-testing, and responsive map interaction would recreate general mapping infrastructure. The project-owned SVG pattern remains accepted for bounded relationship diagrams, not automatically for geographic atlas navigation.

## Trial decision

Authorize **MapLibre GL JS 6.11.2** for a bounded browser-executed M3 renderer trial only.

This is not yet adoption. `PublicMapView` remains the publication/sensitivity authority boundary.

## Trial invariants

1. The renderer accepts only `PublicMapView`-derived data.
2. Renderer data uses only already-coarsened public coordinates; no raw/canonical geography is available to the browser trial.
3. SDA IDs remain identity; backend Q/P IDs are forbidden.
4. The adapter to GeoJSON is deterministic and rejects non-public scope, restricted categories, excess coordinate precision, and records without supporting Evidence.
5. A semantic HTML fallback remains available for bilingual names/location labels and citation presence.
6. No tile provider, basemap provider, geocoder, or external map API is selected by this trial.
7. The browser trial must make zero external network requests; MapLibre assets and synthetic trial data are served locally.
8. The map style used for verification has no external tile/vector/raster source.
9. Renderer numeric/style state does not become canonical geographic truth.
10. Live unit positions, movements, deployments, patrols, readiness, stocks, tactical sites, and unofficial precise operational coordinates remain outside the renderer contract.

## Acceptance matrix

The trial must demonstrate:

- deterministic `PublicMapView -> GeoJSON` output independent of input ordering;
- public two-decimal coordinate precision is preserved and higher precision fails closed;
- restricted/non-public categories and wrong scope fail closed;
- supporting Evidence remains represented in the semantic fallback;
- Arabic and English labels are present in the browser-rendered page;
- MapLibre creates the map canvas and renders the expected public point feature in headless Chromium;
- only the project-owned `sda-public-facilities` GeoJSON source is present in the trial style;
- no Q/P/backend identifiers appear in the renderer payload/page;
- zero external browser network requests;
- exact MapLibre top-level version is pinned to `6.11.2` for the trial.

## Promotion gate

Promote APR-009 to `ACCEPTED / VERIFIED` only after:

1. the browser trial passes in CI on the exact reviewed head;
2. the normal schema/regression suite remains green;
3. first-pass review finds no unresolved publication-boundary, precision, provider-coupling, bilingual, or provenance violation.

Failure keeps MapLibre at `CANDIDATE`/`DEFERRED`; the project must not weaken `PublicMapView` to fit the renderer.

## Non-scope / claim ceiling

A passing trial establishes suitability only for the bounded M3 browser renderer over `PublicMapView`. It does not select or qualify:

- a tile/basemap provider;
- a geocoder;
- production CSP/security configuration;
- production performance/scale;
- offline map packaging;
- final frontend framework;
- final deployment topology;
- operational or precise non-public geography.

## External evidence inspected

- MapLibre GL JS official repository: https://github.com/maplibre/maplibre-gl-js
- MapLibre GL JS current release metadata: https://github.com/maplibre/maplibre-gl-js/releases/tag/v6.11.2
- MapLibre GL JS license: https://github.com/maplibre/maplibre-gl-js/blob/main/LICENSE.txt
- Leaflet official repository: https://github.com/Leaflet/Leaflet
- Leaflet stable release metadata: https://github.com/Leaflet/Leaflet/releases/tag/v1.9.4
- Leaflet FAQ / provider separation: https://github.com/Leaflet/Leaflet/blob/main/FAQ.md
