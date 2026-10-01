"""Synthetic 1M-row policy-location generator.

Distributes policies across US states using population-proportional weights,
with coastal-zone uplift for hurricane-exposed states. Each policy gets a
lat/lon jittered around a state anchor point, a total insured value drawn
from a lognormal distribution, and peril-relevant attributes.

This is 100% synthetic data. No real policyholder information.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# state -> (anchor lat, anchor lon, spread_deg, population weight, coastal?)
STATE_ANCHORS: dict[str, tuple[float, float, float, float, bool]] = {
    "AL": (32.78, -86.83, 1.2, 5.0, True), "AK": (64.20, -152.49, 2.5, 0.73, True),
    "AZ": (34.27, -111.66, 1.4, 7.3, False), "AR": (34.90, -92.44, 1.1, 3.0, False),
    "CA": (37.20, -119.61, 1.8, 39.0, True), "CO": (39.00, -105.55, 1.3, 5.8, False),
    "CT": (41.62, -72.65, 0.5, 3.6, True), "DE": (38.99, -75.50, 0.4, 1.0, True),
    "FL": (28.63, -82.45, 1.5, 22.0, True), "GA": (32.64, -83.44, 1.3, 10.9, True),
    "HI": (20.90, -156.98, 0.6, 1.4, True), "ID": (44.39, -114.66, 1.2, 1.9, False),
    "IL": (40.04, -89.20, 1.4, 12.6, False), "IN": (39.90, -86.28, 1.1, 6.8, False),
    "IA": (42.08, -93.50, 1.2, 3.2, False), "KS": (38.49, -98.38, 1.3, 2.9, False),
    "KY": (37.53, -84.90, 1.1, 4.5, False), "LA": (31.05, -91.99, 1.2, 4.6, True),
    "ME": (45.37, -68.97, 1.0, 1.4, True), "MD": (38.97, -76.79, 0.7, 6.2, True),
    "MA": (42.26, -71.81, 0.6, 7.0, True), "MI": (44.35, -85.41, 1.4, 10.0, False),
    "MN": (46.39, -94.64, 1.4, 5.7, False), "MS": (32.74, -89.67, 1.1, 2.9, True),
    "MO": (38.36, -92.46, 1.3, 6.2, False), "MT": (47.05, -109.63, 1.5, 1.1, False),
    "NE": (41.54, -99.80, 1.3, 2.0, False), "NV": (39.33, -116.63, 1.5, 3.2, False),
    "NH": (43.68, -71.58, 0.7, 1.4, True), "NJ": (40.19, -74.67, 0.7, 9.3, True),
    "NM": (34.43, -106.11, 1.4, 2.1, False), "NY": (42.95, -75.53, 1.3, 19.8, True),
    "NC": (35.54, -79.39, 1.3, 10.7, True), "ND": (47.45, -100.47, 1.3, 0.8, False),
    "OH": (40.29, -82.79, 1.2, 11.8, False), "OK": (35.59, -97.51, 1.3, 4.0, False),
    "OR": (43.94, -120.56, 1.4, 4.2, True), "PA": (40.88, -77.80, 1.2, 13.0, False),
    "RI": (41.68, -71.52, 0.3, 1.1, True), "SC": (33.92, -80.90, 1.1, 5.3, True),
    "SD": (44.44, -100.23, 1.3, 0.9, False), "TN": (35.86, -86.35, 1.2, 7.0, False),
    "TX": (31.48, -99.33, 2.0, 30.0, True), "UT": (39.31, -111.67, 1.2, 3.4, False),
    "VT": (44.07, -72.67, 0.6, 0.6, False), "VA": (37.52, -78.66, 1.2, 8.7, True),
    "WA": (47.38, -120.45, 1.2, 7.8, True), "WV": (38.64, -80.62, 0.9, 1.8, False),
    "WI": (44.63, -89.99, 1.3, 5.9, False), "WY": (42.99, -107.55, 1.3, 0.6, False),
    "DC": (38.91, -77.01, 0.15, 0.7, False),
}

CONSTRUCTION = ["Frame", "Masonry", "Brick", "Concrete", "Steel"]
OCCUPANCY = ["Residential", "Commercial", "Industrial", "Mixed-Use"]


def generate_policies(n: int = 1_000_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    states = list(STATE_ANCHORS.keys())
    weights = np.array([STATE_ANCHORS[s][3] for s in states], dtype=float)
    # coastal uplift: 1.25x for coastal states (1M policies skew coastal)
    for i, s in enumerate(states):
        if STATE_ANCHORS[s][4]:
            weights[i] *= 1.25
    weights /= weights.sum()

    chosen = rng.choice(len(states), size=n, p=weights)
    state_arr = np.array(states, dtype=object)[chosen]
    anchors = np.array([STATE_ANCHORS[s] for s in states], dtype=float)

    lat_c = anchors[chosen, 0]
    lon_c = anchors[chosen, 1]
    spread = anchors[chosen, 2]
    lat = lat_c + rng.normal(0, spread * 0.45, size=n)
    lon = lon_c + rng.normal(0, spread * 0.45, size=n)
    lat = np.clip(lat, 18.0, 71.5)
    lon = np.clip(lon, -171.0, -66.0)

    tiv = rng.lognormal(mean=12.4, sigma=0.65, size=n)  # median ~ $243k
    tiv = np.clip(tiv, 25_000, 25_000_000).round(2)

    df = pd.DataFrame({
        "policy_id": [f"POL-{i:07d}" for i in range(1, n + 1)],
        "lat": lat.round(6),
        "lon": lon.round(6),
        "state": state_arr,
        "total_insured_value": tiv,
        "construction_type": rng.choice(CONSTRUCTION, size=n, p=[0.45, 0.25, 0.15, 0.08, 0.07]),
        "occupancy": rng.choice(OCCUPANCY, size=n, p=[0.78, 0.14, 0.05, 0.03]),
        "year_built": rng.integers(1920, 2026, size=n),
        "coastal_zone": np.array([STATE_ANCHORS[s][4] for s in state_arr]),
    })
    return df
