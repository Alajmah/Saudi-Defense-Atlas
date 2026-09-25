# Vision

## Mission

Build the most rigorous open, bilingual, source-backed knowledge atlas of Saudi defense capabilities and their evolution over time.

Saudi Defense Atlas is not intended to be a conventional military-news site. Its durable asset is a structured knowledge base that can answer questions about organizations, equipment, procurement, training, industry, and historical change with explicit provenance.

## Product Thesis

Most defense information is fragmented across government releases, manufacturers, specialist publications, PDFs, event announcements, and historical reporting. The Atlas converts that fragmentation into a normalized knowledge system.

A source document may create or update multiple connected facts:

```text
Source document
  ├─ equipment claim
  ├─ procurement event
  ├─ manufacturer relationship
  ├─ training participation
  ├─ timeline event
  └─ article/update
```

The system should support questions such as:

- Which aircraft variants are publicly documented in Royal Saudi Air Force service?
- Which procurement programs changed status during a given period?
- Which systems are linked to which manufacturers and contracts?
- Which countries and platforms recur in publicly announced exercises?
- Which localization initiatives are associated with a platform or company?
- Which facts are old, conflicting, or weakly sourced?

## Audience

Primary audiences:

- Arabic-speaking readers seeking a rigorous reference
- Researchers and analysts
- Defense-industry observers
- Journalists and students
- Readers who need cited, structured summaries rather than rumor aggregation

## Differentiators

1. Arabic and English as first-class data, not an afterthought.
2. Claim-level provenance rather than article-level footnotes only.
3. Historical state and revision tracking.
4. Explicit source-quality and uncertainty handling.
5. AI-assisted maintenance with auditable human governance.
6. Connected views: arsenal, procurement, exercises, industry, timeline, map, and graph.

## Scope Boundary

The Atlas covers publicly available strategic, historical, organizational, industrial, procurement, training, and equipment information.

It does **not** aim to provide operational intelligence or facilitate real-time tracking. The platform must avoid publishing or deriving sensitive operational details such as current unit movements, live force disposition, patrol routines, readiness states, ammunition stocks, non-public precise locations, or other information whose aggregation could materially increase operational risk.

## Success Criteria

The platform succeeds when:

- every important displayed fact can be traced to evidence;
- conflicting evidence is represented rather than silently overwritten;
- Arabic and English users resolve to the same canonical entities;
- updates propagate across all related views without manual duplication;
- AI reduces editorial workload without becoming an unaudited authority;
- stale and weak claims become visible to maintainers;
- one maintainer can operate a research product with the leverage of a much larger editorial team.
