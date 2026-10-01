# Architecture: Local Simulation → Production Mapping

This repo is a **local streaming simulation**. No AWS services and no live
National Weather Service feed are used. Every alert is synthetic. The table
below maps each local component to its production counterpart from the
resume project ("Catastrophe Exposure Streaming Pipeline — Amazon Kinesis,
AWS Lambda, DynamoDB, Athena, Power BI").

| Concern | Local (this repo) | Production (resume design) |
|---|---|---|
| Alert source | `generate_alerts.py` — 12 synthetic NWS-style polygons replayed on a timed schedule | NWS alert feed (CAP/ATOM) polled or pushed as alerts are issued |
| Stream transport | `queue.Queue` × 4 partitions; producer emits every 0.25 s | Amazon Kinesis Data Streams (sharded by alert geography) |
| Partitioning | `partition_for()` — MD5 hash of `alert_id` mod N (emulated, labeled) | Kinesis partition key on alert ID / state |
| Stream consumer | Consumer threads in `streaming_engine.py` | AWS Lambda functions triggered per Kinesis batch |
| Spatial join | shapely `STRtree` point-in-polygon over the full 1M-row table | Lambda loads a spatial index (or queries a geospatial store) per invocation |
| Flag store | DuckDB file `outputs/flags.duckdb` (labeled stand-in) | Amazon DynamoDB (policy flags keyed by alert + policy) |
| Aggregation | DuckDB SQL in `aggregation.py` | Amazon Athena over the DynamoDB export / S3 data lake |
| Dashboard | Static HTML report `outputs/exposure_report.html` (not a .pbix) | Power BI dashboard querying Athena |
| Latency SLO | Measured locally (see `latency_methodology.md`) | "Within 2 minutes" is the **production design target**, not a local measurement |

## Data flow (local)

```
generate_policies (1M rows -> parquet)
        |
   PolicyIndex (STRtree)
        |
generate_alerts --timed--> partitioned queues --consumer--> spatial join
                                                              |
                                          flags + latency -> DuckDB store
                                                              |
                              aggregation SQL -> CSVs + static HTML report
```

## Scaling notes

- The full 1M-row table is joined — no sampling. STRtree build is a one-time
  cost; each alert join is a bbox-candidate query plus strict `contains`
  checks on candidates only.
- In production, the same join logic moves into Lambda with the policy
  index pre-loaded (or replaced by a geospatial query against a store such
  as DynamoDB + geohash keys), and Athena replaces the local DuckDB
  aggregation SQL verbatim (see `dashboard_spec.md`).
