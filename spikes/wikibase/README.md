# M0 Wikibase Spike

This directory is a **bounded architecture trial**, not the production topology for Saudi Defense Atlas.

It evaluates whether Wikibase can implement the project's knowledge-core semantics without redefining the domain model or bypassing the `ChangeProposal -> ReviewDecision -> Revision` authority boundary.

## Scope

The local stack contains only what is needed for M0 representation/query testing:

- MariaDB 10.11
- `wikibase/wikibase:8`
- Wikibase job runner
- `wikibase/wdqs:2`
- WDQS updater

The image majors mirror the upstream Wikibase Suite compose configuration inspected at upstream commit `05ba904b687ba5cfc6c28c3140be191b2d0e9615` (2026-09-17). OpenSearch, QuickStatements, the WDQS frontend, TLS, reverse proxying, and production identity/access management are intentionally omitted because they are not required to answer the M0 knowledge-model question.

All host ports bind to `127.0.0.1` only.

## Prerequisites

- Docker Engine with Docker Compose v2
- Python 3.11+

The WDQS image requires meaningful local memory; consult upstream Wikibase Suite documentation before running the stack on a constrained machine.

## Run

```bash
cd spikes/wikibase
cp .env.example .env
```

Edit `.env` and replace the example local passwords. Then:

```bash
docker compose up -d

python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt

set -a
. ./.env
set +a

python seed.py
python verify.py
```

Successful verification creates two ignored local files:

- `state.generated.json` — SDA ID to Q/P ID mappings and created statement GUIDs
- `verification.generated.json` — evidence for the M0 acceptance checks

Inspect container state with:

```bash
docker compose ps
```

Local endpoints:

- Wikibase: `http://localhost:8181`
- Action API: `http://localhost:8181/w/api.php`
- WDQS: `http://localhost:9999/bigdata/namespace/wdq/sparql`

Ports can be changed in `.env`.

## Reset

The seed is designed for a clean bounded trial rather than as the M1 idempotent ingestion implementation.

Reset all local spike volumes and generated evidence before recreating it:

```bash
./reset.sh
```

If the script is not executable in a checkout, run `sh reset.sh`.

## What `seed.py` creates

Real, publicly sourced test records:

- Royal Saudi Air Force
- F-15 family
- F-15SA
- Boeing
- PAC-3 MSE
- a 30 January 2026 PAC-3 MSE possible-FMS approval/notification event
- Spears of Victory 2026

The seed intentionally distinguishes:

- 84 F-15SA as a **historical procurement quantity in the 2011 signed FMS LOA**;
- 730 PAC-3 MSE as a **requested quantity in a 2026 approved possible-FMS notification**;
- neither of those quantity statements is automatically treated as a current operational inventory number.

It also creates one unmistakably named synthetic test item with contradictory quantities `10` and `12`. Those values exist only to verify conflict coexistence and are marked `SYNTHETIC_NON_PUBLIC`.

## What `verify.py` proves

The verifier fails unless the local instance demonstrates:

1. Arabic label, English label, and `RSAF` alias resolve to the same backend item;
2. the SDA project ID remains distinct from the Wikibase Q-ID;
3. a quantity statement carries claim ID, quantity type, point-in-time, and confidence qualifiers;
4. one claim preserves multiple references;
5. two contradictory synthetic quantity statements coexist without overwrite;
6. the PAC-3 MSE event remains explicitly `procurement_approval_or_notification` rather than becoming contract/delivery semantics;
7. MediaWiki/Wikibase revision history is queryable;
8. Action API returns bilingual labels/aliases/claims;
9. WDQS can resolve an entity by its SDA project ID.

## What this does **not** prove

A passing local spike does not establish:

- production security or authorization design;
- high availability;
- backup/recovery;
- production deployment topology;
- performance at Atlas scale;
- operational cost;
- public publishing readiness;
- final Wikibase adoption.

The output must be reviewed in `docs/adr/ADR-0002-knowledge-core.md` before APR-003 may move from trial status to ACCEPTED or REJECTED.

## Provenance

The real test records use official public sources from:

- U.S. Air Force — 2011 F-15SA FMS announcement;
- U.S. Air Force — 2020 final F-15SA delivery announcement;
- Robins Air Force Base — 2012 F-15SA program announcement;
- U.S. Defense Security Cooperation Agency — 2026 PAC-3 MSE possible-FMS notification;
- Saudi Press Agency — Spears of Victory 2026 announcement.

These source references are test evidence for the architecture spike. They do not make the spike database the public production database.