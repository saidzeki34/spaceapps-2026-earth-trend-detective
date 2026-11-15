"""Plotly figures for the trend results. Every function returns a ``plotly.graph_objects.Figure``.

The underlying numbers are always available as tables on ``TrendResults`` (table view for
accessibility and export). Colors follow one fixed palette:
    * categorical identity: blue, orange, aqua (in that order, never cycled)
    * ordered windows/decades: one blue ramp, light (oldest) -> dark (newest)
    * signed change and correlation: diverging red <- grey -> blue (red = less water / negative)
"""

from __future__ import annotations

import calendar

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import baseline
from .flow_metrics import doy_to_date_label
from .registry import axis_label, info
from .seasonal import hydro_month_order

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9",
                  axis="#c3c2b7", mid="#f0efec", missing="#c9c8c1",
                  series=["#2a78d6", "#eb6834", "#1baf7a"]),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a",
                 axis="#383835", mid="#383835", missing="#5e5d59",
                 series=["#3987e5", "#d95926", "#199e70"]),
}
BLUE_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]  # ordinal (>= step 250)
SEQUENTIAL = [[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]]
RED, BLUE = "#d03b3b", "#2a78d6"
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def _diverging(theme: str) -> list:
    return [[0, "#9b2226"], [0.25, "#e34948"], [0.5, THEMES[theme]["mid"]], [0.75, "#3987e5"], [1, "#104281"]]


def _layout(fig: go.Figure, title: str, theme: str = "light", subtitle: str | None = None, **kw) -> go.Figure:
    t = THEMES[theme]
    axis = dict(gridcolor=t["grid"], gridwidth=1, linecolor=t["axis"], zeroline=False,
                tickfont=dict(color=t["muted"]), title_font=dict(color=t["ink2"]))
    text = f"{title}<br><span style='font-size:12px;color:{t['ink2']}'>{subtitle}</span>" if subtitle else title
    fig.update_layout(
        title=dict(text=text, font=dict(color=t["ink"], size=16), x=0, xanchor="left"),
        font=dict(family=FONT, color=t["ink2"], size=12),
        paper_bgcolor=t["surface"], plot_bgcolor=t["surface"],
        legend=dict(font=dict(color=t["ink2"]), bgcolor="rgba(0,0,0,0)") | kw.pop("legend", {}),
        hoverlabel=dict(font=dict(family=FONT)),
        margin=kw.pop("margin", dict(l=60, r=30, t=80 if subtitle else 60, b=50)),
        **kw,
    )
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def _start_month(results) -> int:
    return int(results.meta.get("settings", {}).get("hydro_year_start_month", 10))


def _doy_dates(doy: pd.Series, start_month: int) -> pd.Series:
    """Map day-of-hydro-year to dates in a fixed non-leap reference year, for month-labelled axes."""
    start = pd.Timestamp(year=2001 - (1 if start_month != 1 else 0), month=start_month, day=1)
    return start + pd.to_timedelta(doy.astype(int) - 1, unit="D")


def _date_axis(fig: go.Figure) -> None:
    fig.update_xaxes(tickformat="%b", dtick="M1", hoverformat="%d %b")


def _label(results, gauge_id: str) -> str:
    suffix = " · GLDAS-2.1" if results.meta.get("source") == "gldas" else ""
    return results.gauge_label(gauge_id) + suffix


def _flow(results) -> str:
    """'Discharge' for gauge observations, 'GLDAS runoff' for modelled runoff."""
    return results.meta.get("flow_label", "Discharge")


def _flow_axis(results) -> str:
    unit = "m³/s equivalent" if results.meta.get("source") == "gldas" else "m³/s"
    return f"{_flow(results)} ({unit})"


def _trend_row(results, gauge_id: str, metric: str) -> pd.Series | None:
    t = results.trends
    row = t[(t["gauge_id"] == gauge_id) & (t["metric"] == metric)]
    return None if row.empty else row.iloc[0]


def _fmt_change(row: pd.Series, metric: str) -> str:
    unit = info(metric).unit
    change = f"{row['pct_per_decade']:+.1f} % per decade" if info(metric).relative else \
        f"{row['slope_per_decade']:+.1f} {'days' if 'day' in unit else unit} per decade"
    p = row["p"]
    sig = "significant" if row["significant_fdr"] else ("significant before FDR" if row["significant"] else "not significant")
    return f"Sen's slope {change} · Mann-Kendall p = {p:.3f} ({sig})"




def hydrograph_vs_history(results, gauge_id: str, year: int, reference: tuple[int, int] | None = None,
                          theme: str = "light") -> go.Figure:
    """One hydrological year against the historical day-of-year percentile bands."""
    t = THEMES[theme]
    sm = _start_month(results)
    d = baseline.year_vs_climatology(results.daily, gauge_id, year, reference)
    x = _doy_dates(d["hydro_doy"], sm)
    fig = go.Figure()
    band = "rgba(42,120,214,{})".format
    fig.add_trace(go.Scatter(x=x, y=d["q90"], line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=d["q10"], fill="tonexty", fillcolor=band(0.10), line=dict(width=0),
                             name="10–90 % of past years", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=d["q75"], line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=d["q25"], fill="tonexty", fillcolor=band(0.22), line=dict(width=0),
                             name="25–75 % of past years", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=d["q50"], name="Median", line=dict(color=t["muted"], width=2)))
    fig.add_trace(go.Scatter(
        x=x, y=d["discharge_vol"], name=f"Hydrological year {year}", line=dict(color=t["series"][1], width=2),
        customdata=d["percentile_rank"], hovertemplate="%{y:.2f} m³/s · percentile %{customdata:.0f}<extra></extra>",
    ))
    ref = f"{reference[0]}–{reference[1]}" if reference else "all valid years"
    _layout(fig, f"{_label(results, gauge_id)}: flow in {year} vs history", theme,
            subtitle=f"Daily {_flow(results).lower()}; bands are percentiles per calendar day over {ref}",
            hovermode="x unified", yaxis_title=_flow_axis(results))
    _date_axis(fig)
    return fig


def regime_by_window(results, gauge_id: str, normalized: bool = False, theme: str = "light") -> go.Figure:
    """Mean seasonal hydrograph per 10-year window: shifts show changes in *when* water is available."""
    reg = results.regime_daily[results.regime_daily["gauge_id"] == gauge_id].copy()
    if normalized:
        reg["mean"] = reg["mean"] / reg.groupby("window")["mean"].transform("mean")
    sm = _start_month(results)
    wins = sorted(reg["window"].unique())
    ramp = BLUE_RAMP[-len(wins):] if len(wins) <= len(BLUE_RAMP) else BLUE_RAMP
    fig = go.Figure()
    for color, w in zip(ramp, wins):
        r = reg[reg["window"] == w]
        fig.add_trace(go.Scatter(x=_doy_dates(r["hydro_doy"], sm), y=r["mean"], name=w,
                                 line=dict(color=color, width=2)))
    _layout(fig, f"{_label(results, gauge_id)}: seasonal flow regime by decade", theme,
            subtitle=f"Mean daily {_flow(results).lower()} per window (15-day smoothing)" + (", relative to the window's annual mean" if normalized else ""),
            hovermode="x unified",
            yaxis_title="Flow / annual mean" if normalized else _flow_axis(results), legend_title_text="Window")
    _date_axis(fig)
    return fig


def monthly_regime_table(results, gauge_id: str) -> pd.DataFrame:
    """Table twin of the regime plot: months (hydrological order) x windows."""
    reg = results.regime_monthly[results.regime_monthly["gauge_id"] == gauge_id]
    table = reg.pivot(index="month", columns="window", values="mean")
    return table.reindex(hydro_month_order(_start_month(results)))


def annual_metric(results, gauge_id: str, metric: str, theme: str = "light") -> go.Figure:
    """Annual values of one metric with the Sen's slope trend line and 10-year window means."""
    t = THEMES[theme]
    a = results.annual[results.annual["gauge_id"] == gauge_id].sort_values("hydro_year")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=a["hydro_year"], y=a[metric], mode="markers", name="Annual value",
        marker=dict(color=t["series"][0], size=8, line=dict(color=t["surface"], width=2)),
    ))
    for w, grp in a.dropna(subset=["window"]).groupby("window"):
        fig.add_trace(go.Scatter(
            x=[grp["hydro_year"].min() - 0.4, grp["hydro_year"].max() + 0.4], y=[grp[metric].mean()] * 2,
            mode="lines", line=dict(color=t["muted"], width=2), name="10-year mean",
            legendgroup="win", showlegend=w == a["window"].dropna().iloc[0], hovertemplate=f"{w}: %{{y:.2f}}<extra></extra>",
        ))
    row = _trend_row(results, gauge_id, metric)
    subtitle = None
    if row is not None and np.isfinite(row["slope_per_decade"]):
        yrs = np.array([row["first_year"], row["last_year"]], dtype=float)
        fig.add_trace(go.Scatter(x=yrs, y=row["intercept"] + row["slope_per_decade"] / 10 * yrs, mode="lines",
                                 name="Sen's slope trend", line=dict(color=t["series"][1], width=2)))
        subtitle = _fmt_change(row, metric)
    _layout(fig, f"{_label(results, gauge_id)}: {info(metric).label.lower()}", theme, subtitle=subtitle,
            xaxis_title="Hydrological year", yaxis_title=axis_label(metric), hovermode="closest")
    if info(metric).unit == "day of hydro year":
        sm = _start_month(results)
        vals = a[metric].dropna()
        if len(vals):
            ticks = np.arange(np.floor(vals.min() / 15) * 15, vals.max() + 15, 15)
            fig.update_yaxes(tickvals=ticks, ticktext=[doy_to_date_label(v, sm) for v in ticks], title="Date")
    return fig


def daily_heatmap(results, gauge_id: str, log_scale: bool = True, theme: str = "light") -> go.Figure:
    """Day of year x year grid of discharge: earlier melt shows as the dark band moving left over the years."""
    d = results.daily[(results.daily["gauge_id"] == gauge_id) & (results.daily["hydro_doy"] <= 365)]
    grid = d.pivot_table(index="hydro_year", columns="hydro_doy", values="discharge_vol")
    z = np.log10(grid.clip(lower=1e-3)) if log_scale else grid
    sm = _start_month(results)
    x = _doy_dates(pd.Series(grid.columns), sm)
    fig = go.Figure(go.Heatmap(
        z=z.to_numpy(), x=x, y=grid.index, colorscale=SEQUENTIAL, customdata=grid.to_numpy(),
        hovertemplate="%{x|%d %b} %{y}: %{customdata:.2f} m³/s<extra></extra>",
        colorbar=dict(title="log₁₀ m³/s" if log_scale else "m³/s", outlinewidth=0),
    ))
    _layout(fig, f"{_label(results, gauge_id)}: daily {_flow(results).lower()} by year", theme,
            subtitle="Each row is one hydrological year; darker = more water", yaxis_title="Hydrological year")
    _date_axis(fig)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    return fig


def window_means(results, gauge_id: str, metric: str, theme: str = "light") -> go.Figure:
    """Mean of a metric per 10-year window with the change against the first window."""
    t = THEMES[theme]
    w = results.window_comparison
    w = w[(w["gauge_id"] == gauge_id) & (w["metric"] == metric)].sort_values("window")
    rel = info(metric).relative
    change = w["pct_vs_reference"] if rel else w["change_vs_reference"]
    labels = [
        "reference" if i == 0 else (f"{c:+.1f} %" if rel else f"{c:+.1f}") + ("" if pd.isna(p) else f" (p={p:.2f})")
        for i, (c, p) in enumerate(zip(change, w["p_vs_reference"]))
    ]
    fig = go.Figure(go.Bar(
        x=w["window"], y=w["mean"], text=labels, textposition="outside", width=0.5,
        marker=dict(color=t["series"][0], cornerradius=4), textfont=dict(color=t["ink2"]),
        error_y=dict(type="data", array=w["std"], color=t["muted"], thickness=1),
    ))
    _layout(fig, f"{_label(results, gauge_id)}: {info(metric).label.lower()} per decade", theme,
            subtitle="Bar = window mean, whisker = year-to-year standard deviation; label = change vs first window "
                     "(Mann-Whitney p)", yaxis_title=axis_label(metric), xaxis_title="Window", showlegend=False)
    return fig


def correlation_matrix(results, gauge_id: str | None = None, theme: str = "light") -> go.Figure:
    """Flow metrics x drivers. Per catchment (Spearman r of detrended annual values) or median over all."""
    if gauge_id is None:
        c = results.correlation_summary.rename(columns={"median_r": "r"})
        title, sub = "Drivers and flow: median correlation across catchments", \
            "Spearman r of detrended annual values; association only, not proof of cause"
    else:
        c = results.correlations[results.correlations["gauge_id"] == gauge_id]
        title, sub = f"{_label(results, gauge_id)}: drivers and flow", \
            "Spearman r of detrended annual values (● p < 0.05); association only, not proof of cause"
    m = c.pivot(index="metric", columns="driver", values="r")
    order_rows = [x for x in results.annual.columns if x in m.index]
    order_cols = [x for x in results.annual.columns if x in m.columns]
    m = m.reindex(index=order_rows, columns=order_cols)
    text = None
    if gauge_id is not None:
        p = c.pivot(index="metric", columns="driver", values="p").reindex(index=order_rows, columns=order_cols)
        text = np.where(p.to_numpy() < 0.05, "●", "")
    fig = go.Figure(go.Heatmap(
        z=m.to_numpy(), x=[info(x).label for x in m.columns], y=[info(x).label for x in m.index],
        zmin=-1, zmax=1, colorscale=_diverging(theme), text=text, texttemplate="%{text}" if text is not None else None,
        textfont=dict(color=THEMES[theme]["ink"], size=10), xgap=2, ygap=2,
        hovertemplate="%{y} vs %{x}: r = %{z:.2f}<extra></extra>", colorbar=dict(title="r", outlinewidth=0),
    ))
    _layout(fig, title, theme, subtitle=sub, height=max(400, 28 * len(m) + 160))
    fig.update_xaxes(showgrid=False, tickangle=-35)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return fig


def driver_scatter(results, gauge_id: str, metric: str, driver: str, theme: str = "light") -> go.Figure:
    """Annual flow metric against one driver, coloured by 10-year window."""
    t = THEMES[theme]
    a = results.annual[results.annual["gauge_id"] == gauge_id].dropna(subset=[metric, driver])
    wins = sorted(a["window"].dropna().unique())
    ramp = BLUE_RAMP[-len(wins):]
    fig = go.Figure()
    for color, w in zip(ramp, wins):
        g = a[a["window"] == w]
        fig.add_trace(go.Scatter(x=g[driver], y=g[metric], mode="markers", name=w, customdata=g["hydro_year"],
                                 marker=dict(color=color, size=9, line=dict(color=t["surface"], width=2)),
                                 hovertemplate="%{customdata}: %{x:.2f}, %{y:.2f}<extra></extra>"))
    _layout(fig, f"{_label(results, gauge_id)}: {info(metric).label.lower()} vs {info(driver).label.lower()}", theme,
            xaxis_title=axis_label(driver), yaxis_title=axis_label(metric), legend_title_text="Window")
    return fig




def trend_heatmap(results, kind: str = "volume", significance: str = "fdr", theme: str = "light") -> go.Figure:
    """Catchments x metrics of one kind ('volume', 'timing', 'variability', 'driver').

    Colour = change per decade (% for amounts, days for timing); ● marks significant trends.
    """
    t = results.trends[results.trends["kind"] == kind]
    rel = t["metric"].map(lambda m: info(m).relative)
    t = t.assign(value=np.where(rel, t["pct_per_decade"], t["slope_per_decade"]))
    m = t.pivot(index="gauge_id", columns="metric", values="value")
    sig_col = "significant_fdr" if significance == "fdr" else "significant"
    s = t.pivot(index="gauge_id", columns="metric", values=sig_col).reindex_like(m)
    cols = [c for c in results.annual.columns if c in m.columns]
    m, s = m[cols], s[cols]
    lim = float(np.nanpercentile(np.abs(m.to_numpy()), 95)) if m.size else 1.0
    unit = "% per decade" if rel.all() else ("days per decade" if kind == "timing" else "units per decade")
    fig = go.Figure(go.Heatmap(
        z=m.to_numpy(), x=[info(c).label for c in cols], y=[results.gauge_label(g) for g in m.index],
        zmin=-lim, zmax=lim, colorscale=_diverging(theme), xgap=2, ygap=2,
        text=np.where(s.to_numpy() == True, "●", ""), texttemplate="%{text}",  # noqa: E712
        textfont=dict(color=THEMES[theme]["ink"], size=10),
        hovertemplate="%{y}<br>%{x}: %{z:+.1f}<extra></extra>", colorbar=dict(title=unit, outlinewidth=0),
    ))
    label = "FDR-adjusted" if significance == "fdr" else "unadjusted"
    _layout(fig, f"Trends in {kind} metrics, all selected catchments", theme,
            subtitle=f"Sen's slope; ● = Mann-Kendall p < {results.meta['settings']['alpha']} ({label})",
            height=max(420, 22 * len(m) + 180))
    fig.update_xaxes(showgrid=False, tickangle=-35)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return fig


def window_change_heatmap(results, metric: str, theme: str = "light") -> go.Figure:
    """Catchments x 10-year windows: change of a metric against the first window."""
    rel = info(metric).relative
    w = results.window_comparison[results.window_comparison["metric"] == metric]
    col = "pct_vs_reference" if rel else "change_vs_reference"
    m = w.pivot(index="gauge_id", columns="window", values=col)
    lim = float(np.nanpercentile(np.abs(m.to_numpy()), 95)) if m.size else 1.0
    fig = go.Figure(go.Heatmap(
        z=m.to_numpy(), x=list(m.columns), y=[results.gauge_label(g) for g in m.index], zmin=-lim, zmax=lim,
        colorscale=_diverging(theme), xgap=2, ygap=2, hovertemplate="%{y}<br>%{x}: %{z:+.1f}<extra></extra>",
        colorbar=dict(title="%" if rel else info(metric).unit.replace("day of hydro year", "days"), outlinewidth=0),
    ))
    _layout(fig, f"{info(metric).label}: change vs first decade", theme,
            subtitle="Window mean minus reference-window mean" + (" (in %)" if rel else ""),
            height=max(420, 22 * len(m) + 180))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return fig


def trend_map(results, metric: str, theme: str = "light") -> go.Figure:
    """Gauges on a map coloured by trend; filled = significant (FDR), hollow = not significant."""
    t = THEMES[theme]
    tr = results.trends[results.trends["metric"] == metric]
    a = results.attributes[["gauge_id", "lat", "lon"]] if {"lat", "lon"} <= set(results.attributes) else None
    if a is None:
        raise ValueError("No gauge coordinates in the static attributes")
    d = tr.merge(a, on="gauge_id")
    rel = info(metric).relative
    d["value"] = d["pct_per_decade"] if rel else d["slope_per_decade"]
    d["label"] = d["gauge_id"].map(results.gauge_label)
    lim = float(np.nanpercentile(np.abs(d["value"]), 95)) if len(d) else 1.0
    fig = go.Figure()
    for sig, symbol, name in [(True, "circle", "significant"), (False, "circle-open", "not significant")]:
        g = d[d["significant_fdr"] == sig]
        fig.add_trace(go.Scattergeo(
            lon=g["lon"], lat=g["lat"], name=name, text=g["label"], customdata=g[["value", "p"]],
            mode="markers", marker=dict(
                symbol=symbol, size=12, color=g["value"], cmin=-lim, cmax=lim, colorscale=_diverging(theme),
                line=dict(width=2, color=t["surface"]) if sig else dict(width=2),
                colorbar=dict(title="% / decade" if rel else "per decade", outlinewidth=0) if sig else None,
                showscale=sig,
            ),
            hovertemplate="%{text}<br>%{customdata[0]:+.1f} per decade, p = %{customdata[1]:.3f}<extra></extra>",
        ))
    fig.update_geos(fitbounds="locations", showcountries=True, countrycolor=t["axis"], showland=True,
                    landcolor=t["surface"], showlakes=True, lakecolor="#cde2fb" if theme == "light" else "#184f95",
                    bgcolor=t["surface"], resolution=50, showframe=False)
    _layout(fig, f"{info(metric).label}: trend per catchment", theme,
            subtitle="Sen's slope per decade; filled = significant after FDR correction", height=520,
            legend=dict(orientation="h", y=-0.05))
    return fig


def trend_vs_attribute(results, metric: str, attribute: str, theme: str = "light") -> go.Figure:
    """Across catchments: trend of a metric against a static property (elevation, area, ...)."""
    t = THEMES[theme]
    rel = info(metric).relative
    d = results.trends[results.trends["metric"] == metric].merge(results.attributes[["gauge_id", attribute]],
                                                                  on="gauge_id")
    d["value"] = d["pct_per_decade"] if rel else d["slope_per_decade"]
    d["label"] = d["gauge_id"].map(results.gauge_label)
    fig = go.Figure()
    for sig, name in [(True, "significant"), (False, "not significant")]:
        g = d[d["significant_fdr"] == sig]
        fig.add_trace(go.Scatter(
            x=g[attribute], y=g["value"], mode="markers", name=name, text=g["label"],
            marker=dict(size=10, color=t["series"][0] if sig else t["surface"],
                        line=dict(width=2, color=t["surface"] if sig else t["series"][0])),
            hovertemplate="%{text}<br>%{x}: %{y:+.1f}<extra></extra>",
        ))
    fig.add_hline(y=0, line=dict(color=t["axis"], width=1))
    stat = results.trend_vs_attributes
    stat = stat[(stat["metric"] == metric) & (stat["attribute"] == attribute)]
    sub = None if stat.empty or pd.isna(stat["r"].iloc[0]) else \
        f"Spearman r = {stat['r'].iloc[0]:.2f}, p = {stat['p'].iloc[0]:.3f}, n = {int(stat['n'].iloc[0])} catchments"
    _layout(fig, f"Does the {info(metric).label.lower()} trend depend on {attribute}?", theme, subtitle=sub,
            xaxis_title=attribute, yaxis_title=("% per decade" if rel else f"{info(metric).unit} per decade"))
    return fig


def attribution_bars(results, theme: str = "light") -> go.Figure:
    """Observed runoff change per decade split into precipitation, temperature and unexplained parts."""
    t = THEMES[theme]
    a = results.attribution.copy()
    a["label"] = a["gauge_id"].map(results.gauge_label)
    a = a.sort_values("observed_change_per_decade")
    fig = go.Figure()
    for col, name, color in [("from_precip_per_decade", "Precipitation", t["series"][0]),
                             ("from_temp_per_decade", "Temperature", t["series"][1]),
                             ("residual_per_decade", "Other / unexplained", t["series"][2])]:
        fig.add_trace(go.Bar(y=a["label"], x=a[col], name=name, orientation="h",
                             marker=dict(color=color, line=dict(color=t["surface"], width=2)),
                             hovertemplate="%{y}<br>" + name + ": %{x:+.1f} mm<extra></extra>"))
    fig.add_trace(go.Scatter(y=a["label"], x=a["observed_change_per_decade"], mode="markers", name="Observed change",
                             marker=dict(symbol="diamond", size=10, color=t["ink"], line=dict(color=t["surface"], width=2)),
                             hovertemplate="%{y}<br>Observed: %{x:+.1f} mm<extra></extra>"))
    _layout(fig, "What explains the change in annual runoff?", theme,
            subtitle="Statistical attribution per catchment (mm per decade): elasticity to precipitation and "
                     "sensitivity to temperature × their trends. Association, not proof of cause.",
            barmode="relative", bargap=0.35, xaxis_title="Runoff change (mm per decade)",
            height=max(420, 24 * len(a) + 180), legend=dict(orientation="h", y=-0.12))
    fig.add_vline(x=0, line=dict(color=t["axis"], width=1))
    fig.update_yaxes(showgrid=False)
    return fig


def selection_summary(results, theme: str = "light") -> go.Figure:
    """How many catchments remain after each filter step."""
    t = THEMES[theme]
    s = results.selection_log
    fig = go.Figure(go.Bar(y=s["step"], x=s["remaining"], orientation="h", text=s["remaining"],
                           textposition="outside", textfont=dict(color=t["ink2"]),
                           marker=dict(color=t["series"][0], cornerradius=4), width=0.5))
    _layout(fig, "Catchment selection", theme, subtitle="Catchments remaining after each filter step",
            xaxis_title="Catchments", showlegend=False, height=120 + 50 * len(s))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig




def source_regime(obs, model, gauge_id: str, theme: str = "light") -> go.Figure:
    """Observed discharge vs GLDAS runoff: mean seasonal hydrograph over the common years."""
    from .sources import regime_pair

    t = THEMES[theme]
    reg = regime_pair(obs, model, gauge_id)
    x = _doy_dates(reg["hydro_doy"], _start_month(obs))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=reg["observed"], name="Observed discharge (CAMELS-CH)",
                             line=dict(color=t["series"][0], width=2)))
    fig.add_trace(go.Scatter(x=x, y=reg["gldas"], name="GLDAS-2.1 runoff (unrouted)",
                             line=dict(color=t["series"][1], width=2)))
    years = reg.attrs.get("years")
    _layout(fig, f"{obs.gauge_label(gauge_id)}: observed vs GLDAS", theme,
            subtitle=f"Mean daily flow {years[0]}–{years[1]} (15-day smoothing); GLDAS converted to m³/s with the "
                     "catchment area" if years else None,
            hovermode="x unified", yaxis_title="m³/s", legend=dict(orientation="h", y=-0.15))
    _date_axis(fig)
    return fig


def source_scatter(annual_cmp: pd.DataFrame, obs, metric: str, value: str = "mean",
                   theme: str = "light") -> go.Figure:
    """One point per catchment: observed vs GLDAS (mean over common years) with the 1:1 line."""
    t = THEMES[theme]
    d = annual_cmp[annual_cmp["metric"] == metric].copy()
    d["label"] = d["gauge_id"].map(obs.gauge_label)
    x, y = d[f"{value}_obs"], d[f"{value}_model"]
    lo = float(np.nanmin([x.min(), y.min()])) if len(d) else 0.0
    hi = float(np.nanmax([x.max(), y.max()])) if len(d) else 1.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="1:1",
                             line=dict(color=t["axis"], width=1), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers", name="Catchment", text=d["label"], customdata=d[["r", "n_years"]],
        marker=dict(color=t["series"][0], size=10, line=dict(color=t["surface"], width=2)),
        hovertemplate="%{text}<br>observed %{x:.1f}, GLDAS %{y:.1f}<br>r = %{customdata[0]:.2f} "
                      "(%{customdata[1]} years)<extra></extra>",
    ))
    med_r = d["r"].median()
    _layout(fig, f"{info(metric).label}: observed vs GLDAS", theme,
            subtitle=f"Catchment means over common years; median year-to-year r = {med_r:.2f}" if len(d) else None,
            xaxis_title=f"Observed — {axis_label(metric)}", yaxis_title=f"GLDAS — {axis_label(metric)}",
            showlegend=False)
    return fig


def source_trend_scatter(trend_cmp: pd.DataFrame, obs, metric: str, theme: str = "light") -> go.Figure:
    """Trend per decade from observations vs from GLDAS over the same years, one point per catchment."""
    t = THEMES[theme]
    rel = info(metric).relative
    col = "pct_per_decade" if rel else "slope_per_decade"
    d = trend_cmp[trend_cmp["metric"] == metric].copy()
    d["label"] = d["gauge_id"].map(obs.gauge_label)
    x, y = d[f"{col}_obs"], d[f"{col}_model"]
    lim = float(np.nanmax(np.abs(pd.concat([x, y])))) if len(d) else 1.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[-lim, lim], y=[-lim, lim], mode="lines", line=dict(color=t["axis"], width=1),
                             hoverinfo="skip", showlegend=False))
    fig.add_hline(y=0, line=dict(color=t["grid"], width=1))
    fig.add_vline(x=0, line=dict(color=t["grid"], width=1))
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers", text=d["label"], showlegend=False,
        marker=dict(color=t["series"][0], size=10, line=dict(color=t["surface"], width=2)),
        hovertemplate="%{text}<br>observed %{x:+.1f}, GLDAS %{y:+.1f}<extra></extra>",
    ))
    unit = "% per decade" if rel else f"{info(metric).unit.replace('day of hydro year', 'days')} per decade"
    share = d["same_direction"].mean() * 100 if len(d) else np.nan
    _layout(fig, f"{info(metric).label}: trend from observations vs GLDAS", theme,
            subtitle=f"Sen's slope over common years; same direction in {share:.0f} % of catchments",
            xaxis_title=f"Observed ({unit})", yaxis_title=f"GLDAS ({unit})")
    return fig



ROW_PX = 18          # height of one gauge row
PANEL_GAP_PX = 120   # room above the second country panel for its title and column labels
GLACIER_SCALE = [[0, BLUE_RAMP[0]], [0.5, BLUE_RAMP[2]], [1, BLUE_RAMP[5]]]


def _limit(values: np.ndarray, step: float) -> float:
    """Symmetric colour limit: 95th percentile of |values|, rounded up to ``step``."""
    finite = np.abs(values[np.isfinite(values)])
    return float(np.ceil(np.percentile(finite, 95) / step) * step) if finite.size else step


def _colorbar(title: str, x: float, length: float) -> dict:
    return dict(title=dict(text=title, side="top"), orientation="h", x=x, xanchor="left", y=0, yanchor="top",
                ypad=40, len=length, thickness=12, outlinewidth=0)


def _missing(mask: np.ndarray, x: list, y: list, text: str, theme: str) -> go.Heatmap:
    """Grey cells where there is no value, so missing data never looks like 'no change'."""
    grey = THEMES[theme]["missing"]
    return go.Heatmap(z=np.where(mask, 1.0, np.nan), x=x, y=y, colorscale=[[0, grey], [1, grey]], showscale=False,
                      xgap=1, ygap=1, hovertemplate="%{y}<br>%{x}: " + text + "<extra></extra>")


def _country_panels(network, column_widths: list[float], spacing: float = 0.012):
    """One subplot row per country (rows sized to the number of gauges) and one column per column group."""
    from plotly.subplots import make_subplots

    groups = [(c, network.stations[network.stations["country"] == c]) for c in network.countries]
    sizes = [len(g) for _, g in groups]
    plot_px = ROW_PX * sum(sizes) + PANEL_GAP_PX * (len(groups) - 1)
    fig = make_subplots(len(groups), len(column_widths), shared_yaxes=True, column_widths=column_widths,
                        row_heights=sizes, horizontal_spacing=spacing,
                        vertical_spacing=PANEL_GAP_PX / plot_px if len(groups) > 1 else 0)
    return fig, groups, plot_px


def _panel_titles(fig: go.Figure, network, groups, theme: str, suffix) -> None:
    t = THEMES[theme]
    for row, (country, g) in enumerate(groups, start=1):
        top = fig.get_subplot(row, 1).yaxis.domain[1]
        fig.add_annotation(x=0, y=top, xref="paper", yref="paper", xanchor="left", yanchor="bottom", yshift=48,
                           showarrow=False, align="left", text=f"<b>{country}</b>  ·  {suffix(g)}",
                           font=dict(size=14, color=t["ink"]))


def station_month_heatmap(network, significance: bool = True, theme: str = "light") -> go.Figure:
    """Gauges by country (highest catchment first) x calendar months, late-summer/annual summaries and the
    half-volume date.

    Volume columns share one colour scale (% of the baseline mean per decade; mm per decade in the hover);
    the half-volume date has its own (days per decade). Red = less water / earlier. Grey = too few complete
    years for a slope. ● = Mann-Kendall p < alpha after FDR per column.
    """
    from .stations import LABELS, MONTHS, SUMMARIES, TIMING, change_matrix

    t = THEMES[theme]
    s = network.meta["settings"]
    b0, b1 = s["baseline"]
    change, p = change_matrix(network), change_matrix(network, "p")
    runoff = change_matrix(network, "runoff_change_per_decade")
    sig = change_matrix(network, "significant_fdr").fillna(False).astype(bool)
    info = network.stations.set_index("gauge_id")
    short = {"aug_sep_hm3": "Aug–Sep<br>volume", "annual_hm3": "Annual<br>volume",
             "aug_sep_min7": "Aug–Sep<br>7-day low", TIMING: "Half-volume<br>date"}

    def detail(gid: str, metric: str) -> str:
        r, q = runoff.at[gid, metric], p.at[gid, metric]
        mm = f" ({r:+.2f} {'mm/d' if metric == 'aug_sep_min7' else 'mm'})" if np.isfinite(r) else ""
        return mm + (f" · Mann-Kendall p = {q:.3f}" if np.isfinite(q) else "")

    def record(gid: str) -> str:
        return (f"{info.at[gid, 'complete_years']} complete years, {info.at[gid, 'baseline_years']} in {b0}–{b1}; "
                f"glacier {info.at[gid, 'glacier_pct']:.1f} %")
    column_groups = [(MONTHS, "coloraxis"), (SUMMARIES, "coloraxis"), ([TIMING], "coloraxis2")]
    fig, groups, plot_px = _country_panels(network, [12, 3.6, 1.2])
    for row, (_, g) in enumerate(groups, start=1):
        ids, y = g["gauge_id"].tolist(), g["label"].tolist()
        short_record = ~g["sufficient"].to_numpy()
        for col, (metrics, axis) in enumerate(column_groups, start=1):
            x = [short.get(m, LABELS[m]) for m in metrics]
            unit = "days" if axis == "coloraxis2" else "% of baseline mean"
            hover = np.array([[[detail(gid, m), record(gid)] for m in metrics] for gid in ids])
            fig.add_trace(_missing(np.repeat(short_record[:, None], len(metrics), axis=1), x, y,
                                   "too few complete years for a slope", theme), row=row, col=col)
            fig.add_trace(go.Heatmap(
                z=change.loc[ids, metrics].to_numpy(dtype=float), x=x, y=y, coloraxis=axis, xgap=1, ygap=1,
                customdata=hover,
                text=np.where(sig.loc[ids, metrics].to_numpy(), "●", "") if significance else None,
                texttemplate="%{text}" if significance else None, textfont=dict(color=t["ink"], size=8),
                hovertemplate="%{y}<br>%{x}: %{z:+.1f} " + unit + " per decade%{customdata[0]}"
                              "<br>%{customdata[1]}<extra></extra>",
            ), row=row, col=col)
    vol = change[MONTHS + SUMMARIES].to_numpy(dtype=float)
    lim_vol, lim_days = _limit(vol, 5), _limit(change[TIMING].to_numpy(dtype=float), 1)
    sub = (f"Observed daily discharge, {s['first_year']}–{s['last_year']} · Sen's slope of annual values per decade · "
           f"slopes need ≥ {s['min_complete_years']} complete years, ≥ {s['min_baseline_years']} in {b0}–{b1} "
           "(grey: fewer)"
           f"<br>▲ glacier cover > 0 · ■ reservoir, hydropower or regulation recorded"
           + (f" · ● Mann-Kendall p < {s['alpha']} after FDR per column" if significance else ""))
    _layout(fig, "When is river flow changing?", theme, subtitle=sub,
            height=plot_px + 380, margin=dict(l=20, r=20, t=240, b=140),
            coloraxis=dict(colorscale=_diverging(theme), cmin=-lim_vol, cmax=lim_vol,
                           colorbar=_colorbar(f"Flow volume change (% of {b0}–{b1} mean per decade)", 0, 0.55)),
            coloraxis2=dict(colorscale=_diverging(theme), cmin=-lim_days, cmax=lim_days,
                            colorbar=_colorbar("Half-volume date (days per decade, negative = earlier)", 0.62, 0.38)))
    _panel_titles(fig, network, groups, theme, lambda g: f"{int(g['sufficient'].sum())} of {len(g)} gauges with "
                                                        "slopes · highest catchments at top")
    fig.update_xaxes(showgrid=False, side="top", tickfont=dict(color=t["ink2"]))
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(size=10), automargin=True)
    fig.update_yaxes(showticklabels=False, col=2)
    fig.update_yaxes(showticklabels=False, col=3)
    return fig


def station_year_heatmaps(network, theme: str = "light") -> go.Figure:
    """Same gauge order, one column per year: Aug–Sep volume anomaly (left) and half-volume date anomaly (right).

    Shows whether slopes come from gradual shifts, a few dry years shared across the network, or an abrupt
    change at one gauge. Anomalies are relative to each gauge's baseline mean; grey = no complete record that year.
    """
    from .stations import year_anomalies

    t = THEMES[theme]
    s = network.meta["settings"]
    b0, b1 = s["baseline"]
    a = year_anomalies(network)
    years = list(range(s["first_year"], s["last_year"] + 1))
    fig, groups, plot_px = _country_panels(network, [1, 1], spacing=0.02)
    for row, (_, g) in enumerate(groups, start=1):
        ids, y = g["gauge_id"].tolist(), g["label"].tolist()
        for col, (column, axis, unit) in enumerate(
                [("aug_sep_pct", "coloraxis", "%"), ("half_volume_days", "coloraxis2", "days")], start=1):
            m = a.pivot(index="gauge_id", columns="year", values=column).reindex(index=ids, columns=years)
            z = m.to_numpy(dtype=float)
            fig.add_trace(_missing(np.isnan(z), years, y, "no complete record", theme), row=row, col=col)
            fig.add_trace(go.Heatmap(
                z=z, x=years, y=y, coloraxis=axis, xgap=1, ygap=1,
                hovertemplate="%{y}<br>%{x}: %{z:+.1f} " + unit + f" vs {b0}–{b1} mean<extra></extra>",
            ), row=row, col=col)
    vol = a["aug_sep_pct"].to_numpy(dtype=float)
    days = a["half_volume_days"].to_numpy(dtype=float)
    _layout(fig, "Gradual shift, shared dry years or one gauge?", theme,
            subtitle=f"Each cell is one year at one gauge, relative to that gauge's {b0}–{b1} mean · left: Aug–Sep "
                     "volume, right: half-volume date · same order as the station × month heatmap · grey: no complete "
                     "record",
            height=plot_px + 380, margin=dict(l=20, r=20, t=240, b=140),
            coloraxis=dict(colorscale=_diverging(theme), cmin=-_limit(vol, 10), cmax=_limit(vol, 10),
                           colorbar=_colorbar(f"Aug–Sep volume (% vs {b0}–{b1} mean)", 0, 0.45)),
            coloraxis2=dict(colorscale=_diverging(theme), cmin=-_limit(days, 5), cmax=_limit(days, 5),
                            colorbar=_colorbar(f"Half-volume date (days vs {b0}–{b1} mean, negative = earlier)",
                                               0.53, 0.45)))
    _panel_titles(fig, network, groups, theme, lambda g: f"{len(g)} gauges · highest catchments at top")
    fig.update_xaxes(showgrid=False, side="top", dtick=5, tickfont=dict(color=t["ink2"]))
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(size=10), automargin=True)
    fig.update_yaxes(showticklabels=False, col=2)
    return fig


def driver_change_scatter(network, flow: str, driver: str, theme: str = "light") -> go.Figure:
    """One point per gauge: change in a flow metric against the change in a possible driver, both fitted over
    the same years. One panel per country, colour = glacier cover. Association only, not proof of cause."""
    from plotly.subplots import make_subplots
    from scipy.stats import spearmanr

    from .stations import DATES, LABELS, driver_changes

    t = THEMES[theme]
    d = driver_changes(network)
    d = d[(d["flow"] == flow) & (d["driver"] == driver)]
    countries = [c for c in network.countries if (d["country"] == c).any()]
    titles = []
    for c in countries:
        g = d[d["country"] == c]
        r = spearmanr(g["driver_change"], g["flow_change"], nan_policy="omit")[0] if len(g) > 2 else np.nan
        titles.append(f"<b>{c}</b> · {len(g)} gauges, {int(g['first_year'].median())}–{int(g['last_year'].median())} "
                      f"(median) · Spearman r = {r:.2f}")
    fig = make_subplots(1, max(len(countries), 1), subplot_titles=titles, horizontal_spacing=0.08)
    cmax = _limit(d["glacier_pct"].to_numpy(dtype=float), 5) if len(d) else 5.0
    for col, c in enumerate(countries, start=1):
        g = d[d["country"] == c]
        fig.add_trace(go.Scatter(
            x=g["driver_change"], y=g["flow_change"], mode="markers", text=g["label"], showlegend=False,
            customdata=np.column_stack([g["n_years"], g["first_year"], g["last_year"], g["glacier_pct"]]),
            marker=dict(size=10, color=g["glacier_pct"], coloraxis="coloraxis", line=dict(color=t["surface"], width=2)),
            hovertemplate="%{text}<br>" + LABELS[driver] + ": %{x:+.1f}, " + LABELS[flow] + ": %{y:+.1f} per decade"
                          "<br>%{customdata[0]} years (%{customdata[1]}–%{customdata[2]}), "
                          "glacier %{customdata[3]:.1f} %"
                          "<extra></extra>",
        ), row=1, col=col)
        fig.add_hline(y=0, line=dict(color=t["axis"], width=1), row=1, col=col)
        fig.add_vline(x=0, line=dict(color=t["axis"], width=1), row=1, col=col)

    def unit(m: str) -> str:
        return "days per decade" if m in DATES else "% of mean per decade"

    driver_label = LABELS[driver] if LABELS[driver][:3] in calendar.month_abbr else LABELS[driver].lower()
    _layout(fig, f"{LABELS[flow]} vs {driver_label}: change per gauge", theme,
            subtitle="Sen's slopes over the years where both values exist; colour = glacier cover. "
                     "Association across gauges, not proof of cause.",
            height=520, margin=dict(l=70, r=30, t=110, b=60),
            coloraxis=dict(colorscale=GLACIER_SCALE, cmin=0, cmax=cmax,
                           colorbar=dict(title="Glacier cover (%)", outlinewidth=0, thickness=12)))
    fig.update_annotations(font=dict(color=t["ink2"], size=12))
    fig.update_xaxes(title_text=f"{LABELS[driver]} ({unit(driver)})")
    fig.update_yaxes(title_text=f"{LABELS[flow]} ({unit(flow)})", col=1)
    return fig
