"""Command line for the trend pipeline.

Switzerland, CAMELS-CH (observed, 1981-2020):
    python -m mountain_water.trend download            # fetch CAMELS-CH from Zenodo into data/raw/camels_ch
    python -m mountain_water.trend inspect             # print the real file layout / columns
    python -m mountain_water.trend build               # parse, filter, compute -> data/processed/trend
    python -m mountain_water.trend report [--gauge ID] # write interactive HTML figures to data/exports/trend

Norway, NVE (observed discharge + seNorge, 1961-latest); needs NVE_API_KEY:
    python -m mountain_water.trend inspect --source nve   # real field names of HydAPI / outlines / seNorge
    python -m mountain_water.trend download --source nve  # -> data/raw/nve (cached, resumable)
    python -m mountain_water.trend build --source nve     # -> data/processed/trend_no
    python -m mountain_water.trend report --source nve    # -> data/exports/trend_no

Station x month heatmap, the highest CAMELS-CH river gauges with complete records:
    python -m mountain_water.trend stations [--n-gauges 100] [--period 1981 2020]  # -> data/exports/trend_stations

GLDAS-2.1 Noah (modelled, 2000-now) for either region's selection; needs EARTHDATA_TOKEN:
    python -m mountain_water.trend download --source gldas [--region no] [--probe]
    python -m mountain_water.trend build --source gldas [--region no]   # -> data/processed/trend[_no]_gldas
    python -m mountain_water.trend report --source gldas [--region no]  # incl. observed vs GLDAS
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from . import camels_ch, gldas, nve, pipeline, plots, sources, stations
from .settings import StationNetworkSettings, TrendSettings

SOURCES = ["camels", "nve", "gldas"]


def _region(args) -> str:
    return "no" if args.source == "nve" else ("ch" if args.source == "camels" else args.region)


def _base_settings(args) -> TrendSettings:
    if args.source == "gldas":
        return TrendSettings.gldas(args.region)
    return TrendSettings.nve() if args.source == "nve" else TrendSettings()


def _settings(args) -> TrendSettings:
    s = _base_settings(args)
    if args.source != "gldas":  # GLDAS reuses the observed selection; these filters don't apply
        for attr, value in (("min_mean_elevation_m", args.min_elevation), ("max_area_km2", args.max_area)):
            if value is not None:
                setattr(s.filters, attr, value)
        if args.max_reservoirs is not None:
            s.filters.max_reservoirs = None if args.max_reservoirs < 0 else args.max_reservoirs
    if args.min_years is not None:
        s.filters.min_valid_years = args.min_years
    s.window_years = args.window_years
    s.hydro_year_start_month = args.hydro_year_start
    return s


def _figures(r, gauges: list[str]) -> dict:
    has_coords = {"lat", "lon"} <= set(r.attributes)
    figures = {
        "selection": plots.selection_summary(r),
        "trends_volume": plots.trend_heatmap(r, "volume"),
        "trends_timing": plots.trend_heatmap(r, "timing"),
        "trends_drivers": plots.trend_heatmap(r, "driver"),
        "map_mean_flow": plots.trend_map(r, "mean_flow") if has_coords else None,
        "map_com_doy": plots.trend_map(r, "com_doy") if has_coords else None,
        "decades_mean_flow": plots.window_change_heatmap(r, "mean_flow"),
        "decades_com_doy": plots.window_change_heatmap(r, "com_doy"),
        "correlation_all": plots.correlation_matrix(r),
        "attribution": plots.attribution_bars(r),
        "elevation_vs_com_trend": plots.trend_vs_attribute(r, "com_doy", "elevation") if "elevation" in r.attributes else None,
    }
    for gauge_id in gauges:
        last = int(r.annual.loc[r.annual["gauge_id"] == gauge_id, "hydro_year"].max())
        figures |= {
            f"{gauge_id}_year_vs_history": plots.hydrograph_vs_history(r, gauge_id, last),
            f"{gauge_id}_regime": plots.regime_by_window(r, gauge_id),
            f"{gauge_id}_heatmap": plots.daily_heatmap(r, gauge_id),
            f"{gauge_id}_mean_flow": plots.annual_metric(r, gauge_id, "mean_flow"),
            f"{gauge_id}_com_doy": plots.annual_metric(r, gauge_id, "com_doy"),
            f"{gauge_id}_decades_summer_flow": plots.window_means(r, gauge_id, "summer_mean_flow"),
            f"{gauge_id}_correlation": plots.correlation_matrix(r, gauge_id),
        }
    return figures


def _report(args) -> None:
    settings = _base_settings(args)
    region = _region(args)
    r = pipeline.load(settings.processed_dir)
    default_out = "data/exports/" + settings.processed_dir.name
    out = Path(args.out or default_out)
    out.mkdir(parents=True, exist_ok=True)
    gauges = [g for g in (args.gauge or r.gauges[:1]) if g in r.gauges]
    figures = _figures(r, gauges)
    tables = {name: getattr(r, name) for name in
              ("trends", "window_comparison", "correlation_summary", "attribution", "selection_log")}

    observed_dir = TrendSettings.observed(region).processed_dir
    if args.source == "gldas" and (observed_dir / "meta.json").exists():
        obs = pipeline.load(observed_dir)
        annual_cmp = sources.compare_annual(obs, r)
        trend_cmp = sources.compare_trends(obs, r)
        tables |= {"obs_vs_gldas_annual": annual_cmp, "obs_vs_gldas_trends": trend_cmp,
                   "obs_vs_gldas_summary": sources.summary(annual_cmp, trend_cmp)}
        for metric in ("runoff_mm", "summer_mean_flow", "com_doy", "precip_total_mm", "temp_mean"):
            if (annual_cmp["metric"] == metric).any():
                figures[f"obs_vs_gldas_{metric}"] = plots.source_scatter(annual_cmp, obs, metric)
            if not trend_cmp.empty and (trend_cmp["metric"] == metric).any():
                figures[f"obs_vs_gldas_trend_{metric}"] = plots.source_trend_scatter(trend_cmp, obs, metric)
        for gauge_id in gauges:
            if gauge_id in obs.gauges:
                figures[f"{gauge_id}_obs_vs_gldas_regime"] = plots.source_regime(obs, r, gauge_id)

    written = 0
    for name, fig in figures.items():
        if fig is not None:
            fig.write_html(out / f"{name.replace('.', '_')}.html", include_plotlyjs="cdn")
            written += 1
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=False)
    print(f"Wrote {written} figures and {len(tables)} tables to {out}")


def _stations(args) -> None:
    s = StationNetworkSettings(n_gauges=args.n_gauges, first_year=args.period[0], last_year=args.period[1],
                               baseline=tuple(args.baseline), country=None if args.all_countries else "CH")
    net = stations.build(s)
    out = Path(args.out or "data/exports/" + s.processed_dir.name)
    out.mkdir(parents=True, exist_ok=True)
    figures = {"station_month_heatmap": plots.station_month_heatmap(net),
               "station_year_heatmaps": plots.station_year_heatmaps(net)}
    for name, fig in figures.items():
        fig.write_html(out / f"{name}.html", include_plotlyjs="cdn")
    summary = stations.summary(net)
    tables = {"station_month_trends": stations.wide_table(net), "station_month_trends_long": net.trends,
              "station_month_summary": summary, "station_year_anomalies": stations.year_anomalies(net),
              "station_selection_log": net.selection_log}
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=False, float_format="%.4g")
    print(net.selection_log.to_string(index=False))
    print(summary[["label", "n_negative", "n_positive", "median_change_per_decade", "unit"]].to_string(index=False))
    print(f"Wrote {len(figures)} figures and {len(tables)} tables to {out}")


def _download_gldas(args) -> None:
    if args.probe:
        print(gldas.probe())
        return
    s = TrendSettings.gldas(args.region)
    gauges = args.gauge or pipeline.observed_selection(args.region)
    _, weights = pipeline.gldas_inputs(args.region, gauges, s)
    n_cells = len(weights[["cell_lat", "cell_lon"]].drop_duplicates())
    print(f"{weights['gauge_id'].nunique()} catchments -> {n_cells} GLDAS cells; downloading to {s.gldas_raw_dir}")
    log = gldas.download(weights, s.gldas_raw_dir, start=args.start or gldas.START, end=args.end,
                         chunk_years=args.chunk_years or 5, workers=args.workers or 4)
    _report_failures(log, s.gldas_raw_dir)


def _download_nve(args) -> None:
    s = TrendSettings.nve()
    log = nve.download(
        s.nve_raw_dir, start=args.start or nve.START, end=args.end,
        min_elevation=s.filters.min_mean_elevation_m if args.min_elevation is None else args.min_elevation,
        max_area=s.filters.max_area_km2 if args.max_area is None else args.max_area,
        min_years=s.filters.min_valid_years, workers=args.workers or 6,
    )
    _report_failures(log, s.nve_raw_dir)


def _report_failures(log, raw_dir: Path) -> None:
    failed = log[log["error"] != ""]
    print(f"Fetched {len(log) - len(failed)} requests, {len(failed)} failed (cached requests are skipped).")
    if len(failed):
        path = raw_dir / "failed_requests.csv"
        failed.to_csv(path, index=False)
        print(f"Failures listed in {path}; rerun the same command to retry them.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m mountain_water.trend", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    def source_args(parser, region=True):
        parser.add_argument("--source", choices=SOURCES, default="camels",
                            help="camels = CAMELS-CH (Switzerland), nve = NVE (Norway), gldas = NASA GLDAS-2.1")
        if region:
            parser.add_argument("--region", choices=["ch", "no"], default="ch",
                                help="GLDAS only: which observed catchment selection to use")

    d = sub.add_parser("download", help="Download CAMELS-CH, NVE or GLDAS data")
    source_args(d)
    d.add_argument("--record", default=camels_ch.DEFAULT_RECORD_ID, help="CAMELS-CH: Zenodo record id")
    d.add_argument("--exact", action="store_true", help="CAMELS-CH: use exactly this record, not the latest version")
    d.add_argument("--file", default=None, help="CAMELS-CH: file name inside the record")
    d.add_argument("--gauge", action="append", help="GLDAS: catchment id (repeatable; default: observed selection)")
    d.add_argument("--start", default=None, help="NVE/GLDAS: first day (default 1960-10-01 / 2000-01-01)")
    d.add_argument("--end", default=None, help="NVE/GLDAS: last day (default: latest complete period)")
    d.add_argument("--min-elevation", type=float, default=None, help="NVE: minimum median elevation for download")
    d.add_argument("--max-area", type=float, default=None, help="NVE: maximum catchment area for download")
    d.add_argument("--chunk-years", type=int, default=None, help="GLDAS: years per request (default 5)")
    d.add_argument("--workers", type=int, default=None, help="NVE/GLDAS: parallel requests (default 6 / 4)")
    d.add_argument("--probe", action="store_true", help="GLDAS: one small test request, prints the raw response")

    i = sub.add_parser("inspect", help="Show real file layout (CAMELS-CH) or API field names (NVE)")
    source_args(i, region=False)

    b = sub.add_parser("build", help="Parse, filter and compute all trend tables")
    source_args(b)
    b.add_argument("--gauge", action="append", help="GLDAS: catchment id (repeatable; default: observed selection)")
    b.add_argument("--min-elevation", type=float, default=None,
                   help="Minimum catchment elevation in m (CAMELS-CH mean, default 1500; NVE median, default 800)")
    b.add_argument("--max-area", type=float, default=None, help="Maximum catchment area in km² (default 500)")
    b.add_argument("--max-reservoirs", type=int, default=None,
                   help="Maximum reservoirs / regulation flag (default 0; -1 = no limit)")
    b.add_argument("--min-years", type=int, default=None, help="Minimum valid years (default 30; GLDAS 20)")
    b.add_argument("--window-years", type=int, default=10, help="Length of comparison windows (years)")
    b.add_argument("--hydro-year-start", type=int, default=10, help="First month of the hydrological year")

    rp = sub.add_parser("report", help="Write HTML figures and CSV tables")
    source_args(rp)
    rp.add_argument("--gauge", action="append", help="Gauge id for single-catchment figures (repeatable)")
    rp.add_argument("--out", default=None, help="Output folder (default data/exports/<processed folder name>)")

    st = sub.add_parser("stations", help="Station x month heatmap of the highest CAMELS-CH river gauges")
    st.add_argument("--n-gauges", type=int, default=100, help="Number of gauges, highest mean elevation first")
    st.add_argument("--period", type=int, nargs=2, default=(1981, 2020), metavar=("FIRST", "LAST"),
                    help="Calendar years that must be complete (default 1981 2020)")
    st.add_argument("--baseline", type=int, nargs=2, default=(1981, 2000), metavar=("FIRST", "LAST"),
                    help="Years whose mean the % changes refer to (default 1981 2000)")
    st.add_argument("--all-countries", action="store_true", help="Also use CAMELS-CH gauges outside Switzerland")
    st.add_argument("--out", default=None, help="Output folder (default data/exports/trend_stations)")

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    try:
        _run(args)
    except (RuntimeError, FileNotFoundError, PermissionError, ValueError) as exc:
        if args.verbose:
            raise
        raise SystemExit(f"Error: {exc}") from None


def _run(args) -> None:
    if args.command == "download":
        if args.source == "gldas":
            _download_gldas(args)
        elif args.source == "nve":
            _download_nve(args)
        else:
            path = camels_ch.download(record_id=args.record, latest=not args.exact, file_name=args.file)
            print(f"CAMELS-CH extracted to {path}")
    elif args.command == "inspect":
        if args.source == "nve":
            print(nve.describe(nve.NveClient(os.environ.get("NVE_API_KEY", "").strip() or None)))
        else:
            print(camels_ch.describe(camels_ch.find_dataset_root(TrendSettings().raw_dir)))
    elif args.command == "build":
        s = _settings(args)
        if args.source == "gldas":
            r = pipeline.build_gldas(s, args.gauge, region=args.region)
        elif args.source == "nve":
            r = pipeline.build_nve(s)
        else:
            r = pipeline.build(s)
        print(r.selection_log.to_string(index=False))
        print(f"Windows: {', '.join(r.meta['windows'])}")
        print(f"Saved to {s.processed_dir}")
    elif args.command == "report":
        _report(args)
    elif args.command == "stations":
        _stations(args)


if __name__ == "__main__":
    main()
