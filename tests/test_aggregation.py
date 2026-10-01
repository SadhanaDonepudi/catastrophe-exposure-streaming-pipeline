import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from src.aggregation import exposure_by_peril, exposure_by_state, exposure_by_state_peril
from src.generate_alerts import generate_alerts, _box_polygon, AlertEvent
from src.streaming_engine import LocalFlagStore, PolicyIndex, run_stream
from datetime import datetime, timezone

def _policies():
    return pd.DataFrame({
        "policy_id": ["P1", "P2", "P3"],
        "lat": [35.4, 35.5, 40.0], "lon": [-97.5, -97.4, -80.0],
        "state": ["OK", "OK", "OH"],
        "total_insured_value": [100_000.0, 250_000.0, 999_000.0]})

def test_aggregation_reconciles_with_flags():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "flags.duckdb")
        store = LocalFlagStore(db)
        alert = AlertEvent("T-1", "tornado", "Severe", "OK",
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           _box_polygon(35.45, -97.45, 0.3))
        recs = run_stream([alert], PolicyIndex(_policies()), store, emit_interval_s=0.0)
        store.close()
        assert recs[0].flagged_policies == 2
        assert recs[0].exposed_tiv == 350_000.0
        bp = exposure_by_peril(db)
        assert bp.iloc[0]["flagged_policies"] == 2
        assert abs(float(bp.iloc[0]["exposed_tiv"]) - 350_000.0) < 0.01
        bs = exposure_by_state(db)
        assert bs.iloc[0]["state"] == "OK"
        bsp = exposure_by_state_peril(db)
        assert len(bsp) == 1

def test_multi_alert_tiv_sums():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "flags.duckdb")
        store = LocalFlagStore(db)
        a1 = AlertEvent("T-1", "tornado", "Severe", "OK",
                        datetime.now(timezone.utc), datetime.now(timezone.utc),
                        _box_polygon(35.45, -97.45, 0.3))
        a2 = AlertEvent("T-2", "flood", "Moderate", "OH",
                        datetime.now(timezone.utc), datetime.now(timezone.utc),
                        _box_polygon(40.0, -80.0, 0.3))
        recs = run_stream([a1, a2], PolicyIndex(_policies()), store, emit_interval_s=0.0)
        store.close()
        total = sum(r.exposed_tiv for r in recs)
        bp = exposure_by_peril(db)
        assert abs(float(bp["exposed_tiv"].sum()) - total) < 0.01
