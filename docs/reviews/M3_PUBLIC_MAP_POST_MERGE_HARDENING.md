# M3 Public Map Post-Merge Hardening

## Scope

This review records three Codex findings that arrived after PR #14 had already merged. They are treated as post-merge hardening rather than retroactive changes to the original review record.

## Findings

### PMH-01 — Coordinate unit ambiguity — FIXED

The public-map projector previously accepted any numeric Claim value and interpreted it as degrees. A schema-valid value expressed in radians could therefore be range-valid yet geographically wrong.

**Fix:** public latitude/longitude Claims must use `unit = "degrees"`. Missing or alternative units fail closed. Regression coverage includes radians and null unit values.

### PMH-02 — Backend-ID detection scanned public prose — FIXED

The original guard scanned `repr()` of the whole public projection for `Q`/`P` plus digits. Legitimate prose such as `Hangar Q3`, `Q3 2026`, or `Page P5` could therefore be rejected.

**Fix:** backend-ID rejection is now structural and limited to identity-bearing fields: feature/entity/claim/organization/citation/provenance IDs. Display text and citation prose are not scanned. Regression coverage preserves Q/P-looking prose while still rejecting backend-native IDs in public identity fields.

### PMH-03 — Map feature-ID generation was not injective — FIXED

Removing the `SDA-` prefix could make schema-valid entity IDs such as `SDA-FAC-A` and `FAC-A` converge on the same map feature ID.

**Fix:** feature IDs are generated as `SDA-MAP-{entity_id}` with no lossy prefix removal, and duplicate generated IDs are rejected. Regression coverage proves the two formerly colliding examples remain distinct.

## Claim ceiling

These fixes harden the already accepted M3 public-map publication boundary. They do not expand map scope, precision, or operational geography, and they do not qualify production map infrastructure.
