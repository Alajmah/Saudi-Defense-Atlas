# M4 Canonical Mutation Dispatcher — Exhaustive First Pass

**Scope:** PR #25 project-owned dispatch envelope and global single-writer coordination boundary layered over the existing approved editorial-decision binding and mutation guard.

## Disposition

No merge-blocking implementation defect remains in the bounded dispatcher contract. Merge is permitted only after exact-head schema-validation and Wikibase regression are green.

## What this increment proves

- one immutable dispatch envelope binds the exact review packet, ChangeProposal, human ReviewDecision, and EditorialDecisionBinding;
- dispatch target records are deterministically derived from every mutation payload ID and explicit target ID;
- the dispatch record has no approval, canonical mutation, or publication authority of its own;
- the global serialization lane is acquired before any backend inspection or write;
- a busy lane fails closed with zero backend activity;
- the existing proposal hash, idempotency, reconciliation, and no-blind-retry mutation semantics remain authoritative;
- serialized replay converges without duplicate backend writes.

## Reviewed risk — lower-level mutation primitive remains callable

`execute_editorial_authorized_proposal` remains the already-accepted low-level single-writer primitive used by M1/M4 tests and bounded manual paths. This PR does not remove that API or pretend Python callability is an authorization boundary.

**Operational rule introduced by this increment:** any future M4 orchestration that runs more than one upstream worker must route canonical effects through `execute_dispatched_editorial_proposal`; direct use of the lower-level primitive remains restricted to explicitly single-writer/manual/test contexts.

This is a governance/architecture boundary, not proof that arbitrary future code cannot bypass it. Any production orchestrator must make the dispatcher the only configured canonical-write path and must be reviewed accordingly.

## Reviewed risk — coordinator implementation is not production-qualified

The `SingleWriterCoordinator` protocol requires atomic exclusive acquisition across all canonical mutation workers and retention of exclusivity until release. The validator uses an in-memory fixture only.

Therefore this PR does **not** qualify:

- Redis/PostgreSQL/queue-specific coordination;
- lease expiry or worker crash recovery;
- fencing tokens;
- HA/failover;
- distributed coordinator partitions;
- production multi-process canonical writers.

Until a shared coordinator implementation is separately selected and verified, the deployment invariant remains **one canonical mutation worker**.

## Areas reviewed with no additional blocker

- exact packet/proposal/decision/binding hash revalidation occurs before dispatch;
- rejected decisions cannot create a dispatch envelope;
- dispatch cannot predate the editorial decision binding;
- target-record ordering is deterministic and duplicates are removed;
- target-set tampering invalidates the dispatch;
- the coordinator permit is held across mutation preflight, backend effect, and reconciliation;
- release occurs through `finally` for converged, failed, unknown-effect, or raised execution paths;
- no scheduler, queue backend, orchestrator, or lock technology is selected here.

## Claim ceiling

Passing this PR verifies the single-writer dispatch contract and makes the intended M4 scaling boundary explicit. It does not close production distributed coordination. Multiple monitoring/extraction/review workers may be designed upstream, but multiple canonical mutation workers remain unauthorized until a shared atomic coordinator implementation passes a separate forcing-function review and verification.
