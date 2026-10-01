# Data Dictionary

All data in this repo is synthetic. No real policyholder or live weather data.

## Policy locations (`data/policies.parquet`, generated; sample in `data/sample_policies.csv`)

| Column | Type | Description |
|---|---|---|
| `policy_id` | string | Synthetic ID, `POL-0000001` … `POL-1000000` |
| `lat` | float | Latitude, jittered around a state anchor (clipped 18.0–71.5) |
| `lon` | float | Longitude, jittered around a state anchor (clipped −171.0–−66.0) |
| `state` | string | US state / DC code; population-weighted with 1.25× coastal uplift |
| `total_insured_value` | float | TIV in USD; lognormal (median ≈ $243k), clipped $25k–$25M |
| `construction_type` | string | Frame / Masonry / Brick / Concrete / Steel |
| `occupancy` | string | Residential / Commercial / Industrial / Mixed-Use |
| `year_built` | int | 1920–2025 |
| `coastal_zone` | bool | True for coastal states (hurricane exposure relevance) |

Generation: `src/generate_policies.py`, seed 42, weights = state population
proxy × 1.25 if coastal.

## Synthetic alerts (`src/generate_alerts.py`)

| Field | Description |
|---|---|
| `alert_id` | `SYN-2026-001` … `SYN-2026-012` (SYN = synthetic) |
| `peril` | hurricane / tornado / flood / wildfire / severe_thunderstorm |
| `severity` | Moderate / Severe / Extreme (NWS-style) |
| `headline_states` | States named in the synthetic headline |
| `effective` / `expires` | Alert validity window (12 h) |
| `polygon` | Axis-aligned box polygon (shapely) around a peril-typical center |

## Flag store (`outputs/flags.duckdb` — DuckDB stand-in for DynamoDB)

**`flagged_exposures`**: `alert_id`, `peril`, `policy_id`, `state`,
`total_insured_value`, `flagged_at_ns` (perf_counter_ns at flag emission).

**`alert_latency`**: `alert_id`, `peril`, `ingest_ns`, `flag_ns`,
`latency_ms`, `flagged_policies`, `exposed_tiv`.

## Aggregation outputs (`outputs/`)

- `exposure_by_peril.csv` — peril, flagged_policies, exposed_tiv
- `exposure_by_state.csv` — state, flagged_policies, exposed_tiv
- `exposure_by_state_peril.csv` — state × peril breakdown
- `metrics.json` — run summary incl. latency percentiles and per-alert detail
- `exposure_report.html` — static dashboard report (stand-in for Power BI)
