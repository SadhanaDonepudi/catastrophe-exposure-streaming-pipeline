import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from src.generate_alerts import generate_alerts
from src.streaming_engine import LocalFlagStore, PolicyIndex, partition_for, run_stream

def _policies():
    return pd.DataFrame({
        "policy_id": ["P1", "P2"], "lat": [26.8, 35.4], "lon": [-81.8, -97.5],
        "state": ["FL", "OK"], "total_insured_value": [100_000.0, 200_000.0]})

def test_stream_returns_all_alerts_in_order():
    alerts = generate_alerts()
    with tempfile.TemporaryDirectory() as d:
        store = LocalFlagStore(os.path.join(d, "f.duckdb"))
        recs = run_stream(alerts, PolicyIndex(_policies()), store, emit_interval_s=0.0)
        store.close()
    assert [r.alert_id for r in recs] == [a.alert_id for a in alerts]

def test_latency_nonnegative_and_flag_after_ingest():
    alerts = generate_alerts()[:3]
    with tempfile.TemporaryDirectory() as d:
        store = LocalFlagStore(os.path.join(d, "f.duckdb"))
        recs = run_stream(alerts, PolicyIndex(_policies()), store, emit_interval_s=0.01)
        store.close()
    for r in recs:
        assert r.flag_ns >= r.ingest_ns
        assert r.latency_ms >= 0

def test_partition_assignment_deterministic():
    assert partition_for("SYN-2026-001", 4) == partition_for("SYN-2026-001", 4)
    assert 0 <= partition_for("SYN-2026-001", 4) < 4
