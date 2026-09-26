# M1 Public Projection — Increment E

## Status

**Phase:** implementation complete; merge gated by exact-head CI and PR review.

**Branch:** `m1/public-projection-f15sa`

**Goal:** project-owned canonical read adapter → backend-neutral EquipmentView → read API → Arabic/English public F-15SA page.

This increment completes the public/read half of M1 without creating a second factual truth store.

## Architectural boundary

```text
Wikibase canonical backend
        ↓
SDA canonical read adapter
        ↓
Entity / Claim / Event / Evidence / Document / Source records
        ↓
EquipmentView projector
        ↓
framework-neutral read API / web shell
        ↓
Arabic + English public page
```

The public layer does not depend on Wikibase Q/P identifiers or raw snaks. SDA IDs and SDA domain records are the application contract. A production frontend framework and deployment topology remain subject to the Architecture Pattern Register rather than being silently adopted in M1.

## Public projection invariants

1. A material public fact is rendered only from an admitted SDA Claim in `active` or `disputed` state.
2. Every rendered material Claim/Event must resolve a complete Evidence → Document → Source chain.
3. Every rendered material Claim/Event requires at least one Evidence link with role `supports`; contextualizing or contradictory evidence alone cannot establish a publishable fact.
4. Missing provenance is a projection error, not permission to publish an uncited value.
5. `withdrawn` and `superseded` Claims are not presented as current public facts.
6. `disputed` Claims remain visibly disputed; the projector does not flatten them to known truth.
7. Absence of an admitted Claim is rendered as explicit `unknown`, not inferred from unrelated events or backend statements.
8. A delivery Event is not an inventory quantity, service-state, readiness, current-location, or timeless operator assertion.
9. Arabic and English labels are projections of the same SDA Entity ID.
10. Backend identifiers are adapter metadata and do not leak into the public read model or HTML.
11. Arbitrary legacy/test Wikibase statements are not public facts. The reader consumes only current SDA-projected Claim/Event records.
12. Canonical payload integrity and public read-projection integrity are distinct contracts. `read_projection_sha256` validates the exact subset reconstructed by the public reader; it is not an alias for canonical `payload_sha256`.
13. The public view remains non-operational: no live locations, readiness, stock levels, patrol patterns, or other restricted operational detail is introduced by projection.

## EquipmentView contract

`schemas/v0.1/equipment-view.schema.json` defines the backend-neutral public equipment view. It contains:

- SDA equipment Entity identity and bilingual labels;
- language-grouped aliases;
- explicit field states for manufacturer, operator, inventory quantity, and service state;
- presented Claims with direction and confidence;
- dated Events with participant roles;
- citation objects carrying Evidence, Document, Source, source class, URL, and locator;
- related SDA Entities;
- provenance record IDs and project Revision IDs.

The field-state model distinguishes:

- `known` — at least one admitted supporting Claim exists;
- `disputed` — a relevant admitted Claim is explicitly disputed;
- `unknown` — no admitted canonical Claim establishes the field.

For the bounded F-15SA slice, manufacturer is established by the admitted Boeing manufacturer Claim. Operator, inventory quantity, and service state remain `unknown`. The dated final-delivery Event does not fill those fields.

## Implemented read path

The project-owned Wikibase adapter reconstructs current SDA Entity/Claim/Event/Evidence/Document/Source records. Legacy M0 trial statements lacking current SDA projection markers are excluded. Entity and Event public-read metadata use an explicit read-projection version and `read_projection_sha256` integrity marker.

The framework-neutral web shell exposes:

- `GET /api/equipment/SDA-EQUIP-F15SA` — the exact typed `EquipmentView` JSON;
- `GET /ar/equipment/f-15sa` — Arabic RTL rendering;
- `GET /en/equipment/f-15sa` — English LTR rendering.

Both localized pages derive from the same canonical EquipmentView and show localized manufacturer, explicit unknown fields, visible citations, the delivery timeline, related entities, and language switching.

## Verification

Static CI validates:

- schema validity;
- pure EquipmentView behavior;
- strict Evidence → Document → Source citation resolution;
- mandatory supporting Evidence for material facts/events;
- canonical-vs-read hash separation;
- withdrawn/disputed Claim behavior;
- SDA-ID API behavior;
- Arabic/English rendering and localized manufacturer;
- explicit unknowns;
- citation/timeline visibility;
- backend Q/P identifier exclusion.

Clean-stack Wikibase verification additionally reconstructs the EquipmentView from canonical backend state, renders the API/Arabic/English outputs, and uploads those generated artifacts as verification evidence.

## Qualification boundary

M1-F15 concurrent-writer canonical-ID uniqueness remains open. It does not block this read-only public increment, but production automated canonical mutation workers remain unauthorized until a project-owned coordination/uniqueness mechanism is selected and independently verified.
