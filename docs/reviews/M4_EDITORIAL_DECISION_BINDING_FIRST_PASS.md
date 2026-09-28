# M4 Editorial Decision Binding — Exhaustive First Pass

**Scope:** `m4/editorial-decision-binding`

## Review target

The increment binds a content-addressed M4 `EditorialReviewPacket`, exact `ChangeProposal`, and human `ReviewDecision` into immutable operational audit metadata, then permits only an exact `approve` decision to pass into the existing M1 canonical mutation guard.

## Invariants reviewed

- packet identity and full content remain bound after review;
- proposal ID and canonical SHA-256 agree across packet, decision, and binding;
- ReviewDecision content cannot change after binding;
- only a human may decide an AMBER M4 editorial packet;
- reject / return-for-revision are auditable but cannot execute canonical writes;
- approval does not create a second mutation authority: existing `execute_authorized_proposal` remains authoritative;
- decision/binding temporal order cannot predate packet/proposal review context;
- the binding itself has no approval, canonical-mutation, or publication authority;
- backend idempotency/reconciliation semantics remain inherited from the previously verified mutation guard.

## Finding DB-F01 — packet audit binding relied only on truncated content-addressed ID — FIXED

### Observation

The initial binding retained `review_packet_id`, proposal SHA-256, and ReviewDecision SHA-256. The packet ID is content-addressed, but its stable identifier uses a bounded digest prefix rather than preserving the complete packet digest as a first-class audit field.

### Risk

The binding claimed exact packet provenance without carrying the same full-digest evidence already preserved for proposal and ReviewDecision payloads.

### Remediation

`review_packet_sha256` is now required by `editorial-decision-binding.schema.json` and generated from canonical JSON for the complete final review packet. Validation recomputes the binding from packet/proposal/decision inputs, so any packet or binding tamper fails closed.

### Regression coverage

`validate_m4_editorial_decision_binding.py` verifies the full packet digest, packet-content tamper rejection, binding-hash tamper rejection, proposal tamper rejection, and ReviewDecision tamper rejection.

## Reviewed areas with no blocking finding

- human reviewer requirement;
- exact proposal hash equality across review surfaces;
- packet content-addressed-ID verification;
- `awaiting_human` / AMBER packet requirement;
- approve vs reject/return execution behavior;
- temporal ordering;
- binding content-addressed identity;
- mutation-guard reuse and no duplicate approval authority;
- backend write suppression on rejected decisions.

## Explicit non-scope / retained gap

The binding contract does **not** establish global uniqueness or serialization of multiple human decisions for the same review packet. That property requires a durable operational coordinator/queue/transaction boundary and belongs with the still-open concurrent-writer coordination problem. This increment must not disguise that distributed coordination problem with process-local locking or by treating a content-addressed binding as a uniqueness constraint.

Production scheduler/orchestrator selection, distributed writer coordination, model/provider selection, autonomous approval, and publication authority remain outside this increment.

## Disposition

**GO to exact-head CI and independent review.**

Promotion/merge requires schema-validation and Wikibase regression gates on the final branch head and resolution of any substantiated independent-review findings.