# Domain Schemas v0.1

These JSON Schemas are the implementation-neutral contract between ingestion/AI systems, editorial governance, and any canonical knowledge-store adapter.

## Core records

- `entity.schema.json` — stable domain identity and multilingual naming
- `source.schema.json` — publisher/origin authority
- `document.schema.json` — retrieved/versioned source artifact
- `evidence.schema.json` — bounded locator/span inside a document
- `claim.schema.json` — sourced assertion with temporal/scope context
- `event.schema.json` — sourced dated occurrence

## Mutation governance

- `change-proposal.schema.json` — candidate mutations; not canonical truth
- `review-decision.schema.json` — approve/reject/return-for-revision decision
- `revision.schema.json` — auditable canonical application record

The authority chain is:

```text
candidate extraction
    -> ChangeProposal
    -> policy evaluation
    -> ReviewDecision
    -> canonical adapter write
    -> Revision
```

An editor changing a proposal creates a new proposal that supersedes the original. Reviewed payloads are not silently mutated.

## Identity rules

Project-issued record IDs are independent of backend identifiers. Wikibase Q/P IDs, relational primary keys, search document IDs, and other adapter-native identifiers are mappings, not canonical domain identity.

Allocation of a project ID does not imply that a candidate record has been admitted as canonical knowledge.

## Provenance rules

`Source`, `Document`, and `Evidence` are deliberately separate:

```text
Source
  publisher/origin
       |
       v
Document
  retrieved/versioned artifact + content hash
       |
       v
Evidence
  bounded locator/span in that artifact
       |
       v
Claim/Event
  support / contradiction / context link
```

A URL alone is not immutable document identity. A publisher is not a document. A document is not automatically evidence for every statement it contains.

## Claim rules

- factual claims require at least one evidence link;
- credible conflicting claims may coexist;
- status, quantity, scope, and time are claim context rather than timeless entity fields;
- `unknown` is a valid value kind where the source does not justify precision;
- canonical predicates are versioned through the schema/ontology rather than accepted as arbitrary free text.

## Procurement semantics

Procurement is modeled as typed events plus bounded status/quantity claims. The project does not require a single linear finite-state transition sequence. Approval, contract, order, delivery, and entry into service remain distinct.

## Validation

Run:

```bash
python scripts/validate_schemas.py
```

The validator checks schema correctness, resolves cross-schema references from the local registry, and evaluates positive and negative fixtures in `tests/fixtures/schema-fixtures.json`.

JSON Schema validates record shape. Cross-record invariants—such as whether a `ReviewDecision` is authorized for the referenced proposal risk class—remain application/policy validation and must be tested separately.