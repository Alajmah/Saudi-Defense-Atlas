# M1 Public Projection — Increment E

## Status

**Phase:** read-model contract implementation started

**Branch:** `m1/public-projection-f15sa`

**Goal:** project-owned canonical read adapter → backend-neutral EquipmentView → read API → Arabic/English public F-15SA page.

This increment completes the public/read half of M1. It must not create a second factual truth store.

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
read API
        ↓
Arabic + English public page
```

The public layer must not depend on Wikibase Q/P identifiers or raw snaks. SDA IDs and SDA domain records are the application contract.

## Public projection invariants

1. A material public fact is rendered only from an admitted SDA Claim in `active` or `disputed` state.
2. Every rendered material Claim/Event must resolve a complete Evidence → Document → Source chain.
3. Missing provenance is a projection error, not permission to publish an uncited value.
4. `withdrawn` and `superseded` Claims are not presented as current public facts.
5. `disputed` Claims remain visibly disputed; the projector must not flatten them to known truth.
6. Absence of an admitted Claim is rendered as explicit `unknown`, not inferred from unrelated events or backend statements.
7. A delivery Event is not an inventory quantity, service-state, readiness, current-location, or timeless operator assertion.
8. Arabic and English labels are projections of the same SDA Entity ID.
9. Backend identifiers are adapter metadata and must not leak into the public read model.
10. Arbitrary legacy/test Wikibase statements are not public facts. The reader supplies SDA canonical Claim/Event records to the projector rather than enumerating raw backend statements indiscriminately.
11. The public view remains non-operational: no live locations, readiness, stock levels, patrol patterns, or other restricted operational detail is introduced by projection.

## First contract: `EquipmentView`

The initial schema is `schemas/v0.1/equipment-view.schema.json`.

It contains:

- SDA equipment Entity identity and bilingual labels;
- language-grouped aliases;
- explicit field states for manufacturer, operator, inventory quantity, and service state;
- generic presented Claims with direction and confidence;
- dated Events with participant roles;
- citation objects carrying Evidence, Document, Source, source class, URL, and locator;
- related SDA Entities;
- provenance record IDs and project Revision IDs.

The field-state model deliberately distinguishes:

- `known` — at least one admitted supporting Claim exists;
- `disputed` — a relevant admitted Claim is explicitly disputed;
- `unknown` — no admitted canonical Claim establishes the field.

For the bounded F-15SA slice, manufacturer is established by the admitted Boeing manufacturer Claim. Operator, inventory quantity, and service state remain `unknown` unless separate admitted Claims establish them. The dated final-delivery Event does not fill those fields.

## Validation target

`scripts/validate_m1_equipment_view.py` proves the first pure projection before any frontend framework is introduced. It verifies:

- bilingual identity from one SDA Entity;
- inbound manufacturer Claim rendering;
- full Claim citation traceability;
- delivery Event separation and participant roles;
- explicit unknown operator/inventory/service-state fields;
- related Entity projection;
- no backend-identifier leakage;
- fail-closed behavior for unresolved Evidence;
- withdrawal exclusion;
- disputed-Claim presentation.

## Next increments

After this pure contract is green:

1. implement a project-owned Wikibase read adapter that reconstructs canonical SDA records rather than exposing raw Q/P/snaks;
2. run the EquipmentView projector against the clean-stack records written by the M1 canonical-write workflow;
3. expose the typed view through a minimal read API by SDA ID;
4. create Arabic and English F-15SA routes from the same API result;
5. add visible citation/source UI and a delivery timeline snippet;
6. run the M1 acceptance checklist and exhaustive review before declaring M1 complete.

Open M1-F15 (concurrent-writer uniqueness) does not block this read-only increment, but production automated canonical writers remain unauthorized until it is resolved.
