# Ontology v0.1

## Purpose

This document defines the initial conceptual model for Saudi Defense Atlas. It describes domain meaning, not database tables. Storage technology may change while this contract remains stable.

## Core Primitives

### Entity

A stable project identity for a real-world or conceptual domain thing.

Required conceptual fields:

- `id`
- `entity_type`
- Arabic and/or English canonical names
- aliases where applicable
- record lifecycle status

Operational, procurement, inventory, readiness, or service state should not be stored as timeless entity attributes when they are factual assertions that can change. Those belong in sourced claims/events.

Backend identifiers such as Wikibase Q/P IDs or relational primary keys are mappings, not canonical domain identity.

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
- scope
- precision
- confidence evaluation
- lifecycle state such as active/disputed/superseded
- one or more evidence links

A material factual claim cannot be canonical without evidence.

### Source

The publisher or originating authority behind documents, such as a government agency, armed force, manufacturer, specialist publication, or other publisher.

A Source is not the same thing as a retrieved web page/PDF and is not itself evidence for every claim published under its name.

### Document

A specific retrieved or versioned source artifact, for example an official release, procurement notice, report, PDF, manufacturer announcement, or specialist article.

A Document should preserve enough identity/provenance to distinguish revisions and repeated retrievals, including where available:

- source/publisher
- canonical/retrieved locator
- publication date
- retrieval timestamp
- content fingerprint
- document type/language
- archival/version relationship

A URL alone is not assumed to be immutable document identity.

Documents are provenance records, not ordinary military-domain entities by default.

### Evidence

A bounded piece of a Document that bears on a Claim or Event.

Evidence identifies the relevant location/span/section/page or structured observation. Its role is assigned by the Claim/Event link:

- `supports`
- `contradicts`
- `contextualizes`

This separation allows one document to support one claim while contradicting or merely contextualizing another.

### Event

A dated occurrence that may change knowledge state or connect entities, for example:

- procurement request
- government approval/notification
- contract award/signature
- order
- delivery/delivery start
- entry into service
- upgrade
- retirement/cancellation/suspension
- exercise/training
- localization agreement
- facility opening

Events are first-class records because procurement/training history cannot be safely reconstructed from a single current status field.

### Relationship

A typed connection between entities. A relationship requiring factual support is represented as or backed by a Claim.

### ChangeProposal

A candidate set of mutations produced by a human, AI process, or deterministic system. A proposal is explicitly non-canonical until policy/review requirements are satisfied.

### ReviewDecision

A recorded approval, rejection, or return-for-revision decision over an exact ChangeProposal.

Editing a proposal creates a new superseding proposal rather than silently changing the object that was reviewed.

### Revision

An immutable audit record that links an approved proposal/decision to the canonical mutations actually applied, including backend receipts where relevant.

Conceptual mutation boundary:

```text
candidate extraction
    ↓
ChangeProposal
    ↓
policy / review
    ↓
ReviewDecision
    ↓
canonical adapter write
    ↓
Revision
```

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

A named exercise or training event/series. Individual occurrences may additionally be represented as Events when needed for chronology.

### ProcurementProgram

A durable acquisition/program identity that connects procurement events, contracts, equipment, quantities, and status claims.

### Contract

A documented contract or award. A government approval/notification is not automatically a Contract.

### LocalizationProgram

Industrial participation, local manufacture, technology transfer, MRO, or other documented localization initiative.

### Country

Used for manufacturers, suppliers, exercise participants, and government-to-government relationships.

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
equipment.service_state
procurement_program.lifecycle_state
inventory.quantity
procurement.quantity
```

Predicates must be centrally registered; arbitrary free-text predicates are not allowed in canonical data.

## Procurement Lifecycle Semantics

Procurement is **not** modeled as a mandatory linear finite-state machine.

The common conceptual progression may look like:

```text
rumored / under evaluation
        ↓
request / announcement
        ↓
approval or notification
        ↓
contract / order
        ↓
delivery activity
        ↓
entry into service / operational use
```

But real programs may:

- skip stages visible in public sources;
- split into tranches or amendments;
- be suspended/cancelled and later resumed;
- have approval, contracting, delivery, and operationalization facts that overlap in time;
- have one stage documented while another remains unknown.

Therefore the canonical history is primarily represented through **typed Events plus temporally bounded Claims**. A lifecycle-state claim is a convenience projection over evidence, not the sole source of procurement history.

The following concepts must always remain distinct:

- request/announcement
- government approval or notification
- contract award/signature
- order
- delivery start / partial delivery / delivery
- entry into operational service
- cancellation / suspension

## Equipment Service State

Canonical values for service-state claims may include:

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

Status claims require temporal qualification whenever possible and must not be inferred from procurement approval alone.

## Quantity Model

Never represent an uncertain inventory number as a timeless scalar.

A quantity Claim should support:

```text
value
unit
quantity_type
point_in_time / valid interval
scope
precision or bounds
source/evidence
confidence
```

`quantity_type` examples:

- ordered
- approved
- contracted
- delivered
- operational estimate
- original fleet
- upgraded
- lost/retired when reliably documented

Conflicting quantities remain separate Claims until explicitly reconciled or superseded. Different quantity types are not conflicts merely because their numbers differ.

## Naming and Multilingual Rules

Each Entity should support:

- official Arabic name, if available
- official English name, if available
- normalized Arabic name
- normalized English name
- transliterations and common aliases
- abbreviations such as `RSAF`
- manufacturer designations

Search aliases do not change canonical naming.

Arabic and English names resolve to the same project Entity ID.

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

Temporal values should retain precision (`year`, `month`, `day`, etc.) rather than manufacture a day when only a year is known.

Unknown dates remain unknown.

## Geographic Semantics

The ontology may represent publicly documented geographic relationships at an appropriate granularity, but the product is not a live order-of-battle or tracking system.

Canonical/public data must not be designed to infer or publish sensitive real-time positions, movement patterns, readiness, patrol schedules, ammunition storage, or non-public precise coordinates.

Public availability alone does not imply that aggregating a detail is operationally appropriate.

## Identity and Deduplication

The project distinguishes:

- domain identity (`SDA` project ID);
- backend/store identity (for example Wikibase Q/P IDs);
- source publisher identity;
- document/artifact identity;
- content identity/fingerprint.

These are related but not interchangeable.

Idempotent ingestion must rely on explicit document/content and record semantics rather than assuming identical URLs, backend IDs, or prose titles imply identity.

## Seed Entities for M0

The M0 prototype should model only enough diversity to stress the ontology:

1. Royal Saudi Air Force
2. F-15 family
3. F-15SA variant
4. Boeing
5. one documented air-defense procurement item such as PAC-3 MSE
6. one official procurement Event
7. one publicly announced multinational Exercise

Where M0 needs to demonstrate contradictory claims independent of real-world evidence, it must use an explicitly **synthetic/non-public test fixture** rather than fabricate a conflict about a real entity.

These records are test fixtures for architecture validation; inclusion in M0 does not automatically authorize public publication.