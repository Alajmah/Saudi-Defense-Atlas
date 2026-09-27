# APR-009 — MapLibre GL JS as bounded public-map browser renderer

- pattern_status: ACCEPTED
- implementation_status: VERIFIED
- planning_disposition: current-plan-authorized
- date: 2026-09-27
- authority: `docs/adr/ADR-0005-public-map-renderer-trial.md`

## Problem

M3 requires an interactive public atlas map without allowing a browser renderer, tile provider, or map-library data model to become geographic authority or bypass the accepted non-operational `PublicMapView` boundary.

## Invariant

The renderer consumes `PublicMapView` only. It never receives raw/canonical geography, movement Events, backend Q/P identity, or geography outside the fixed-public-facility publication policy. Tile/basemap providers and geocoders remain separate architectural decisions.

## Mechanism

- MapLibre GL JS `6.11.2` as the browser renderer;
- project-owned deterministic `PublicMapView -> GeoJSON` adapter;
- project-owned semantic HTML fallback preserving bilingual labels and supporting Evidence/Document/Source identity;
- provider-independent verified style containing only the project-owned `sda-public-facilities` GeoJSON source.

## Alternatives characterized

- **Leaflet** — remains a viable fallback with a smaller conventional map API; not rejected.
- **Project-owned SVG/HTML geographic renderer** — avoids a map dependency but would recreate pan/zoom, projection, hit-testing, clustering, and vector-style infrastructure; retained for bounded non-geographic diagrams rather than adopted for atlas navigation.

## Benefits verified

- real browser/WebGL rendering in headless Chromium;
- direct GeoJSON consumption from the accepted public projection;
- future path to styled/filterable vector layers without changing canonical geography authority;
- renderer remains separable from tile provider and geocoder;
- Arabic and English semantic fallback retained;
- zero external network dependency in the bounded trial.

## Liabilities retained

- larger browser/runtime surface than Leaflet;
- WebGL/browser compatibility becomes an operational concern;
- production CSP/security, performance, accessibility, offline packaging, tile-provider behavior, and frontend integration remain separately unqualified.

## Failure modes reviewed

- raw or higher-precision geography bypassing `PublicMapView`;
- non-public category/scope admission;
- malformed or duplicated public identity arrays being silently normalized;
- Q/P/backend identifier leakage;
- citation count without Evidence identity;
- Arabic/English fallback loss;
- external tile/provider coupling appearing implicitly;
- installed renderer version drifting from declared evidence;
- renderer input ordering changing the project-owned payload.

## Forcing function

`docs/ROADMAP.md` M3 requires a public non-operational map and explicitly requires separate APR evidence before selecting a map/rendering mechanism.

## Decision history

### APRD-011 — Authorize bounded MapLibre renderer trial

- from_status: CANDIDATE
- to_status: TRIAL-AUTHORIZED
- implementation_status: IN-TRIAL
- scope: MapLibre `6.11.2` rendering of synthetic `PublicMapView`-derived fixed-facility GeoJSON in headless Chromium.
- non_scope: tile/basemap provider, geocoder, production deployment/security, frontend framework, operational geography.
- verification_plan: deterministic adapter tests plus a local-only browser trial requiring expected feature rendering, bilingual semantic fallback, exact installed version, and zero external network requests.

### APRD-012 — Promote after bounded verification

- from_status: TRIAL-AUTHORIZED
- to_status: ACCEPTED
- implementation_status_from: IN-TRIAL
- implementation_status_to: VERIFIED
- evidence: implementation/review head `3da37e060dc9b44b30474ea2444f57d7d2b63eda`; schema-validation run `36334373812` (#516) PASS; MapLibre verification run `36334373823` (#11) PASS; artifact `m3-maplibre-trial-evidence`; `docs/reviews/M3_MAPLIBRE_TRIAL_FIRST_PASS.md`.
- rationale: the hardened trial demonstrated real browser rendering while preserving the SDA public-geography authority boundary and provider independence.

## Implementation links

- `services/presentation/map_geojson.py`
- `scripts/validate_m3_map_renderer_payload.py`
- `scripts/emit_m3_maplibre_fixture.py`
- `spikes/maplibre/`
- `.github/workflows/maplibre-verification.yml`
- `docs/adr/ADR-0005-public-map-renderer-trial.md`
- `docs/reviews/M3_MAPLIBRE_TRIAL_FIRST_PASS.md`

## Source ledger addendum

External primary evidence inspected 2026-09-27:

- MapLibre GL JS official repository and package metadata — renderer scope, current package structure, BSD-3-Clause license;
- MapLibre GL JS release `v6.11.2` — current trial version and release date;
- Leaflet official repository/package metadata — mobile-friendly interactive-map library, BSD-2-Clause;
- Leaflet stable release `v1.9.4` and project FAQ — stable version evidence and explicit separation between Leaflet and map imagery/tile services.

External evidence characterizes mechanisms only; adoption authority comes from the project trial, review, ADR, and roadmap forcing function.

## Replacement / expansion forcing functions

A new APR is required for:

- tile/basemap provider selection;
- geocoder selection;
- production CSP/security or offline-map topology;
- target-scale performance qualification;
- frontend integration that materially changes the renderer authority boundary;
- any geography outside the accepted `PublicMapView` scope;
- demonstrated runtime/operational complexity that makes Leaflet or another renderer preferable.

## Claim ceiling

`VERIFIED` means only that MapLibre GL JS `6.11.2` satisfies the tested bounded M3 renderer contract over already-public, already-coarsened `PublicMapView` data. It does not qualify production deployment and does not authorize operational or precise non-public geography.