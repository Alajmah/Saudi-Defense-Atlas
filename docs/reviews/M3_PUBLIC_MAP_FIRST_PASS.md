# M3 Public Map Contract — Exhaustive First-Pass Review

**Date:** 2026-09-27  
**Milestone:** M3  
**Scope:** `public-map-view` schema, fixed-facility location predicates, public map projector, safety/publication boundary, and validation suite.  
**Decision scope:** data/publication contract only; no renderer, provider, geocoder, or frontend framework is selected here.

## Review disposition

**PASS after remediation.** No unresolved blocker remains in the bounded public-map data contract.

The accepted boundary is deliberately narrower than general geospatial publication: only explicitly allowlisted, fixed, publicly documented facility categories can be projected, and the projector has no Event/movement input path.

## Findings

### M3-MAP-F01 — Disputed optional metadata could suppress a safe fixed-facility feature — FIXED

The initial helper raised on any disputed facility metadata Claim, including optional `facility.public_location_label` and `facility.associated_with.organization` Claims.

**Risk:** a disputed label or association could remove/block an otherwise independently supported coordinate feature, conflating optional descriptive uncertainty with the map admission decision.

**Remediation:** coordinate disputes remain fail-closed. Disputed optional labels/associations are omitted from the public feature instead of invalidating the fixed-facility coordinate.

**Regression:** validation separately disputes an English location label and an organization association; the feature remains publishable while the disputed optional value is absent.

### M3-MAP-F02 — Association targets were not resolved against canonical Entity state — FIXED

The initial projector accepted the entity ID in `facility.associated_with.organization` without proving that the target exists and remains an active `organization` Entity.

**Risk:** stale, missing, or mistyped references could enter the public map as apparently valid organizational relationships.

**Remediation:** every eligible public association target must resolve to an active canonical Entity whose `entity_type` is `organization`; otherwise projection fails closed.

**Regression:** missing, facility-typed, and inactive organization targets are rejected.

### M3-MAP-F03 — Facility-only association predicates on non-facility subjects could be silently ignored — FIXED

The initial cross-record subject guard covered public latitude/longitude/location-label predicates but not `facility.associated_with.organization`.

**Risk:** malformed canonical semantics could disappear silently from the public projection instead of being surfaced as an integrity error.

**Remediation:** all map-relevant facility predicates, including the association predicate, require a canonical `facility` subject before projection proceeds.

**Regression:** an organization subject carrying the facility association predicate is rejected fail-closed.

## Areas reviewed with no unresolved finding

- Only active `facility` Entities are eligible.
- Facility subtype is explicitly allowlisted; tactical/operational fixture subtype `air_defense_site` is excluded.
- The projector accepts no Event/movement input, preventing live deployment/movement observations from becoming map features through this contract.
- Latitude/longitude require active `high` or `verified` Claims.
- Exactly one eligible latitude and longitude Claim are required; incomplete or duplicate eligible pairs fail closed.
- Disputed coordinate Claims fail closed.
- Every published material Claim resolves through at least one `supports` Evidence link to Document and Source.
- Source coordinates are coarsened before public output; the tested source precision does not survive into the map view.
- Public coordinate metadata explicitly declares `coarsened_2dp` and `fixed_public_reference_only`.
- Broad Arabic/English public location labels remain optional, cited metadata.
- Medium/low/unverified coordinates are not admitted.
- Backend Wikibase Q/P identifiers do not enter the public view.
- Provenance records retain SDA Entity/Claim/Evidence/Document/Source and Revision identifiers.
- No automatic geocoding, coordinate inference, or city-centroid substitution is authorized.
- No map rendering library, tile provider, geocoder, frontend framework, or deployment topology is selected by this increment.

## Safety/publication boundary

The contract is for public reference geography of fixed facilities only. It does not authorize publication or aggregation of:

- live or changing unit positions;
- deployment/return timing;
- patrol patterns;
- readiness;
- ammunition/fuel stocks;
- tactical air-defense/radar/command-post locations;
- unofficial precise operational coordinates;
- movement-derived or inferred geography.

A broader geography requirement requires a new explicit contract and review rather than extending this allowlist implicitly.

## Claim ceiling

A passing implementation proves only that the tested projection enforces the declared fixed-facility allowlist, canonical provenance, confidence rules, coordinate coarsening, cross-record integrity, and backend-ID boundary.

It does not qualify a map renderer/provider, production security, production hosting, geocoder, richer geography, or any operational-location product.
