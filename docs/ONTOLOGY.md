# Ontology v0.1

## Purpose

This document defines the initial conceptual model for Saudi Defense Atlas. It describes domain meaning, not database tables. Storage technology may change while this contract remains stable.

## Core Primitives

### Entity

A stable identity for a real-world or conceptual thing.

Required fields:

- `id`
- `entity_type`
- `name_ar`
- `name_en`
- `aliases[]`
- `status`

Optional fields may include descriptions, external identifiers, parent entity, and editorial metadata.

### Claim

A sourced assertion about an entity or relationship.

Conceptually:

```text
subject --predicate--> value/object
```

A claim may include:

- qualifiers
- valid-from / valid-to
- point-in-time
- precision
- confidence
- status
- one or more evidence records

### Evidence

A specific piece of source material supporting, contradicting, or contextualizing a claim.

Minimum fields:

- source
- source locator or URI
- publication date when known
- retrieved date
- evidence role: `supports | contradicts | contextualizes`
- excerpt or structured locator where legally appropriate
- content fingerprint

### Source

The publisher/origin of evidence, including authority class and metadata.

### Event

A dated occurrence that may change knowledge state or connect entities, for example contract award, announced procurement, delivery, exercise participation, upgrade, opening, retirement, or localization agreement.

### Relationship

A typed connection between entities. A relationship requiring factual support is represented as or backed by a claim.

### Revision

An immutable record of a knowledge change, including who/what proposed it, who/what approved it, timestamps, and rationale.

## Entity Types v0.1

### Organization

- ministry
- armed forces / service branch
- command
- military organization
- government agency
- defense company
- manufacturer
- educational/training institution

### MilitaryUnit

Used only where the unit is publicly documented and inclusion satisfies publication policy.

### Equipment

Parent concept for military systems and materiel.

Subtypes:

- aircraft
- helicopter
- unmanned system
- missile
- air-defense system
- radar/sensor
- electronic-warfare system
- C4ISR system
- armored vehicle
- artillery system
- small arm where editorially relevant
- naval vessel/class
- support vehicle/system
- munition

### EquipmentVariant

A specific model/variant, separated from the equipment family when facts differ materially by variant.

### Facility

Only publicly documented facilities represented at a non-operational level appropriate to project policy.

Subtypes:

- air base
- naval base
- military city
- training facility
- academy
- defense-industry facility

### Exercise

A named exercise or training event/series.

### ProcurementProgram

Tracks acquisition lifecycle independently of news articles.

### Contract

A documented contract or award. A government approval/notification is not automatically a contract.

### LocalizationProgram

Industrial participation, local manufacture, technology transfer, MRO, or other documented localization initiative.

### Country

Used for manufacturers, suppliers, exercise participants, and government-to-government relationships.

### Document

A source artifact such as an official release, contract notice, report, PDF, manufacturer announcement, or specialist publication.

## Key Predicates v0.1

Representative relationships include:

```text
organization.parent_of.organization
organization.operates.equipment_variant
military_unit.part_of.organization
military_unit.operates.equipment_variant
manufacturer.manufactures.equipment
company.participates_in.procurement_program
equipment_variant.variant_of.equipment
procurement_program.acquires.equipment_variant
contract.part_of.procurement_program
contract.awarded_to.company
exercise.participant.organization
exercise.uses.equipment_variant
localization_program.related_to.equipment
facility.associated_with.organization
```

Predicates must be centrally registered; arbitrary free-text predicates are not allowed in canonical data.

## Procurement State Machine

Use explicit states to prevent the common error of treating an approval as a delivery:

```text
rumored
  ↓
under_evaluation
  ↓
announced_or_requested
  ↓
approved_or_notified
  ↓
contracted
  ↓
on_order
  ↓
delivery_started
  ↓
partially_delivered
  ↓
delivered
  ↓
operational
```

Not every program traverses every state. Cancellation, suspension, and unknown states must be representable.

## Equipment Service State

Canonical values:

- `planned`
- `under_evaluation`
- `on_order`
- `delivery_in_progress`
- `operational`
- `upgrade_in_progress`
- `reserve_or_limited`
- `retired`
- `cancelled`
- `unknown`

Status claims require temporal qualification whenever possible.

## Quantity Model

Never represent an uncertain inventory number as a timeless scalar.

A quantity claim should support:

```text
value
unit
quantity_type
point_in_time / valid interval
scope
precision
source/evidence
confidence
```

`quantity_type` examples:

- ordered
- approved
- delivered
- operational estimate
- original fleet
- upgraded
- lost/retired when reliably documented

Conflicting quantities remain separate claims until reconciled.

## Naming and Multilingual Rules

Each entity should support:

- official Arabic name, if available
- official English name, if available
- normalized Arabic name
- normalized English name
- transliterations and common aliases
- abbreviations such as `RSAF`
- manufacturer designations

Search aliases do not change canonical naming.

## Temporal Semantics

Prefer explicit temporal qualifiers:

- `point_in_time`
- `valid_from`
- `valid_to`
- `announced_at`
- `signed_at`
- `delivery_started_at`
- `entered_service_at`
- `retired_at`

Unknown dates remain unknown; the system must not manufacture precision.

## Geographic Semantics

The ontology may represent publicly documented geographic relationships at an appropriate granularity, but the product is not a live order-of-battle or tracking system.

Canonical data must not be designed to infer or publish sensitive real-time positions, movement patterns, readiness, patrol schedules, ammunition storage, or non-public precise coordinates.

## Seed Entities for M0

The M0 prototype should model only enough diversity to stress the ontology:

1. Royal Saudi Air Force
2. F-15 family
3. F-15SA variant
4. Boeing
5. PAC-3 MSE or another documented air-defense procurement item
6. one official procurement event
7. one publicly announced multinational exercise

These are test fixtures, not a claim that the initial public release must be limited to these entities.
