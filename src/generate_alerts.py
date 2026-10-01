"""Synthetic NWS-style severe-weather alert polygon generator.

All alerts are SYNTHETIC — they mimic the structure of National Weather
Service alerts (event type, severity, effective/expiry, polygon geometry)
but are generated locally for simulation. No live NWS feed is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from shapely.geometry import Polygon

PERILS = ["hurricane", "tornado", "flood", "wildfire", "severe_thunderstorm"]

# (alert_id, peril, center lat, center lon, half-width deg, severity, headline states)
_ALERT_DEFS = [
    ("SYN-2026-001", "hurricane", 26.8, -81.8, 1.6, "Extreme", "FL"),
    ("SYN-2026-002", "hurricane", 30.0, -89.5, 1.4, "Severe", "LA,MS,AL"),
    ("SYN-2026-003", "hurricane", 33.5, -79.0, 1.2, "Severe", "SC,NC"),
    ("SYN-2026-004", "tornado", 35.4, -97.5, 0.7, "Extreme", "OK"),
    ("SYN-2026-005", "tornado", 38.5, -98.4, 0.8, "Severe", "KS"),
    ("SYN-2026-006", "flood", 40.0, -89.2, 1.1, "Moderate", "IL"),
    ("SYN-2026-007", "flood", 32.7, -89.7, 1.0, "Moderate", "MS"),
    ("SYN-2026-008", "wildfire", 37.2, -119.6, 1.5, "Severe", "CA"),
    ("SYN-2026-009", "wildfire", 34.3, -111.7, 1.1, "Moderate", "AZ"),
    ("SYN-2026-010", "severe_thunderstorm", 41.5, -93.5, 1.0, "Severe", "IA,IL"),
    ("SYN-2026-011", "severe_thunderstorm", 39.0, -86.3, 0.9, "Moderate", "IN,OH"),
    ("SYN-2026-012", "hurricane", 28.5, -96.0, 1.4, "Severe", "TX"),
]


def _box_polygon(lat: float, lon: float, half: float) -> Polygon:
    """Axis-aligned box polygon around a center (simplified alert geometry)."""
    return Polygon([
        (lon - half, lat - half), (lon + half, lat - half),
        (lon + half, lat + half), (lon - half, lat + half),
        (lon - half, lat - half),
    ])


@dataclass
class AlertEvent:
    alert_id: str
    peril: str
    severity: str
    headline_states: str
    effective: datetime
    expires: datetime
    polygon: Polygon = field(repr=False)

    @property
    def area_desc(self) -> str:
        return f"Synthetic {self.peril} alert for {self.headline_states}"


def generate_alerts(base_time: datetime | None = None) -> list[AlertEvent]:
    if base_time is None:
        base_time = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    alerts: list[AlertEvent] = []
    for i, (aid, peril, lat, lon, half, sev, states) in enumerate(_ALERT_DEFS):
        eff = base_time + timedelta(minutes=15 * i)
        exp = eff + timedelta(hours=12)
        alerts.append(AlertEvent(
            alert_id=aid, peril=peril, severity=sev, headline_states=states,
            effective=eff, expires=exp, polygon=_box_polygon(lat, lon, half),
        ))
    return alerts
