# Catastrophe Exposure Streaming Pipeline

Flags insured properties inside active severe-weather alert zones and
publishes exposed total insured value (TIV) by state and peril for claims
and catastrophe teams.

> ⚠️ **Local streaming simulation — read this first.** This repo contains
> **no AWS services** (no Kinesis, Lambda, DynamoDB, or Athena) and **no
> live National Weather Service feed**. Synthetic NWS-style alert polygons
> are replayed on a timed schedule into in-process queues; a consumer
> performs the geospatial join locally. It is a faithful local replica of
> the production design described in the resume project *"Catastrophe
> Exposure Streaming Pipeline — Amazon Kinesis, AWS Lambda, DynamoDB,
> Athena, Power BI"*. Every number below is a measured local output.
> The full local → production mapping is in
> [`docs/architecture.md`](docs/architecture.md).

## Measured results (actual local run)

| Metric | Measured |
|---|---|
| Policy rows joined | **1,000,000 (full table — no sampling)** |
| Synthetic alerts streamed | 12 (hurricane ×4, tornado ×2, flood ×2, wildfire ×2, severe thunderstorm ×2) |
| Policy-flags emitted (policy×alert pairs) | 217,577 |
| Total exposed TIV (summed over flags) | $65,183,082,748.00 |
| Alert-to-flag latency p50 | 82.03 ms |
| Alert-to-flag latency p95 | 1,065.41 ms |
| Alert-to-flag latency max | 1,245.45 ms |
| Alert-to-flag latency mean | 251.16 ms |

Latency is measured with `perf_counter_ns()` at ingest (producer enqueue)
and at flag emission (consumer completes the join and writes flags), so it
includes queue wait plus the full spatial join. Methodology:
[`docs/latency_methodology.md`](docs/latency_methodology.md).

**On the resume's "within 2 minutes" figure:** that is the **production
design target** for the AWS deployment (alert issuance → flagged exposure
visible to claims/catastrophe teams, including Kinesis propagation, Lambda
execution, DynamoDB writes, Athena query, and Power BI refresh). It is
**not** a local measurement and **not** a guarantee. Locally, the in-memory
STRtree join is far faster (above) precisely because none of those network
and service hops exist here.

**On sampling:** none. The full 1M-row policy table was generated and
joined. A shapely STRtree spatial index makes the full join fast enough
that no sampling was needed; had sampling been used it would be stated
here with the exact sampled count.

### Exposed TIV by peril (actual run)

| Peril | Flagged policies | Exposed TIV |
|---|---|---|
| wildfire | 127,427 | $38,116,388,581.98 |
| flood | 36,527 | $10,996,086,107.25 |
| hurricane | 27,960 | $8,375,962,340.15 |
| severe_thunderstorm | 14,588 | $4,383,124,565.37 |
| tornado | 11,075 | $3,311,521,153.25 |

### Exposed TIV by state — top 5 (actual run)

| State | Flagged policies | Exposed TIV |
|---|---|---|
| CA | 111,331 | $33,273,213,694.85 |
| IL | 27,732 | $8,360,229,458.42 |
| FL | 23,964 | $7,171,116,597.58 |
| AZ | 16,083 | $4,839,719,144.44 |
| MS | 8,826 | $2,643,860,924.44 |

Full state × peril table: `outputs/exposure_by_state_peril.csv`
(regenerated per run; see Run below). Per-alert detail (flag counts,
exposed TIV, latency) is in `outputs/metrics.json`.

> Note on the distribution: the California wildfire alert (SYN-2026-008)
> dominates exposure because California holds the largest policy share and
> its synthetic alert polygon is wide. Alert SYN-2026-012 (Texas hurricane)
> flagged only 59 synthetic policies — the generator's Texas policies are
> spread over a wide anchor area, so few fall inside that polygon. Both are
> artifacts of the synthetic data, reported as measured.

## How it works

```
generate_policies (1M rows -> parquet, gitignored)
        |
   PolicyIndex (shapely STRtree over 1M points)
        |
generate_alerts --timed 0.25s--> 4 partitioned queues --consumers--> point-in-polygon join
        (Kafka-style partitioning emulated by hash of alert_id — not a broker)
                                                              |
                              flags + per-alert latency -> DuckDB store
                              (local stand-in for DynamoDB, labeled as such)
                                                              |
              aggregation SQL -> exposure CSVs + static HTML report
```

- `src/generate_policies.py` — synthetic 1M-row policy table
  (population-weighted by state, 1.25× coastal uplift, lognormal TIV).
- `src/generate_alerts.py` — 12 synthetic NWS-style alert polygons, all
  labeled synthetic (`SYN-2026-*`).
- `src/streaming_engine.py` — timed producer, partitioned in-process
  queues, consumer threads, STRtree join, DuckDB flag store, latency
  capture.
- `src/aggregation.py` — exposed TIV by state / peril / state×peril.
- `src/dashboard.py` — renders the static report (see below).
- `src/run_pipeline.py` — end-to-end runner.

## Dashboard deliverable

This repo ships a **dashboard specification plus a rendered static
report** — **not** a live `.pbix` file and no Power BI/Athena connection:

- [`docs/dashboard_spec.md`](docs/dashboard_spec.md) — Power BI pages,
  visuals, DAX measures, and the Athena queries for production, each
  paired with the DuckDB equivalent actually executed locally.
- `outputs/exposure_report.html` — static report (KPI table, exposed-TIV
  bar charts by peril and state, full state×peril table) rendered from
  the actual local run.

## Run

```bash
python -m pytest tests/ -q          # 12 tests
python -m src.run_pipeline          # generates 1M rows on first run (~30s), streams 12 alerts
cat outputs/metrics.json            # latency percentiles + per-alert detail
```

Dependencies: `pandas`, `duckdb`, `shapely`, `pytest` (see
`requirements.txt`). The 1M-row parquet and DuckDB store are gitignored —
only a 200-row sample (`data/sample_policies.csv`) is committed.

## Tests

12 pytest tests, all passing: polygon join correctness (known points
in/out, empty regions, strict boundary semantics), latency measurement
logic and percentile summary, aggregation reconciliation (flagged-TIV
sums match the flag store across single- and multi-alert runs), and
stream consumer ordering / partition determinism.

## Docs

- [`docs/architecture.md`](docs/architecture.md) — local → production
  (Kinesis, Lambda, DynamoDB, Athena, Power BI) mapping
- [`docs/data_dictionary.md`](docs/data_dictionary.md)
- [`docs/latency_methodology.md`](docs/latency_methodology.md)
- [`docs/dashboard_spec.md`](docs/dashboard_spec.md)

## Resume-vs-repo honesty notes

| Resume claim | What this repo actually does |
|---|---|
| "streaming National Weather Service alerts through Amazon Kinesis and AWS Lambda" | Local simulation only: synthetic alerts, in-process queues + consumer threads. No AWS, no live NWS feed. |
| "within 2 minutes" | Production design target, labeled as such. Local measured latency: p50 82 ms / p95 1.07 s / max 1.25 s (in-process, no network hops). |
| "geospatially matching them to 1M policy locations" | ✅ Real: full synthetic 1M-row table joined via STRtree, no sampling. |
| "publishing results to a Power BI dashboard queried through Amazon Athena" | Spec + static HTML report only. No .pbix, no Athena. DuckDB SQL equivalents were executed locally. |
