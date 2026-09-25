# Source and Claim Admission Policy

## Purpose

Saudi Defense Atlas separates **discovery value** from **evidentiary authority**. A source may be useful for finding a lead without being strong enough to establish a canonical claim.

## Source Classes

### A — Primary / Official

Examples:

- Saudi government and military authorities
- foreign government agencies and official procurement notices
- official armed-forces releases
- official gazettes and parliamentary/congressional documents
- authoritative contract-award notices

Default evidentiary weight: **very high**, subject to interpretation and scope.

### B — First-Party Industry

Examples:

- manufacturer press releases
- company filings
- official product documentation
- official partner announcements

Default evidentiary weight: **high** for the company's own contracts, products, and announcements; lower for broad independent assessments.

### C — Specialist / Professional Defense Sources

Examples:

- established defense intelligence and trade publications
- specialist aviation, naval, land, and procurement publications

Default evidentiary weight: **medium to high**, depending on methodology, attribution, and corroboration.

### D — General News / Research

Examples:

- major newspapers and broadcasters
- think-tank reports
- academic material

Default evidentiary weight: **context-dependent**.

### E — Open-Source Leads

Examples:

- social media
- forums
- enthusiast databases
- unsourced aggregators
- image/video posts without authoritative context

Default evidentiary weight: **discovery only** unless independently corroborated.

## Source Metadata

Every registered source should record:

- source ID
- publisher
- source class
- URL/locator
- publication date if available
- retrieval date
- language
- content fingerprint
- document type
- archival reference if available
- access/licensing notes where relevant

## Claim Admission Rules

### Rule 1 — No orphan facts

A material canonical claim requires at least one evidence record.

### Rule 2 — Match source authority to claim type

A manufacturer may be authoritative about a product designation or its own award, but not necessarily about the complete operational inventory of a military service.

### Rule 3 — Approval is not contract

Government approval, notification, request, memorandum, contract award, delivery, and entry into service are distinct event types and must not be collapsed.

### Rule 4 — Preserve disagreement

Credible conflicting claims remain separately stored with their own evidence and temporal context. Reconciliation is an explicit editorial act.

### Rule 5 — Newer is not automatically truer

A newer source may describe a different scope, date, contract phase, or counting method. Replacement requires semantic comparison, not date comparison alone.

### Rule 6 — Unknown remains unknown

Do not infer exact quantities, dates, configurations, or locations when the evidence supports only a range or broad statement.

## Confidence Model v0.1

Confidence is attached to a claim evaluation, not treated as an intrinsic property of a source.

Suggested labels:

- `verified` — directly supported by strong evidence and internally consistent
- `high` — strongly supported, minor uncertainty remains
- `medium` — plausible and sourced but incomplete or indirectly supported
- `low` — weak, disputed, or insufficiently corroborated
- `unverified` — discovery lead, not admitted as fact

The numeric implementation, if any, must be documented separately and must not imply false precision.

## Automatic Admission

A pipeline may automatically admit low-risk metadata when all of the following hold:

- extraction is schema-valid;
- entity resolution is unambiguous;
- the source is approved for that claim type;
- no conflicting canonical claim is detected;
- the change is non-sensitive and reversible;
- policy explicitly allows automation for that field.

Examples may include title normalization, publisher metadata, document dates, or links.

## Human Review Required

Human review is required by default for material changes involving:

- equipment quantities or inventory estimates
- first confirmed delivery
- operational status or entry into service
- retirement or loss claims
- conflicting credible sources
- changes with strategic significance
- claims based primarily on lower-authority sources
- geographic detail approaching operational sensitivity

## Staleness

Claims should support `verified_at` and an optional review policy.

A stale claim is not automatically false. Staleness indicates that re-verification is due.

Priority for re-verification should consider:

- claim volatility
- source age
- strategic importance
- source quality
- known procurement lifecycle
- conflicting newer evidence

## Citation Requirement

Public pages should expose claim-level or section-level citations wherever practical. AI-generated answers must cite the underlying approved evidence rather than cite the AI-generated prose.

## Corrections

Corrections must preserve revision history. The system should record:

- previous claim/value
- replacement or superseding claim
- evidence
- editor or automated process
- reason
- timestamp

Silent destructive replacement is discouraged for substantive facts.
