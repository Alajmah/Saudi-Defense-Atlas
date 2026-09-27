# ADR-0005 — Public Map Renderer

- status: ACCEPTED / VERIFIED (bounded M3 role)
- date: 2026-09-27
- milestone: M3
- pattern: APR-009

## Context

M3 has an accepted public-map data/sensitivity boundary: only allowlisted fixed public facilities may enter `PublicMapView`; coordinates are already coarsened to two decimals; supporting Evidence is required; operational/movement geography is excluded. The renderer consumes that public projection rather than canonical/raw geography.

The next forcing function was an interactive atlas renderer. Renderer selection remains separate from tile-provider, geocoder, frontend-framework, and deployment decisions.

## Candidates characterized

### Option A — MapLibre GL JS 6.11.2

Primary evidence inspected on 2026-09-27:

- official MapLibre repository/release metadata identifies MapLibre GL JS as an open-source browser map renderer using GPU-accelerated vector-tile rendering;
- current release inspected: `6.11.2`, published 2026-09-24;
- license: BSD-3-Clause;
- package is an ES module and includes `bidi-js`, relevant to bidirectional text handling;
- style sources are configured separately from the renderer, allowing a provider-independent empty/local style during trial.

Strength for SDA: clear path from the current point-only map to future vector layers/filtering while keeping provider/style sources replaceable.

Liability: materially larger browser/runtime surface than Leaflet or project-owned SVG; production accessibility and tile/provider behavior remain separate work.

### Option B — Leaflet

Primary evidence inspected on 2026-09-27:

- official project describes Leaflet as a mobile-friendly interactive-map JavaScript library;
- stable release metadata identifies `1.9.4`; the `main` package currently identifies `2.0.0-alpha.1`;
- license: BSD-2-Clause;
- official FAQ explicitly separates Leaflet itself from map imagery/tile services.

Strength for SDA: smaller/simpler map API and strong fit for conventional markers/raster tiles.

Current disadvantage: the Atlas roadmap anticipates service/equipment/manufacturer/status filtering and richer styled vector layers; proving those future paths would require more plugin/composition decisions than MapLibre's native style/source model.

Leaflet is not rejected and remains a fallback if later evidence shows unacceptable MapLibre complexity.

### Option C — Project-owned SVG/HTML map

Strength: zero map-library dependency and deterministic server rendering.

Current disadvantage: implementing pan/zoom, geographic projection, clustering, vector styling, hit-testing, and responsive map interaction would recreate general mapping infrastructure. The project-owned SVG pattern remains accepted for bounded relationship diagrams, not automatically for geographic atlas navigation.

## Decision

Accept **MapLibre GL JS 6.11.2** as the bounded M3 browser renderer over `PublicMapView`.

`PublicMapView` remains the publication/sensitivity authority boundary. MapLibre is a rendering mechanism only and never receives raw/canonical geography in the accepted contract.

## Accepted invariants

1. The renderer accepts only `PublicMapView`-derived data.
2. Renderer data uses only already-coarsened public coordinates; raw/canonical geography is outside the adapter/browser contract.
3. SDA IDs remain identity; backend Q/P IDs are forbidden.
4. The adapter to GeoJSON is deterministic and rejects non-public scope, restricted categories, excess coordinate precision, malformed identity arrays, incomplete coordinate-Claim provenance, and records without supporting Evidence.
5. A semantic HTML fallback preserves bilingual names/location labels and supporting Evidence/Document/Source identity.
6. No tile provider, basemap provider, geocoder, or external map API is selected by this decision.
7. The verification browser makes zero external network requests; MapLibre assets and synthetic trial data are served locally.
8. The verified style has no external tile/vector/raster source.
9. Renderer numeric/style state does not become canonical geographic truth.
10. Live unit positions, movements, deployments, patrols, readiness, stocks, tactical sites, and unofficial precise operational coordinates remain outside the renderer contract.

## Verification evidence

Implementation/review head `3da37e060dc9b44b30474ea2444f57d7d2b63eda`:

- schema-validation run `36334373812` (#516) — PASS;
- MapLibre verification run `36334373823` (#11) — PASS;
- browser trial — PASS in headless Chromium;
- artifact `m3-maplibre-trial-evidence` uploaded;
- exhaustive first-pass: `docs/reviews/M3_MAPLIBRE_TRIAL_FIRST_PASS.md`.

The passing browser trial verified:

- deterministic `PublicMapView -> GeoJSON` adaptation;
- 2dp public precision and fail-closed higher precision;
- restricted/wrong-scope rejection;
- supporting Evidence identity in semantic fallback;
- Arabic and English labels;
- MapLibre canvas creation and expected public feature rendering;
- only the project-owned `sda-public-facilities` source in the style;
- no Q/P/backend identifier leakage;
- zero external browser network requests;
- installed MapLibre version exactly `6.11.2`.

Final merge remains gated on exact-head schema, MapLibre, and continuing Wikibase regression checks after governance documentation changes.

## Replacement / expansion forcing functions

A new APR is required for any of the following:

- tile/basemap provider selection;
- geocoder selection;
- production CSP/security policy;
- offline map packaging;
- production scale/performance qualification;
- frontend-framework integration that materially changes the renderer boundary;
- exposing geography outside the accepted `PublicMapView` scope;
- evidence that MapLibre runtime/operational cost materially exceeds its value.

## Non-scope / claim ceiling

This decision establishes suitability only for the bounded M3 browser renderer over `PublicMapView`. It does not select or qualify:

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
