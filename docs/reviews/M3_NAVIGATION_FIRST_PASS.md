# M3 Timeline and Filter Navigation — Exhaustive First Pass

**Date:** 2026-09-27  
**Scope:** `m3/timeline-filter-navigation` public navigation projection over accepted `SearchDocument` and `RelationshipGraphView` contracts.

## Disposition

**PASS after remediation**, subject to final exact-head CI. No unresolved blocker remains in the reviewed navigation contract.

## Areas reviewed

- authority boundary and avoidance of a new truth store;
- facet counting semantics and referential integrity;
- bilingual entity-backed filter labels;
- timeline temporal ordering and unknown-date handling;
- duplicate Event reconciliation across graph projections;
- Event provenance membership;
- Evidence-role preservation and supporting-Evidence admission;
- backend Q/P leakage;
- avoidance of lifecycle/current-state inference from Event ordering;
- deterministic output under repeated public projections.

## Findings fixed before merge

### M3-NAV-F01 — Entity-backed facets resolved identity but not semantic type

**Risk:** a `country_ids` facet could resolve to a SearchDocument whose `entity_type` was not `country`; equivalent type confusion was possible for service/manufacturer facets.

**Fix:** entity facets now enforce explicit target-type sets: service → organization/military unit, manufacturer → organization, country → country.

**Regression:** wrong-type country target fails closed.

### M3-NAV-F02 — Duplicate citation identity could be order-dependent

**Risk:** the same `(Evidence, Document, Source)` identity appearing in repeated graph projections with different material citation data could be overwritten based on graph order.

**Fix:** citation identity is merged only when material data agrees; conflicts fail closed both within a timeline item and across graph projections.

**Regression:** duplicate Event with the same citation identity but a different URL fails closed.

### M3-NAV-F03 — Timeline navigation dropped contradictory/contextual Evidence

**Risk:** retaining only `supports` citations could make a navigation timeline look more certain than the accepted public graph from which it was projected.

**Fix:** timeline navigation preserves `supports`, `contradicts`, and `contextualizes` roles while still requiring at least one supporting Evidence item for publication.

**Regression:** synthetic delivery Event preserves both supporting and contradicting Evidence; a context/contradiction-only Event remains inadmissible.

## Additional guards verified by the contract

- entity-backed facet IDs must resolve to public SearchDocuments;
- timeline Event IDs must appear in each source graph's provenance record IDs;
- duplicate Event material must agree before root/domain context is merged;
- unknown date precision remains explicit and sorts after known temporal values;
- timeline output does not contain inferred `current_state` or `status` fields;
- navigation provenance unions SearchDocument revisions and graph revisions/record IDs;
- Q/P/backend identifiers fail closed.

## Claim ceiling

This review validates a backend-neutral navigation projection only. It does not select a frontend framework or router, does not establish dynamic per-query facet counts, and does not authorize semantic/vector search or any new canonical Claim/Event storage.
