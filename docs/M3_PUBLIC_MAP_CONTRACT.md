# M3 Public Non-Operational Map Contract

## Purpose

Define a backend-neutral public map projection before selecting any map library, tile provider, geocoder, or frontend framework.

The map is a **publication view over canonical SDA records**, not a second location database.

## Accepted scope for this increment

Only fixed facilities with an explicitly allowlisted public category may become map features:

- `air_base`
- `naval_base`
- `military_city`
- `training_center`
- `military_education`
- `defense_industry_facility`
- `administrative_facility`

The first contract deliberately excludes mobile/temporary/operational subtypes such as unit positions, deployments, patrol locations, air-defense sites, radar sites, command posts, ammunition/fuel storage, or other tactical sub-facility locations.

## Canonical inputs

The projection consumes canonical `Entity`, `Claim`, `Evidence`, `Document`, and `Source` records.

The bounded location vocabulary is:

- `facility.public_latitude`
- `facility.public_longitude`
- `facility.public_location_label`
- existing `facility.associated_with.organization`

Latitude and longitude remain ordinary sourced Claims. No map-specific truth store owns coordinates.

## Publication guards

A public map feature is admitted only when:

1. the subject is an active `facility` Entity;
2. its subtype is in the allowlist above;
3. exactly one eligible active latitude Claim and one eligible active longitude Claim exist;
4. both coordinate Claims are `high` or `verified` confidence;
5. each material Claim resolves through at least one `supports` Evidence link to Document and Source;
6. disputed coordinate Claims fail closed;
7. incomplete or duplicate coordinate pairs fail closed;
8. public output coordinates are rounded to **two decimal places** before publication;
9. Wikibase Q/P identifiers never enter the public view.

The public coordinate object is marked:

```text
precision_class = coarsened_2dp
publication_policy = fixed_public_reference_only
```

The projector never accepts Events or movement observations as input, so live/temporal movement cannot become a map feature through this contract.

## Precision boundary

The public view does not reproduce source precision. Even when a source-backed coordinate is more precise, the map projection exposes only the two-decimal public reference.

This coarsening is a publication rule, not a claim that the facility itself is uncertain by exactly that distance.

## Unknowns and exclusions

If no eligible coordinate pair exists, the facility is absent from the map rather than guessed or geocoded automatically.

Medium/low/unverified coordinates are not published by this contract. A future geocoder or city-centroid mechanism requires a separate explicit contract and provenance rule.

## Architecture boundary

This increment does **not** select:

- Leaflet
- MapLibre GL JS
- Mapbox
- Google Maps
- a tile provider
- a geocoder
- a frontend framework

Those are presentation/infrastructure mechanisms and require separate APR evidence after this data/sensitivity contract is verified.

## Implementation

- schema: `schemas/v0.1/public-map-view.schema.json`
- projector: `services/presentation/public_map.py`
- validation: `scripts/validate_m3_public_map.py`

## Claim ceiling

Passing this contract proves only that the tested public read model enforces the declared fixed-facility, provenance, confidence, coarsening, and backend-ID boundaries. It does not qualify a map renderer/provider or authorize broader operational geography.
