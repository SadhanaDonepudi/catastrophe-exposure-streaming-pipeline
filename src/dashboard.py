"""Dashboard deliverable: static HTML exposure report.

Renders the local run outputs (state x peril tables, latency stats) into a
self-contained static HTML report with inline SVG bar charts. This stands
in for the Power BI deliverable — it is NOT a live .pbix file. The full
Power BI spec (pages, visuals, DAX measures, Athena equivalents) lives in
docs/dashboard_spec.md.
"""
from __future__ import annotations

import html

import pandas as pd


def _fmt_money(v: float) -> str:
    if v >= 1e9:
        return f"${v/1e9:,.2f}B"
    if v >= 1e6:
        return f"${v/1e6:,.1f}M"
    return f"${v:,.0f}"


def _bar_chart(df: pd.DataFrame, label_col: str, value_col: str, title: str,
               width: int = 720, row_h: int = 26) -> str:
    if df.empty:
        return f"<h3>{html.escape(title)}</h3><p>No data.</p>"
    maxv = float(df[value_col].max()) or 1.0
    rows = []
    for _, r in df.head(15).iterrows():
        w = max(2, int(width * 0.62 * float(r[value_col]) / maxv))
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{html.escape(str(r[label_col]))}</span>'
            f'<span class="bar" style="width:{w}px"></span>'
            f'<span class="bar-val">{_fmt_money(float(r[value_col]))}</span></div>')
    return f"<h3>{html.escape(title)}</h3>" + "".join(rows)


def _table(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>No rows.</p>"
    cols = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = ""
    for _, r in df.iterrows():
        tds = ""
        for c in df.columns:
            v = r[c]
            if isinstance(v, float) and c == "exposed_tiv":
                tds += f"<td>{_fmt_money(v)} ({v:,.2f})</td>"
            elif isinstance(v, float):
                tds += f"<td>{v:,.2f}</td>"
            else:
                tds += f"<td>{html.escape(str(v))}</td>"
        body += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{cols}</tr></thead><tbody>{body}</tbody></table>"


def render_report(by_peril: pd.DataFrame, by_state: pd.DataFrame,
                  by_state_peril: pd.DataFrame, latency: dict,
                  n_policies: int, n_alerts: int) -> str:
    total_tiv = float(by_peril["exposed_tiv"].sum()) if not by_peril.empty else 0.0
    total_flags = int(by_peril["flagged_policies"].sum()) if not by_peril.empty else 0
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Catastrophe Exposure — Local Streaming Run Report</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;margin:32px;color:#1a1a2e;max-width:980px}}
h1{{color:#7b1d1d}} h3{{color:#333;margin-top:28px}}
table{{border-collapse:collapse;margin:10px 0}} th,td{{border:1px solid #bbb;padding:5px 10px;text-align:right}}
th{{background:#7b1d1d;color:#fff}} td:first-child,th:first-child{{text-align:left}}
.bar-row{{display:flex;align-items:center;gap:8px;margin:3px 0}}
.bar-label{{width:130px;text-align:right;font-size:13px}}
.bar{{display:inline-block;height:16px;background:#c0392b;border-radius:2px}}
.bar-val{{font-size:13px}} .note{{background:#fdf3e7;border-left:4px solid #c0392b;padding:10px 14px}}
</style></head><body>
<h1>Catastrophe Exposure Streaming Pipeline — Local Run Report</h1>
<p class="note"><strong>Local simulation output.</strong> Alerts are synthetic NWS-style
polygons replayed through an in-process stream (queue consumer standing in for
Kinesis + Lambda; DuckDB standing in for DynamoDB). This static report stands in for the
Power BI deliverable — it is <em>not</em> a live .pbix. See <code>docs/dashboard_spec.md</code>
for the full Power BI / Athena specification.</p>
<h3>Run summary</h3>
<table><tbody>
<tr><th>Policies joined (full table)</th><td>{n_policies:,}</td></tr>
<tr><th>Synthetic alerts streamed</th><td>{n_alerts}</td></tr>
<tr><th>Policy-flags emitted (policy-alert pairs)</th><td>{total_flags:,}</td></tr>
<tr><th>Total exposed insured value (sum over flags)</th><td>{_fmt_money(total_tiv)} ({total_tiv:,.2f})</td></tr>
<tr><th>Alert-to-flag latency p50</th><td>{latency['p50_ms']} ms</td></tr>
<tr><th>Alert-to-flag latency p95</th><td>{latency['p95_ms']} ms</td></tr>
<tr><th>Alert-to-flag latency max</th><td>{latency['max_ms']} ms</td></tr>
</tbody></table>
{_bar_chart(by_peril, "peril", "exposed_tiv", "Exposed TIV by peril")}
{_bar_chart(by_state, "state", "exposed_tiv", "Exposed TIV by state (top 15)")}
<h3>Exposed TIV by peril</h3>{_table(by_peril)}
<h3>Exposed TIV by state</h3>{_table(by_state)}
<h3>Exposed TIV by state and peril</h3>{_table(by_state_peril)}
<p><em>Latency measured locally from ingest (producer enqueue) to flag emission
(consumer write) with perf_counter_ns; methodology in docs/latency_methodology.md.
The resume's "within 2 minutes" figure is the production design target for the
AWS deployment, not a local measurement.</em></p>
</body></html>"""
