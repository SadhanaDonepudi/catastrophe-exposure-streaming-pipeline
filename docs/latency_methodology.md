# Latency Methodology

## What is measured

End-to-end **alert-to-flag latency** per alert, inside the local simulation:

- **Ingest timestamp** (`ingest_ns`): `time.perf_counter_ns()` captured by the
  producer thread at the moment an alert event is placed on its partition
  queue. This is the local analogue of a record arriving on a Kinesis shard.
- **Flag timestamp** (`flag_ns`): `time.perf_counter_ns()` captured by the
  consumer immediately after the spatial join completes and before flags are
  written to the local store. This is the local analogue of the Lambda
  invocation finishing its DynamoDB writes.
- **Latency** = `(flag_ns − ingest_ns) / 1e6` ms. It therefore includes queue
  wait time, the STRtree point-in-polygon join over the full 1M-row table,
  and result materialization.

Reported statistics: p50, p95, max, and mean over all streamed alerts
(n = 12 in the reference run), plus per-alert values in `outputs/metrics.json`.

## What is NOT measured

- Network transit, Kinesis shard propagation, Lambda cold starts, DynamoDB
  write latency, Athena query time, and Power BI refresh — none of these
  exist locally.
- The resume's **"within 2 minutes"** figure is the **production design
  target** for the AWS deployment (alert issuance → flagged exposure visible
  to claims/catastrophe teams). It is not a guarantee and not a local
  measurement. Local latencies are orders of magnitude below it because the
  join runs in-process against an in-memory index; the honest claim is the
  measured distribution in the README, not the 2-minute target.

## Reproducing

```bash
~/workspace/github-projects/.venv/bin/python -m src.run_pipeline   # or: python -m src.run_pipeline with deps installed
cat outputs/metrics.json
```
