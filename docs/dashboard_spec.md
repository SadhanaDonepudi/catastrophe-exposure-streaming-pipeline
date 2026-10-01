# Power BI Dashboard Spec (deliverable: spec + static report)

> **Honesty note:** This repo does **not** contain a live `.pbix` file and
> does not connect to Power BI, Athena, or any AWS service. The deliverables
> are (1) this written specification and (2) a rendered static summary,
> `outputs/exposure_report.html`, produced from the actual local run
> (DuckDB aggregation over the local flag store). In production, Power BI
> queries Amazon Athena; every Athena query below has a DuckDB equivalent
> that was actually executed locally in `src/aggregation.py`.

## Page 1 — Executive exposure overview

| Visual | Source | Production (Athena) | Local equivalent (DuckDB, executed) |
|---|---|---|---|
| KPI card: total exposed TIV | `exposure_by_peril` roll-up | `SELECT SUM(total_insured_value) FROM flagged_exposures` | Same SQL over `outputs/flags.duckdb` |
| KPI card: policies flagged | flag store | `SELECT COUNT(*) FROM flagged_exposures` | Same |
| Bar: exposed TIV by peril | `exposure_by_peril.csv` | `SELECT peril, SUM(total_insured_value) … GROUP BY peril` | `exposure_by_peril()` |
| Bar: exposed TIV by state | `exposure_by_state.csv` | `… GROUP BY state` | `exposure_by_state()` |
| Slicers | peril, state, severity | DirectQuery filters on Athena view | CSV filters in the static report |

## Page 2 — State × peril drill-down

- Matrix visual: rows = state, columns = peril, values = exposed TIV and
  flagged policy count (source: `exposure_by_state_peril.csv`).
- Athena: `SELECT state, peril, COUNT(*), SUM(total_insured_value) FROM flagged_exposures GROUP BY state, peril`
- DuckDB equivalent executed locally: `exposure_by_state_peril()`.

## Page 3 — Streaming operations

- Per-alert table: alert, peril, flagged policies, exposed TIV, latency ms
  (source: `alert_latency` table / `metrics.json` per-alert detail).
- Latency KPI cards: p50 / p95 / max alert-to-flag ms.
- Production note: the "within 2 minutes" figure is the design target for
  this page's SLO tile; the local build reports measured values only.

## DAX measures (production Power BI model)

```dax
Exposed TIV = SUM ( flagged_exposures[total_insured_value] )
Policies Flagged = COUNTROWS ( flagged_exposures )
Exposed TIV by Peril = CALCULATE ( [Exposed TIV], ALLEXCEPT ( flagged_exposures, flagged_exposures[peril] ) )
Share of Exposed TIV = DIVIDE ( [Exposed TIV], CALCULATE ( [Exposed TIV], ALL ( flagged_exposures ) ) )
Distinct Policies Exposed = DISTINCTCOUNT ( flagged_exposures[policy_id] )
```

## Refresh model

- Production: Athena-backed DirectQuery (or hourly Import refresh of the
  Athena view), so claims and catastrophe teams see near-real-time exposed
  TIV by state and peril as new alerts are flagged.
- Local: the static HTML report is regenerated per run by
  `src/dashboard.py` from the same aggregation outputs.
