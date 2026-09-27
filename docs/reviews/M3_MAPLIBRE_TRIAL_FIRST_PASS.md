# M3 MapLibre Trial — Exhaustive First Pass

**Date:** 2026-09-27  
**Scope:** `m3/map-renderer-evaluation` bounded renderer trial over the already-accepted `PublicMapView` boundary.  
**Decision under review:** ADR-0005 / APR-009 candidate MapLibre GL JS renderer.

## Review disposition

**PASS after remediation** for the bounded trial implementation. No unresolved blocker remains in the reviewed renderer/publication-boundary surface.

The review does **not** qualify production security, a tile/basemap provider, geocoder, deployment topology, frontend framework, offline packaging, operational geography, or raw/canonical geographic access.

## Areas reviewed

- renderer authority boundary (`PublicMapView` only);
- public coordinate precision and scope admission;
- deterministic GeoJSON adaptation;
- canonical SDA identity versus backend identity;
- Evidence/Document/Source trace retained in semantic fallback;
- malformed cross-record/public-projection metadata behavior;
- Arabic/English fallback content;
- renderer/runtime version pinning;
- provider coupling and browser network behavior;
- headless-browser rendering proof;
- regression interaction with M0–M3 validation suites.

## Findings fixed before promotion

### M3-MAPLIBRE-F01 — Malformed organization IDs could be silently dropped

**Risk:** the renderer adapter initially normalized `associated_organization_ids` by filtering invalid values. A malformed upstream public projection could therefore be partially accepted instead of failing closed.

**Fix:** renderer ID arrays now validate every entry, reject duplicates, and fail closed on malformed IDs. Coordinate Claim provenance is also required as exactly two unique IDs.

**Regression:** `scripts/validate_m3_map_renderer_payload.py` covers malformed/duplicate organization IDs and incomplete coordinate-Claim provenance.

### M3-MAPLIBRE-F02 — Semantic fallback preserved citation count but not Evidence identity

**Risk:** an accessible/non-canvas presentation could state that citations existed without exposing which Evidence/Document/Source supported the map feature.

**Fix:** semantic fallback now renders supporting Evidence identity with linked Document/Source identity metadata and optional source URL.

**Regression:** browser trial asserts `SDA-EVID-TRIAL-MAP`, `SDA-DOC-TRIAL-MAP`, and `SDA-SOURCE-TRIAL-MAP` survive into the fallback.

### M3-MAPLIBRE-F03 — Trial evidence hard-coded the renderer version

**Risk:** CI output could claim MapLibre `6.11.2` even if dependency resolution installed another version.

**Fix:** the trial reads the installed `node_modules/maplibre-gl/package.json`, fails on a version mismatch, and emits the inspected runtime package version.

**Regression:** browser trial asserts exact installed version `6.11.2` before launching the map.

## No-issue findings

- `PublicMapView` remains the only geographic input to the renderer adapter.
- No Claim/Event/canonical geography reader is available to the browser trial.
- Higher-than-2dp coordinate input fails closed at the adapter boundary.
- Restricted facility categories and wrong map scope fail closed.
- Backend `Q/P` identifier leakage is rejected.
- GeoJSON output is deterministic under input reordering.
- MapLibre trial style contains no tile/vector/raster provider source.
- Browser verification permits only localhost/data/blob requests and fails on any external request.
- Arabic and English names/location labels remain available in semantic fallback.
- Tile provider and geocoder remain explicitly undecided.

## Implementation evidence before governance promotion

Implementation/review head: `3da37e060dc9b44b30474ea2444f57d7d2b63eda`.

- schema-validation run `36334373812` (#516) — **PASS**;
- MapLibre verification run `36334373823` (#11) — **PASS**;
- MapLibre browser step — **PASS**;
- artifact: `m3-maplibre-trial-evidence` uploaded by the passing trial.

The Wikibase regression gate was still a separate continuing regression job when this first-pass record was frozen; promotion/merge remains gated on its successful conclusion plus final exact-head reruns after governance documentation.

## Claim ceiling

The evidence supports only this statement:

> MapLibre GL JS 6.11.2 can render the bounded SDA public fixed-facility projection in a real headless browser while remaining downstream of `PublicMapView`, without a selected tile provider/geocoder or external browser network dependency in the trial.

It does not establish production readiness or authorize any broader geography.