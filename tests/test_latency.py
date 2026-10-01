import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from src.aggregation import latency_summary
from src.streaming_engine import AlertLatency

def test_latency_ms_computation():
    r = AlertLatency("A", "flood", ingest_ns=1_000_000_000, flag_ns=1_250_000_000,
                     flagged_policies=3, exposed_tiv=100.0)
    assert r.latency_ms == 250.0

def test_latency_summary_percentiles():
    recs = [AlertLatency(f"A{i}", "flood", 0, int(i * 1e6), 0, 0.0) for i in range(1, 101)]
    s = latency_summary(recs)
    assert s["count"] == 100
    assert abs(s["p50_ms"] - 50.5) < 1.0
    assert s["max_ms"] == 100.0
    assert s["p95_ms"] > s["p50_ms"]

def test_latency_summary_empty():
    s = latency_summary([])
    assert s["count"] == 0 and s["max_ms"] == 0.0
