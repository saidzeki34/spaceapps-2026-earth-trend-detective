import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mountain_water.analysis.baseline import align_baseline


def break_gaps(table):
    """Insert display-only null rows so absent intervals never become drawn flow."""
    if table.empty:
        return table.copy()
    gaps = table.start.shift(-1) > table.end
    missing = table.loc[gaps].copy()
    missing["start"] = missing.end
    for column in missing.columns.difference(["start", "end"]):
        missing[column] = False if column == "valid" else np.nan
    return pd.concat([table, missing], ignore_index=True).sort_values("start").reset_index(drop=True)


def flow_figure(result):
    t = result.observations.copy()
    figure = go.Figure()
    if t.empty:
        return figure, {"status": "no_data"}
    if not result.baseline.empty:
        t = align_baseline(t, result.baseline, result.request.outlet.calendar_timezone)
    if result.exposure:
        t["requirement_m3s"] = result.exposure["aligned"].requirement_m3s.to_numpy()
    t = break_gaps(t)
    if not result.baseline.empty:
        figure.add_trace(go.Scatter(x=t.start, y=t.p90, line={"width": 0},
                                   name="Historical 90th percentile", hoverinfo="skip"))
        figure.add_trace(go.Scatter(x=t.start, y=t.p10, fill="tonexty", fillcolor="rgba(77,119,146,.15)",
            line={"width": 0}, name="Historical 10-90% spread", connectgaps=False))
        figure.add_trace(go.Scatter(x=t.start, y=t["mean"], name="Seasonal baseline mean",
                                   line={"color": "#8097a5", "dash": "dot"}, connectgaps=False))
    q = t.discharge_m3s.where(t.valid)
    figure.add_trace(go.Scatter(x=t.start, y=q, name="Observed daily mean",
                               line={"color": "#087f83", "width": 1.6}, connectgaps=False))
    if result.exposure:
        r = t.requirement_m3s
        figure.add_trace(go.Scatter(x=t.start, y=r, name="Selected requirement", line={"color": "#d38526"}))
        lower = q.where((q.to_numpy() < r.to_numpy()) & r.notna().to_numpy())
        upper = r.where(lower.notna().to_numpy())
        figure.add_trace(go.Scatter(x=t.start, y=lower, line={"width": 0}, showlegend=False,
                                   hoverinfo="skip", connectgaps=False))
        figure.add_trace(go.Scatter(x=t.start, y=upper, fill="tonexty", fillcolor="rgba(220,99,64,.28)",
            line={"width": 0}, name="Interval-average shortfall", connectgaps=False))
    figure.update_layout(template="plotly_white", height=410, margin={"l": 10, "r": 10, "t": 20, "b": 10},
                         yaxis_title="Discharge (m³/s)", xaxis_title="Interval start (UTC)",
                         legend={"orientation": "h", "y": 1.16}, hovermode="x unified")
    return figure, {"band": "Empirical historical variability; not a confidence or prediction interval"}


def environmental_figure(driver, observations):
    t = break_gaps(driver.table)
    observations = break_gaps(observations)
    figure = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.07,
                           subplot_titles=("NASA NDSI snow-cover index", "Valid catchment area", "Observed discharge"))
    figure.add_trace(go.Scatter(x=t.start, y=t.value, name="Mean NDSI", line={"color": "#507dad"}, connectgaps=False), row=1, col=1)
    figure.add_trace(go.Scatter(x=t.start, y=100 * t.valid_area_fraction, name="Coverage (%)", line={"color": "#96a2ab"}), row=2, col=1)
    if not observations.empty:
        figure.add_trace(go.Scatter(x=observations.start, y=observations.discharge_m3s.where(observations.valid),
            name="Flow (m³/s)", line={"color": "#087f83"}, connectgaps=False), row=3, col=1)
    figure.update_yaxes(title_text="Index (0–100)", row=1, col=1)
    figure.update_yaxes(title_text="Area (%)", range=[0, 100], row=2, col=1)
    figure.update_yaxes(title_text="m³/s", row=3, col=1)
    figure.update_layout(template="plotly_white", height=620, showlegend=False, margin={"t": 30, "b": 20})
    return figure, {"aggregation": driver.aggregation, "resolution_m": driver.spatial_resolution_m,
                    "caution": "Daily product labels and gauge intervals have different temporal support; no causal claim."}


def outlook_figure(forecast):
    t = forecast.table
    figure = go.Figure()
    if len(t):
        figure.add_trace(go.Scatter(x=t.start, y=t.p90, line={"width": 0}, showlegend=False))
        figure.add_trace(go.Scatter(x=t.start, y=t.p10, line={"width": 0}, fill="tonexty",
            fillcolor="rgba(107,104,174,.15)", name="Historical variability"))
        figure.add_trace(go.Scatter(x=t.start, y=t.estimate_m3s, mode="lines+markers",
            name="Seasonal baseline outlook", line={"color": "#7267a3", "dash": "dash"}))
    figure.update_layout(template="plotly_white", height=350, yaxis_title="Monthly mean discharge (m³/s)",
                         xaxis_title="Target interval start", margin={"t": 20, "b": 20})
    return figure, {"model": forecast.model, "interval_type": forecast.interval_type}
