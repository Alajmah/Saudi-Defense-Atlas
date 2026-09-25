# AI Governance and Publication Policy

## Principle

AI is an operational assistant, not an epistemic authority.

Models may discover, extract, classify, normalize, translate, compare, summarize, draft, and propose changes. Canonical truth is admitted only through source-backed policy and, where required, human review.

## AI Roles

### Scout

Finds potentially relevant new material from approved public sources.

May:

- classify relevance
- detect likely new events
- prioritize review

May not:

- establish unsupported facts
- infer sensitive operational information

### Extractor

Converts documents into structured candidate entities, claims, events, dates, quantities, and relationships.

Output must be schema-validated.

### Resolver

Proposes mappings from extracted names to canonical entities and aliases.

Ambiguous matches must remain unresolved or go to review.

### Verifier

Compares candidate claims with existing knowledge and additional evidence.

It must be able to return `insufficient evidence` rather than force a conclusion.

### Conflict Detector

Identifies semantic disagreement, scope differences, temporal mismatch, or duplicate records.

### Editor

Creates Arabic/English summaries, page copy, metadata, and explanatory prose from approved claims.

Generated prose is not itself evidence.

### Auditor

Periodically identifies stale claims, broken references, unresolved conflicts, duplicate entities, and anomalous changes.

## Authority Levels

### GREEN — Automated

AI/automation may publish or update when policy explicitly permits the field and all validation checks pass.

Typical examples:

- normalized document metadata
- source ingestion timestamps
- deterministic aliases
- indexing/search metadata
- low-risk link maintenance

### AMBER — AI proposes, human approves

Default for substantive knowledge changes, including:

- quantities
- procurement lifecycle state
- delivery state
- service status
- first identification of a new platform/variant
- exercise participation when evidence is ambiguous
- conflicting sources
- material translation choices affecting meaning

### RED — Human-only / restricted

AI must not autonomously publish or transform into an operational feed:

- real-time force movement
- live unit disposition
- patrol patterns
- readiness assessments derived from sensitive aggregation
- ammunition stocks or storage details
- non-public precise coordinates
- tactical vulnerabilities
- other information whose aggregation materially increases operational risk

The system should prefer exclusion or coarse historical/public representation over attempting to maximize detail.

## Required AI Trace

Each AI-proposed change should retain, where practical:

- model/provider identifier
- model version
- prompt/template version
- source document IDs
- extracted evidence spans or locators
- structured output
- validation result
- confidence/rationale fields
- timestamp
- reviewer decision
- final admitted revision ID

## Model Independence

Domain schemas and workflow semantics must not depend on one model provider. Model-specific adapters belong at the edge.

## Structured Output First

Canonical ingestion uses typed schemas. Free-form model text cannot directly mutate canonical knowledge.

Example:

```text
Source document
  ↓
LLM extraction
  ↓
Typed candidate object
  ↓
Schema validation
  ↓
Entity resolution
  ↓
Policy checks
  ↓
Evidence verification
  ↓
Approval / rejection
  ↓
Canonical revision
```

## Hallucination Controls

At minimum:

1. require evidence locators for factual extractions;
2. allow null/unknown values;
3. forbid invented precision;
4. distinguish extraction from inference;
5. compare proposed changes to current canonical state;
6. route contradictions to review;
7. evaluate extraction against a curated test corpus;
8. log rejected proposals as training/evaluation feedback, not as facts.

## Translation Policy

Arabic and English text should share the same canonical entity and claim IDs.

AI translation must obey a maintained terminology registry for military organizations, ranks, equipment categories, procurement states, and recurring technical terms.

Official names take precedence over generated translations where available.

## Publication Policy

AI-generated public prose may be automatically published only when:

- every material factual statement is grounded in already-approved claims;
- citations are resolvable;
- no unresolved conflict is hidden by the prose;
- no restricted operational detail is introduced;
- the generated text passes deterministic policy checks.

Otherwise the draft enters editorial review.

## Evaluation

Before enabling automatic mutation or publication for a new claim type, the project must maintain an evaluation set covering:

- correct extraction
- false positives
- entity collisions
- Arabic/English alias resolution
- date interpretation
- procurement-stage confusion
- quantity/scope confusion
- source conflicts
- refusal to infer unknown values
- restricted operational detail

Automation authority expands only after measured performance is acceptable for the risk class.
