"""Aggregation: exposed total insured value by state and peril.

Reads the local flag store (DuckDB stand-in for DynamoDB) and produces
the state x peril exposure tables that feed the dashboard deliverable.
In production this maps to Athena queries over the DynamoDB/S3 export;
see docs/dashboard_spec.md for the Athena SQL equivalents.
"""
from __future__ import annotations

import duckdb
import pandas as pd


def exposure_by_state_peril(db_path: str) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT state, peril,
               COUNT(*) AS flagged_policies,
               ROUND(SUM(total_insured_value), 2) AS exposed_tiv
        FROM flagged_exposures
        GROUP BY state, peril
        ORDER BY exposed_tiv DESC
    """).df()
    con.close()
    return df


def exposure_by_peril(db_path: str) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT peril, COUNT(*) AS flagged_policies,
               ROUND(SUM(total_insured_value), 2) AS exposed_tiv
        FROM flagged_exposures GROUP BY peril ORDER BY exposed_tiv DESC
    """).df()
    con.close()
    return df


def exposure_by_state(db_path: str) -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT state, COUNT(*) AS flagged_policies,
               ROUND(SUM(total_insured_value), 2) AS exposed_tiv
        FROM flagged_exposures GROUP BY state ORDER BY exposed_tiv DESC
    """).df()
    con.close()
    return df


def latency_summary(latencies) -> dict:
    """Percentile summary (ms) over measured alert-to-flag latencies."""
    import numpy as np
    ms = np.array([r.latency_ms for r in latencies], dtype=float)
    if len(ms) == 0:
        return {"count": 0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0, "mean_ms": 0.0}
    return {
        "count": int(len(ms)),
        "p50_ms": round(float(np.percentile(ms, 50)), 2),
        "p95_ms": round(float(np.percentile(ms, 95)), 2),
        "max_ms": round(float(ms.max()), 2),
        "mean_ms": round(float(ms.mean()), 2),
    }
