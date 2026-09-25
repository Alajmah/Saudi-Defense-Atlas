# Wikibase M0 Mapping

This mapping is a trial adapter contract. It does not redefine the Saudi Defense Atlas ontology.

## Identity

Every Wikibase item created by the spike receives an `SDA canonical ID` statement.

```text
SDA domain ID  ->  Wikibase Q/P ID
```

The arrow is a backend mapping. Q/P IDs are never treated as stable public/domain identity.

## Entities

| SDA concept | Wikibase representation |
|---|---|
| Entity | Item |
| Arabic/English names | labels |
| abbreviations/common names | aliases |
| descriptions | descriptions |
| SDA canonical ID | external-id statement |
| typed relationship | item-valued statement |

## Claims

A claim is represented as a statement on its subject item.

Project context is retained through qualifiers:

- SDA claim ID
- quantity type / scope where relevant
- point in time
- confidence label
- fixture marker for synthetic conflict tests

Wikibase statement rank is **not** used as the project confidence model. Confidence remains an SDA qualifier/policy concept.

## Evidence

A Wikibase reference is a projection of SDA provenance, not a replacement for the SDA `Source -> Document -> Evidence` model.

The M0 reference set carries:

- SDA document ID
- source URL
- evidence locator
- retrieval date when available

One statement may receive multiple Wikibase references to prove that the store can represent multiple evidence records.

## Events

For the M0 spike, important procurement/training Events are represented as Items with:

- SDA canonical ID
- event type
- event date
- related/participant Items as statements

This is a representational experiment. Event storage may later remain in Wikibase, PostgreSQL, or a hybrid model depending on the M0 decision.

## Proposals, decisions, and revisions

`ChangeProposal`, `ReviewDecision`, and SDA `Revision` remain project governance records outside Wikibase.

The Wikibase adapter may execute writes only when the bundle satisfies:

```text
proposal.policy_outcome permits admission
AND decision == approve
AND reviewer authority satisfies risk class
AND revision references that exact proposal + decision
```

A MediaWiki/Wikibase revision ID is recorded as a **backend receipt** after the approved project revision is applied. It does not replace the project Revision record.

## Conflict test

Real defense entities must not receive fabricated contradictory claims merely to test storage behavior.

The spike therefore creates a clearly marked synthetic fixture with two simultaneous contradictory quantity statements. Passing this test demonstrates coexistence mechanics only; it makes no real-world factual assertion.

## Trial claim ceiling

Passing this mapping proves only that the tested SDA semantics can be represented and retrieved from the tested local Wikibase configuration. It does not establish production scalability, security, availability, backup/recovery, or long-term operational suitability.