"""Read-only presentation adapter for the team's saved trend results.

No download, build, gap filling, simulated observations or predictions occur here.
Scientific calculations and figures remain owned by ``mountain_water.trend``.
"""
from __future__ import annotations

import calendar
import json
import threading
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from pyproj import Transformer

from mountain_water.trend import pipeline, plots, registry, sources, stations

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"

DATASETS = {
    "ch": ("Switzerland / CAMELS-CH", "CH", "observed", "trend", "build"),
    "no": ("Norway / NVE + seNorge", "NO", "observed", "trend_no", "build --source nve"),
    "ch_gldas": ("Switzerland / GLDAS-2.1", "CH", "model", "trend_gldas", "build --source gldas"),
    "no_gldas": ("Norway / GLDAS-2.1", "NO", "model", "trend_no_gldas", "build --source gldas --region no"),
    "stations": ("Station network", "", "network", "trend_stations", "stations"),
}
VARIABLE_LABELS = {
    "discharge_vol": "Discharge", "discharge_spec": "Specific discharge", "waterlevel": "Water level",
    "precipitation": "Precipitation", "temperature_mean": "Air temperature", "temperature_min": "Minimum temperature",
    "temperature_max": "Maximum temperature", "swe": "Snow water equivalent", "rel_sun_dur": "Sunshine duration",
    "evap": "Evapotranspiration", "snowmelt": "Snowmelt", "snowfall": "Snowfall",
    "runoff_surface": "Surface runoff", "runoff_base": "Base runoff",
}
MODEL_NOTE = "GLDAS-2.1 is unrouted land-surface model runoff; it is not a river measurement or forecast."
TREND_NOTE = "Saved backend results: review coverage, gap filling, serial dependence and FDR before interpreting trends. Association does not establish causation."
STATION_NOTE = "Station network uses complete calendar years and its own selection and baseline; it differs from the hydrological-year catchment selection."

# id, label, scope, matching table, option names
VIEW_SPECS = (
    ("timeseries", "Time series", "catchment", "daily", ("year", "variable", "interval")),
    ("hydrograph_vs_history", "Year against history", "catchment", "daily", ("year",)),
    ("regime_by_window", "Seasonal regime", "catchment", "regime_monthly", ("normalized",)),
    ("annual_metric", "Annual metric and trend", "catchment", "trends", ("metric",)),
    ("daily_heatmap", "Daily flow heatmap", "catchment", "daily", ("log_scale",)),
    ("window_means", "Window means", "catchment", "window_comparison", ("metric",)),
    ("correlation_matrix", "Driver correlations", "catchment", "correlations", ()),
    ("driver_scatter", "Flow against driver", "catchment", "correlations", ("metric", "driver")),
    ("flow_surface", "Flow surface", "catchment", "daily", ("year",)),
    ("trend_heatmap", "Catchment trend heatmap", "region", "trends", ("kind",)),
    ("window_change_heatmap", "Window change heatmap", "region", "window_comparison", ("metric",)),
    ("trend_map", "Catchment trend map", "region", "trends", ("metric",)),
    ("trend_vs_attribute", "Trend against catchment attribute", "region", "trend_vs_attributes", ("metric", "attribute")),
    ("attribution_bars", "Statistical runoff attribution", "region", "attribution", ()),
    ("selection_summary", "Catchment selection", "region", "selection_log", ()),
    ("source_regime", "Observed / GLDAS regime", "sources", "source_regime", ()),
    ("source_scatter", "Observed / GLDAS means", "sources", "source_annual", ("metric",)),
    ("source_trend_scatter", "Observed / GLDAS trends", "sources", "source_trends", ("metric",)),
    ("station_month_heatmap", "Station / month changes", "stations", "station_trends", ()),
    ("station_year_heatmaps", "Station / year anomalies", "stations", "station_year_anomalies", ()),
    ("driver_change_scatter", "Station driver changes", "stations", "station_drivers", ("pair",)),
)


def _clean(value):
    """JSON numbers remain finite; missing observations remain null."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _text(value):
    return "" if value is None or pd.isna(value) else str(value).replace("_", " ").strip()


def _option(name, label, values):
    return {"name": name, "label": label, "values": [{"id": str(k), "label": str(v)} for k, v in values]}


class Backend:
    def __init__(self, data_root: Path | None = None):
        self.data_root = Path(data_root) if data_root is not None else DATA_ROOT
        self._cache = {}
        self._comparisons = {}
        self._lock = threading.RLock()

    def refresh(self):
        with self._lock:
            self._cache.clear()
            self._comparisons.clear()
        return self.catalogue()

    def _load(self, dataset):
        if dataset not in DATASETS:
            raise ValueError("Unknown dataset")
        label, country, kind, folder, command = DATASETS[dataset]
        directory = self.data_root / "processed" / folder
        names = stations.TABLES if dataset == "stations" else pipeline.TABLES
        files = [directory / "meta.json", *(directory / f"{name}.parquet" for name in names)]
        base = dict(id=dataset, label=label, country=country, region=country.lower(), kind=kind,
                    build_command=f"python -m mountain_water.trend {command}",
                    command=f"python -m mountain_water.trend {command}", gauges=[], views=[])
        if not all(path.is_file() for path in files):
            return None, dict(base, status="missing", message="Saved backend results are not built on this computer.")
        signature = tuple((path.stat().st_mtime_ns, path.stat().st_size) for path in files)
        with self._lock:
            cached = self._cache.get(dataset)
            if cached and cached[0] == signature:
                return cached[1], dict(base, status="ready")
            try:
                result = stations.load(directory) if dataset == "stations" else pipeline.load(directory)
                if not result.gauges:
                    return None, dict(base, status="missing", message="This saved build contains no selected gauges.")
            except Exception as error:
                return None, dict(base, status="error", message=f"Saved results could not be read ({type(error).__name__}). Rebuild or restore this dataset.")
            self._cache[dataset] = (signature, result)
            self._comparisons.clear()
            return result, dict(base, status="ready")

    def _gauges(self, result, dataset):
        network = dataset == "stations"
        attrs = result.stations if network else result.attributes[result.attributes["gauge_id"].isin(result.gauges)]
        rows = []
        swiss_positions = {}
        swiss_attrs = attrs
        if network:
            swiss, _ = self._load("ch")
            swiss_attrs = swiss.attributes if swiss is not None else pd.DataFrame()
        if {"gauge_easting", "gauge_northing"} <= set(swiss_attrs):
            # CAMELS-CH lat/lon are rounded; use its station coordinates in LV95.
            transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
            valid = swiss_attrs.dropna(subset=["gauge_easting", "gauge_northing"])
            longitude, latitude = transformer.transform(valid.gauge_easting.to_numpy(), valid.gauge_northing.to_numpy())
            swiss_positions = {str(g): (float(la), float(lo)) for g, la, lo in zip(valid.gauge_id, latitude, longitude)
                               if np.isfinite(la) and np.isfinite(lo)}
        for row in attrs.to_dict("records"):
            gauge_id = str(row["gauge_id"])
            name = _text(row.get("name"))
            river = _text(row.get("river") if network else row.get("water_body", row.get("river")))
            country = row.get("country") or DATASETS[dataset][1]
            if country == "Switzerland": country = "CH"
            if country == "Norway": country = "NO"
            latitude, longitude = (row.get("lat"), row.get("lon"))
            if country != "NO" and gauge_id in swiss_positions:
                latitude, longitude = swiss_positions[gauge_id]
            rows.append(dict(id=gauge_id, name=name, place=name, river=river,
                             label=f"{river} / {name} ({gauge_id})", country=country,
                             lat=latitude, lon=longitude, area_km2=row.get("area"),
                             elevation_m=row.get("elevation"),
                             elevation_statistic=row.get("elevation_statistic", "median" if country == "NO" else "mean")))
        return _clean(rows)

    def _options(self, result, dataset):
        if dataset == "stations":
            return {"pair": _option("pair", "Driver pair", [("snow", "Half-volume date / snow-free date"),
                                                            ("precipitation", "Aug–Sep low flow / Jul–Sep precipitation")])}
        metrics = [m for m in registry.METRICS if m in result.annual and result.annual[m].notna().any()]
        variables = [v for v in VARIABLE_LABELS if v in result.daily and result.daily[v].notna().any()]
        units = result.meta.get("units", {})
        label = lambda m: f"{registry.info(m).label} [{registry.info(m).unit}]"
        return {
            "metric": _option("metric", "Annual metric", [(m, label(m)) for m in metrics]),
            "driver": _option("driver", "Driver", [(m, label(m)) for m in metrics if m in registry.DRIVER_METRICS]),
            "year": _option("year", "Hydrological year", [(y, y) for y in sorted(result.annual.hydro_year.unique())]),
            "variable": _option("variable", "Time-series variable", [(v, f"{VARIABLE_LABELS[v]} [{units.get(v, '')}]") for v in variables]),
            "attribute": _option("attribute", "Catchment attribute", [(a, a.title()) for a in pipeline.ATTRIBUTE_CANDIDATES if a in result.attributes]),
            "interval": _option("interval", "Interval", [("daily", "Daily"), ("monthly", "Monthly mean")]),
            "kind": _option("kind", "Metric group", [("volume", "Volume"), ("timing", "Timing"), ("variability", "Variability"), ("driver", "Drivers")]),
            "normalized": _option("normalized", "Regime units", [("false", "Discharge"), ("true", "Normalized")]),
            "log_scale": _option("log_scale", "Colour scale", [("true", "Logarithmic"), ("false", "Linear")]),
        }

    def _views(self, result, dataset):
        options = self._options(result, dataset)
        return [{"id": ident, "label": label, "scope": scope, "table": table,
                 "options": [options[n] for n in names]} for ident, label, scope, table, names in VIEW_SPECS
                if (scope == "stations") == (dataset == "stations") and all(options[n]["values"] for n in names)]

    def catalogue(self):
        datasets = []
        for dataset in DATASETS:
            result, item = self._load(dataset)
            if result is not None:
                item.update(gauges=self._gauges(result, dataset), views=self._views(result, dataset),
                            count=len(result.gauges), source=result.meta.get("source", "station network"),
                            units=result.meta.get("units", {}), settings=result.meta.get("settings", {}),
                            provenance=result.meta.get("provenance", result.meta.get("sources", {})))
                if dataset == "stations":
                    item.update(countries=result.countries, years=sorted(result.annual.year.unique().tolist()), notes=[STATION_NOTE])
                else:
                    options = self._options(result, dataset)
                    item.update(years=sorted(result.annual.hydro_year.unique().tolist()),
                                windows=result.meta.get("windows", []), metrics=options["metric"]["values"],
                                variables=options["variable"]["values"],
                                first_date=str(result.daily.date.min().date()), last_date=str(result.daily.date.max().date()),
                                notes=[TREND_NOTE] + ([MODEL_NOTE] if item["kind"] == "model" else []))
            datasets.append(item)
        return _clean({"datasets": datasets, "stations": datasets[-1], "views": [dict(id=a, label=b, scope=c, table=d) for a,b,c,d,_ in VIEW_SPECS],
                       "incomplete": ["Risk assessment", "Prediction model"],
                       "notes": ["Only saved local results are read. Refresh re-reads local files; it does not download or build data."]})

    def _request(self, query):
        dataset = str(query.get("dataset", "ch"))
        result, state = self._load(dataset)
        if result is None: return dataset, None, state, None
        view = str(query.get("view", "station_month_heatmap" if dataset == "stations" else "timeseries"))
        spec = next((v for v in self._views(result, dataset) if v["id"] == view), None)
        if spec is None: raise ValueError("Unknown view for this dataset")
        gauge = str(query.get("gauge") or result.gauges[0])
        if gauge not in result.gauges: raise ValueError("Gauge is not in this dataset's saved selection")
        context = dict(dataset=dataset, source=state["label"], title=spec["label"], gauge=gauge,
                       period=f"{result.annual['year' if dataset == 'stations' else 'hydro_year'].min()}–{result.annual['year' if dataset == 'stations' else 'hydro_year'].max()}",
                       calendar="calendar years" if dataset == "stations" else "hydrological years",
                       hydro_year_start_month=result.meta.get("settings", {}).get("hydro_year_start_month"),
                       kind=state["kind"])
        return dataset, result, context, spec

    def _paired(self, dataset):
        region = dataset.split("_")[0]
        obs, obs_state = self._load(region)
        model, model_state = self._load(f"{region}_gldas")
        if obs is None: return None, None, obs_state
        if model is None: return None, None, model_state
        if not (set(obs.gauges) & set(model.gauges)):
            return None, None, dict(status="missing", message="Observed and GLDAS builds have no common gauges.")
        return obs, model, None

    def _comparison(self, dataset, obs, model, which):
        key = (dataset.split("_")[0], which)
        with self._lock:
            if key not in self._comparisons:
                metrics = [m for m in registry.METRICS if m in obs.annual and m in model.annual]
                self._comparisons[key] = (sources.compare_trends if which == "trends" else sources.compare_annual)(obs, model, metrics=metrics)
            return self._comparisons[key]

    @staticmethod
    def _source_context(context, comparison, kind):
        """Describe coverage reported by the backend, without refitting its results."""
        context = dict(context)
        context["source"] = "NVE + seNorge / GLDAS-2.1" if context["dataset"].startswith("no") else "CAMELS-CH / GLDAS-2.1"
        context["period"] = "Common saved years"
        context["calendar"] = "valid coverage varies by gauge/metric"
        if kind == "regime":
            years = comparison.attrs.get("years")
            if years:
                context.update(period=f"{years[0]}–{years[1]}", calendar="common hydrological years")
        elif kind == "annual" and not comparison.empty:
            context.update(period=f"{int(comparison.first_year.min())}–{int(comparison.last_year.max())}",
                           calendar="common hydrological years; valid coverage varies by gauge/metric")
        return context

    def _daily(self, result, gauge, query):
        daily = result.daily[result.daily.gauge_id == gauge].copy()
        year = int(query.get("year") or daily.hydro_year.max())
        daily = daily[daily.hydro_year == year].sort_values("date")
        if daily.empty: raise ValueError("No saved data for this gauge and hydrological year")
        return daily

    @staticmethod
    def _observed_only(frame):
        """Blank the values the trend section interpolated across short gaps (its ``*_filled`` flags).

        Graphs of daily records then draw recorded values only; an interpolated day shows as a gap.
        Returns (copy, {column: number of blanked days}). The saved tables are never changed.
        """
        frame, blanked = frame.copy(), {}
        for flag in [c for c in frame.columns if c.endswith("_filled")]:
            column = flag[: -len("_filled")]
            if column not in frame: continue
            mask = frame[flag].fillna(False).astype(bool) & frame[column].notna()
            blanked[column] = int(mask.sum())
            frame.loc[mask, column] = np.nan
        return frame, blanked

    def _observed_gauge(self, result, gauge):
        """The saved results with one gauge's interpolated days blanked, for the backend's daily-record figures."""
        daily, blanked = self._observed_only(result.daily[result.daily.gauge_id == gauge])
        return replace(result, daily=daily), blanked.get("discharge_vol", 0)

    def _timeseries(self, result, gauge, query):
        daily, blanked = self._observed_only(self._daily(result, gauge, query))
        variables = str(query.get("variables") or query.get("variable") or "discharge_vol").split(",")
        if not 1 <= len(variables) <= 4: raise ValueError("Choose one to four variables")
        if any(v not in VARIABLE_LABELS or v not in daily for v in variables): raise ValueError("Variable not available in this dataset")
        hidden = max([blanked.get(v, 0) for v in variables] or [0])  # days, not values: the flow columns share them
        if not any(daily[v].notna().any() for v in variables): raise ValueError("No values for the selected variables and year")
        interval = query.get("interval", "daily")
        if interval not in ("daily", "monthly"): raise ValueError("Unknown time interval")
        if interval == "monthly":
            daily = daily.set_index("date")[variables].resample("MS").mean().reset_index()
        fig = go.Figure()
        colors = ["#17658a", "#a84620", "#287149", "#765a22"]
        for i, variable in enumerate(variables):
            unit = result.meta.get("units", {}).get(variable, "")
            label = "GLDAS runoff" if variable == "discharge_vol" and result.meta.get("source") == "gldas" else VARIABLE_LABELS[variable]
            fig.add_trace(go.Scatter(x=daily.date, y=daily[variable], name=f"{label} [{unit}]", connectgaps=False,
                                     line=dict(color=colors[i], width=1.5), yaxis="y" if i == 0 else f"y{i+1}"))
            axis = dict(title=dict(text=f"{label} [{unit}]", font=dict(color=colors[i])), tickfont=dict(color=colors[i]))
            if i:
                axis.update(overlaying="y", side="right" if i % 2 else "left", anchor="free",
                            position={1: .9, 2: .04, 3: 1}[i], showgrid=False)
            fig.update_layout(**{"yaxis" if i == 0 else f"yaxis{i+1}": axis})
        fig.update_layout(xaxis=dict(domain=[.13 if len(variables)>2 else 0, .85 if len(variables)>1 else 1]),
                          hovermode="x unified", title=f"{gauge} / {query.get('year') or result.annual.hydro_year.max()} / {interval}",
                          # For the page: which chosen variables have no value in this year, and how many
                          # interpolated days were left out of the lines.
                          meta=dict(empty_variables=[v for v in variables if not daily[v].notna().any()],
                                    interpolated_days_hidden=hidden))
        return fig

    def _flow_surface(self, result, gauge, query):
        """The saved daily discharge as a surface: day of the hydrological year x year x flow.

        This is the grid of the backend's daily heatmap shown in 3D. Values are the saved daily
        records. Nothing is smoothed or estimated here; days the trend section interpolated
        (its ``discharge_vol_filled`` flag) are left out, so every gap stays a gap.
        """
        daily = result.daily[(result.daily.gauge_id == gauge) & (result.daily.hydro_doy <= 365)]
        daily, blanked = self._observed_only(daily)
        hidden = blanked.get("discharge_vol", 0)
        grid = daily.pivot_table(index="hydro_year", columns="hydro_doy", values="discharge_vol")
        if grid.empty: raise ValueError("No saved discharge for this gauge")
        start = int(result.meta.get("settings", {}).get("hydro_year_start_month") or 10)
        months = [(start - 1 + i) % 12 + 1 for i in range(12)]
        firsts = np.cumsum([0] + [calendar.monthrange(2001, m)[1] for m in months[:-1]]) + 1
        unit = result.meta.get("units", {}).get("discharge_vol", "")
        label = "GLDAS runoff" if result.meta.get("source") == "gldas" else "Discharge"
        fig = go.Figure(go.Surface(
            x=grid.columns.to_numpy(), y=grid.index.to_numpy(), z=grid.to_numpy(), showscale=False,
            contours=dict(z=dict(show=True, usecolormap=True, project=dict(z=True))),
            hovertemplate="Day %{x} of hydrological year %{y}: %{z:.2f} " + unit + "<extra></extra>"))
        year = query.get("year")
        if year and str(year).isdigit() and int(year) in grid.index:
            fig.add_trace(go.Scatter3d(x=grid.columns.to_numpy(), y=[int(year)] * grid.shape[1], z=grid.loc[int(year)].to_numpy(),
                                       mode="lines", line=dict(width=6), name=f"Hydrological year {int(year)}",
                                       connectgaps=False, hoverinfo="skip"))
        fig.update_layout(
            title=f"{gauge} / flow surface", height=540, showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
            meta=dict(interpolated_days_hidden=hidden),
            scene=dict(xaxis=dict(title="Day of hydrological year", tickvals=firsts.tolist(),
                                  ticktext=[calendar.month_abbr[m] for m in months]),
                       yaxis=dict(title="Hydrological year"), zaxis=dict(title=f"{label} [{unit}]"),
                       camera=dict(eye=dict(x=-1.45, y=-1.75, z=0.95)), aspectratio=dict(x=1.5, y=1.7, z=0.62)))
        return fig

    @staticmethod
    def _style(fig, theme):
        dark = theme in ("night", "dark")
        ink, paper, grid = ("#e4e8ea", "#20262a", "#424b50") if dark else ("#20272b", "#ffffff", "#dce1e4")
        fig.update_layout(template="plotly_dark" if dark else "plotly_white", font=dict(family="Arial", size=12, color=ink),
                          paper_bgcolor=paper, plot_bgcolor=paper, autosize=True, width=None,
                          title=dict(font=dict(family="Arial", size=14)),
                          hoverlabel=dict(font=dict(family="Arial", size=12)),
                          legend=dict(font=dict(family="Arial", size=12)), transition=dict(duration=0))
        fig.update_xaxes(gridcolor=grid, linecolor=grid, tickfont=dict(family="Arial", size=12), title_font=dict(family="Arial", size=12))
        fig.update_yaxes(gridcolor=grid, linecolor=grid, tickfont=dict(family="Arial", size=12), title_font=dict(family="Arial", size=12), automargin=True)
        fig.update_annotations(font=dict(family="Arial", size=12))
        for trace in fig.data:
            if trace.type == "bar": trace.update(marker_cornerradius=0)
        return json.loads(fig.to_json())

    def figure(self, query):
        try:
            dataset, result, context, spec = self._request(query)
            if result is None: return context
            view, gauge = spec["id"], context["gauge"]
            theme = "dark" if query.get("theme") in ("night", "dark") else "light"
            notes = [STATION_NOTE if dataset == "stations" else TREND_NOTE]
            if "gldas" in dataset: notes.append(MODEL_NOTE)
            metric = str(query.get("metric") or "volume_hm3")
            driver = str(query.get("driver") or "precip_total_mm")
            if "metric" in [o["name"] for o in spec["options"]] and metric not in result.annual: raise ValueError("Annual metric is unavailable")
            if spec["scope"] == "catchment" and "metric" in [o["name"] for o in spec["options"]]:
                selected = result.annual[result.annual.gauge_id == gauge]
                if not selected[metric].notna().any():
                    return dict(status="missing", message="No saved values for this gauge and annual metric.", context=context)
            if view.startswith("source_"):
                obs, model, unavailable = self._paired(dataset)
                if unavailable: return unavailable
                notes.append(MODEL_NOTE)
                if view == "source_regime":
                    if gauge not in obs.gauges or gauge not in model.gauges: return dict(status="missing", message="This gauge has no matching observed / GLDAS results.")
                    regime = sources.regime_pair(obs, model, gauge)
                    if not regime.attrs.get("years"): return dict(status="missing", message="This gauge has no common observed / GLDAS years.")
                    context = self._source_context(context, regime, "regime")
                    fig = plots.source_regime(obs, model, gauge, theme=theme)
                    fig.data[0].name = "Observed discharge (NVE)" if dataset.startswith("no") else "Observed discharge (CAMELS-CH)"
                else:
                    which = "trends" if view == "source_trend_scatter" else "annual"
                    comparison = self._comparison(dataset, obs, model, which)
                    if comparison.empty or not (comparison.metric == metric).any(): return dict(status="missing", message="Insufficient common years for this metric.")
                    context = self._source_context(context, comparison[comparison.metric == metric], which)
                    fig = getattr(plots, view)(comparison, obs, metric, theme=theme)
            elif view == "timeseries": fig = self._timeseries(result, gauge, query)
            elif view == "flow_surface": fig = self._flow_surface(result, gauge, query)
            elif view == "hydrograph_vs_history":
                daily = self._daily(result, gauge, query)
                observed, hidden = self._observed_gauge(result, gauge)
                fig = plots.hydrograph_vs_history(observed, gauge, int(daily.hydro_year.iloc[0]), theme=theme)
                fig.update_layout(meta=dict(interpolated_days_hidden=hidden))
            elif view == "regime_by_window": fig = plots.regime_by_window(result, gauge, normalized=query.get("normalized") == "true", theme=theme)
            elif view == "daily_heatmap":
                observed, hidden = self._observed_gauge(result, gauge)
                fig = plots.daily_heatmap(observed, gauge, log_scale=query.get("log_scale", "true") == "true", theme=theme)
                fig.update_layout(meta=dict(interpolated_days_hidden=hidden))
            elif view in ("annual_metric", "window_means"): fig = getattr(plots, view)(result, gauge, metric, theme=theme)
            elif view == "correlation_matrix": fig = plots.correlation_matrix(result, gauge, theme=theme)
            elif view == "driver_scatter":
                if driver not in result.annual: raise ValueError("Driver is unavailable")
                fig = plots.driver_scatter(result, gauge, metric, driver, theme=theme)
            elif view == "trend_heatmap":
                kind = query.get("kind", "volume")
                if kind not in ("volume", "timing", "variability", "driver"): raise ValueError("Unknown metric group")
                fig = plots.trend_heatmap(result, kind=kind, theme=theme)
            elif view in ("window_change_heatmap", "trend_map"): fig = getattr(plots, view)(result, metric, theme=theme)
            elif view == "trend_vs_attribute":
                attribute = query.get("attribute", "elevation")
                if attribute not in pipeline.ATTRIBUTE_CANDIDATES or attribute not in result.attributes: raise ValueError("Catchment attribute is unavailable")
                fig = plots.trend_vs_attribute(result, metric, attribute, theme=theme)
            elif view == "driver_change_scatter":
                pair = query.get("pair", "snow")
                if pair not in ("snow", "precipitation"): raise ValueError("Unknown driver pair")
                flow, driver = ("half_volume_doy", "snow_free_doy") if pair == "snow" else ("aug_sep_min7", "precip_jul_sep_mm")
                fig = plots.driver_change_scatter(result, flow, driver, theme=theme)
            else: fig = getattr(plots, view)(result, theme=theme)
            if not fig.data: return dict(status="missing", message="No saved values for this view.", context=context)
            return dict(status="ready", figure=self._style(fig, theme), context=_clean(context), notes=notes)
        except (ValueError, KeyError, TypeError) as error:
            return dict(status="error", message=str(error))
        except Exception as error:
            return dict(status="error", message=f"The backend could not render this saved view ({type(error).__name__}).")

    def table(self, query):
        try:
            dataset, result, context, spec = self._request(query)
            if result is None: return context
            name = str(query.get("table") or spec["table"])
            gauge, view = context["gauge"], spec["id"]
            if name.startswith("source_"):
                obs, model, unavailable = self._paired(dataset)
                if unavailable: return unavailable
                if name == "source_regime": frame = sources.regime_pair(obs, model, gauge)
                elif name in ("source_annual", "source_trends"): frame = self._comparison(dataset, obs, model, "trends" if name == "source_trends" else "annual")
                else: raise ValueError("Unknown source table")
            elif dataset == "stations":
                functions = {"station_trends": lambda: result.trends, "station_summary": lambda: stations.summary(result),
                             "station_year_anomalies": lambda: stations.year_anomalies(result),
                             "station_drivers": lambda: stations.driver_changes(result), "selection_log": lambda: result.selection_log}
                if name not in functions: raise ValueError("Unknown station table")
                frame = functions[name]()
            elif name == "daily":
                frame = result.daily[result.daily.gauge_id == gauge] if view in ("daily_heatmap", "flow_surface") else self._daily(result, gauge, query)
            elif name == "regime_monthly": frame = plots.monthly_regime_table(result, gauge).reset_index()
            elif name in pipeline.TABLES:
                frame = getattr(result, name)
                if spec["scope"] == "catchment" and "gauge_id" in frame: frame = frame[frame.gauge_id == gauge]
            else: raise ValueError("Unknown table")
            if query.get("metric") and "metric" in frame: frame = frame[frame.metric == query["metric"]]
            if name.startswith("source_"):
                kind = name.removeprefix("source_")
                if kind == "regime" and not frame.attrs.get("years"):
                    return dict(status="missing", message="This gauge has no common observed / GLDAS years.")
                context = self._source_context(context, frame, kind)
            rows = json.loads(frame.to_json(orient="records", date_format="iso"))
            return dict(status="ready", columns=list(frame.columns), rows=rows, context=_clean(context),
                        notes=[STATION_NOTE if dataset == "stations" else TREND_NOTE])
        except (ValueError, KeyError, TypeError) as error:
            return dict(status="error", message=str(error))
        except Exception as error:
            return dict(status="error", message=f"The backend could not read this table ({type(error).__name__}).")


_instance = None


def _backend():
    global _instance
    if _instance is None or _instance.data_root != Path(DATA_ROOT): _instance = Backend(DATA_ROOT)
    return _instance


def catalogue(): return _backend().catalogue()
def figure(query): return _backend().figure(query)
def table(query): return _backend().table(query)
def refresh(): return _backend().refresh()
