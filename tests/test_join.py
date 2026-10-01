import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import pytest
from shapely.geometry import Polygon
from src.generate_alerts import AlertEvent, _box_polygon
from src.streaming_engine import PolicyIndex
from datetime import datetime, timezone

def _alert(poly):
    return AlertEvent("T-1", "tornado", "Severe", "OK",
                      datetime.now(timezone.utc), datetime.now(timezone.utc), poly)

def test_known_point_inside_flagged():
    df = pd.DataFrame({"policy_id": ["A", "B"], "lat": [35.4, 40.0],
                       "lon": [-97.5, -80.0], "state": ["OK", "OH"],
                       "total_insured_value": [100000.0, 200000.0]})
    idx = PolicyIndex(df)
    hits = idx.join(_alert(_box_polygon(35.4, -97.5, 0.7)))
    assert list(hits["policy_id"]) == ["A"]

def test_point_outside_not_flagged():
    df = pd.DataFrame({"policy_id": ["A"], "lat": [45.0], "lon": [-70.0],
                       "state": ["ME"], "total_insured_value": [50000.0]})
    idx = PolicyIndex(df)
    hits = idx.join(_alert(_box_polygon(35.4, -97.5, 0.7)))
    assert hits.empty

def test_empty_candidate_region():
    df = pd.DataFrame({"policy_id": ["A"], "lat": [35.4], "lon": [-97.5],
                       "state": ["OK"], "total_insured_value": [1.0]})
    idx = PolicyIndex(df)
    hits = idx.join(_alert(_box_polygon(60.0, -150.0, 0.5)))
    assert hits.empty

def test_boundary_excluded_strict_contains():
    # Point exactly on polygon edge: shapely contains() is strict (interior only)
    poly = Polygon([(-98.0, 35.0), (-97.0, 35.0), (-97.0, 36.0), (-98.0, 36.0), (-98.0, 35.0)])
    df = pd.DataFrame({"policy_id": ["EDGE", "IN"], "lat": [35.0, 35.5],
                       "lon": [-97.5, -97.5], "state": ["OK", "OK"],
                       "total_insured_value": [1.0, 1.0]})
    idx = PolicyIndex(df)
    hits = idx.join(_alert(poly))
    assert list(hits["policy_id"]) == ["IN"]
