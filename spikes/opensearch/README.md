# M3 OpenSearch Trial

This directory is a disposable architectural trial, not production search infrastructure.

## Purpose

Evaluate whether OpenSearch can implement the accepted M3 public lexical-search contract while remaining a downstream index over SDA `SearchDocument` records.

The trial is pinned to **OpenSearch 3.8.0** and compares engine result ordering against `execute_reference_lexical_search` for the same schema-valid documents and queries.

## Contract boundary

- SDA canonical IDs remain identity.
- The index never becomes canonical truth.
- Engine `_score` is not a public contract field.
- Exact/prefix/token baseline behavior is driven by SDA-normalized fields, not by OpenSearch stemming.
- The custom Arabic analyzer is characterized separately with `standard + lowercase + decimal_digit + arabic_normalization`.
- No stop-word filter or stemmer is enabled in the conservative analyzer.
- Semantic/vector search is not enabled.
- Security is disabled only in the ephemeral CI/local trial container.

## Acceptance cases

The executable trial checks:

1. `F-15SA` exact name;
2. `F15SA` compact alias;
3. Arabic Typhoon with diacritics;
4. RSAF with an alef variant;
5. entity/manufacturer/country filtering;
6. whole-token isolation (`air` does not match `chair`);
7. deterministic ranking for shared `fighter` tokens;
8. no Q/P backend identity in indexed trial payloads;
9. conservative Arabic analyzer tokens through `_analyze`;
10. exact engine version pin (`3.8.0`).

## Local execution

Start a disposable node using the same configuration as CI:

```bash
docker run --rm -d \
  --name sda-opensearch-trial \
  -p 127.0.0.1:9200:9200 \
  -e discovery.type=single-node \
  -e DISABLE_SECURITY_PLUGIN=true \
  -e DISABLE_INSTALL_DEMO_CONFIG=true \
  -e 'OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m' \
  opensearchproject/opensearch:3.8.0
```

After `http://127.0.0.1:9200` is healthy:

```bash
python spikes/opensearch/run_trial.py
```

The script emits JSON evidence and exits non-zero on any contract divergence.

## Claim ceiling

A passing run qualifies only the bounded M3 downstream lexical-index mechanism. It does not qualify production security, HA, backup/recovery, upgrades, target-scale performance, semantic/vector relevance, or final deployment topology.
