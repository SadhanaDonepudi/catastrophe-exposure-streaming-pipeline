"""End-to-end local pipeline: generate -> index -> stream -> aggregate -> report.

LOCAL STREAMING SIMULATION — no AWS, no live NWS feed. Synthetic alerts are
replayed on a timed schedule into in-process queues; a consumer performs the
spatial join against the full 1M-row policy table via a shapely STRtree.

Outputs (outputs/): exposure CSVs, metrics.json, exposure_report.html.
"""
from __future__ import annotations

import json
import os
import time

import duckdb

from src.aggregation import (exposure_by_peril, exposure_by_state,
                             exposure_by_state_peril, latency_summary)
from src.dashboard import render_report
from src.generate_alerts import generate_alerts
from src.generate_policies import generate_policies
from src.streaming_engine import LocalFlagStore, PolicyIndex, run_stream

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs")


def main() -> dict:
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    policies_path = os.path.join(DATA, "policies.parquet")
    db_path = os.path.join(OUT, "flags.duckdb")

    if os.path.exists(policies_path):
        con = duckdb.connect()
        policies = con.execute(f"SELECT * FROM read_parquet('{policies_path}')").df()
        con.close()
        print(f"Loaded {len(policies):,} policies from {policies_path}")
    else:
        t0 = time.time()
        policies = generate_policies(n=1_000_000, seed=42)
        con = duckdb.connect()
        con.register("p", policies)
        con.execute(f"COPY p TO '{policies_path}' (FORMAT PARQUET)")
        con.close()
        print(f"Generated {len(policies):,} policies in {time.time()-t0:.1f}s -> {policies_path}")

    sample = policies.head(200)
    sample.to_csv(os.path.join(DATA, "sample_policies.csv"), index=False)

    t0 = time.time()
    index = PolicyIndex(policies)
    print(f"STRtree index over {len(index):,} points built in {time.time()-t0:.1f}s")

    alerts = generate_alerts()
    print(f"Streaming {len(alerts)} synthetic alerts (all synthetic, no live NWS feed)...")
    if os.path.exists(db_path):
        os.remove(db_path)
    store = LocalFlagStore(db_path)
    latencies = run_stream(alerts, index, store, emit_interval_s=0.25, n_partitions=4)
    store.close()

    lat = latency_summary(latencies)
    by_peril = exposure_by_peril(db_path)
    by_state = exposure_by_state(db_path)
    by_sp = exposure_by_state_peril(db_path)
    by_peril.to_csv(os.path.join(OUT, "exposure_by_peril.csv"), index=False)
    by_state.to_csv(os.path.join(OUT, "exposure_by_state.csv"), index=False)
    by_sp.to_csv(os.path.join(OUT, "exposure_by_state_peril.csv"), index=False)

    total_flags = int(sum(r.flagged_policies for r in latencies))
    total_tiv = float(by_peril["exposed_tiv"].sum()) if not by_peril.empty else 0.0
    metrics = {
        "policies_joined": len(policies),
        "sampling": "none — full 1M-row table joined via STRtree",
        "alerts_streamed": len(alerts),
        "total_policy_flags": total_flags,
        "total_exposed_tiv": round(total_tiv, 2),
        "latency_ms": lat,
        "per_alert": [{"alert_id": r.alert_id, "peril": r.peril,
                       "flagged_policies": r.flagged_policies,
                       "exposed_tiv": round(r.exposed_tiv, 2),
                       "latency_ms": round(r.latency_ms, 2)} for r in latencies],
    }
    with open(os.path.join(OUT, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    html_out = render_report(by_peril, by_state, by_sp, lat, len(policies), len(alerts))
    with open(os.path.join(OUT, "exposure_report.html"), "w") as f:
        f.write(html_out)

    print(json.dumps(metrics["latency_ms"], indent=2))
    print(f"Total flags: {total_flags:,} | Total exposed TIV: ${total_tiv:,.2f}")
    print(f"Outputs in {OUT}")
    return metrics


if __name__ == "__main__":
    main()
