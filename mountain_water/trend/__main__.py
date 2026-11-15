"""Command line for the trend pipeline.

CAMELS-CH (observed, 1981-2020):
    python -m mountain_water.trend download            # fetch CAMELS-CH from Zenodo into data/raw/camels_ch
    python -m mountain_water.trend inspect             # print the real file layout / columns
    python -m mountain_water.trend build               # parse, filter, compute -> data/processed/trend
    python -m mountain_water.trend report [--gauge ID] # write interactive HTML figures to data/exports/trend

GLDAS-2.1 Noah (modelled, 2000-now) for the same catchments; needs EARTHDATA_TOKEN and a CAMELS-CH build:
    python -m mountain_water.trend download --source gldas --probe   # one small request to test token/format
    python -m mountain_water.trend download --source gldas           # -> data/raw/gldas (cached, resumable)
    python -m mountain_water.trend build --source gldas              # -> data/processed/trend_gldas
    python -m mountain_water.trend report --source gldas [--gauge ID] # -> data/exports/trend_gldas (+ obs vs GLDAS)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import camels_ch, gldas, pipeline, plots, sources
from .settings import TrendSettings


def _settings(args) -> TrendSettings:
    s = TrendSettings.gldas() if args.source == "gldas" else TrendSettings()
    s.filters.min_mean_elevation_m = args.min_elevation
    s.filters.max_area_km2 = args.max_area
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
    gldas_run = args.source == "gldas"
    settings = TrendSettings.gldas() if gldas_run else TrendSettings()
    r = pipeline.load(settings.processed_dir)
    out = Path(args.out or ("data/exports/trend_gldas" if gldas_run else "data/exports/trend"))
    out.mkdir(parents=True, exist_ok=True)
    gauges = [g for g in (args.gauge or r.gauges[:1]) if g in r.gauges]
    figures = _figures(r, gauges)
    tables = {name: getattr(r, name) for name in
              ("trends", "window_comparison", "correlation_summary", "attribution", "selection_log")}

    if gldas_run and (TrendSettings().processed_dir / "meta.json").exists():
        obs = pipeline.load(TrendSettings().processed_dir)
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
            fig.write_html(out / f"{name}.html", include_plotlyjs="cdn")
            written += 1
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=False)
    print(f"Wrote {written} figures and {len(tables)} tables to {out}")


def _download_gldas(args) -> None:
    if args.probe:
        print(gldas.probe())
        return
    root = camels_ch.find_dataset_root(TrendSettings().raw_dir)
    gauges = args.gauge or pipeline.camels_selection()
    weights = gldas.catchment_weights(root, gauges)
    n_cells = len(weights[["cell_lat", "cell_lon"]].drop_duplicates())
    print(f"{len(gauges)} catchments -> {n_cells} GLDAS cells; downloading to {TrendSettings().gldas_raw_dir}")
    log = gldas.download(weights, TrendSettings().gldas_raw_dir, start=args.start, end=args.end,
                         chunk_years=args.chunk_years, workers=args.workers)
    failed = log[log["error"] != ""]
    print(f"Fetched {len(log) - len(failed)} requests, {len(failed)} failed (cached requests are skipped).")
    if len(failed):
        path = TrendSettings().gldas_raw_dir / "failed_requests.csv"
        failed.to_csv(path, index=False)
        print(f"Failures listed in {path}; rerun the same command to retry them.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m mountain_water.trend", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("download", help="Download CAMELS-CH (Zenodo) or GLDAS (Giovanni API)")
    d.add_argument("--source", choices=["camels", "gldas"], default="camels")
    d.add_argument("--record", default=camels_ch.DEFAULT_RECORD_ID, help="CAMELS-CH: Zenodo record id")
    d.add_argument("--exact", action="store_true", help="CAMELS-CH: use exactly this record, not the latest version")
    d.add_argument("--file", default=None, help="CAMELS-CH: file name inside the record")
    d.add_argument("--gauge", action="append", help="GLDAS: catchment id (repeatable; default: CAMELS-CH selection)")
    d.add_argument("--start", default=gldas.START, help="GLDAS: first day (YYYY-MM-DD)")
    d.add_argument("--end", default=None, help="GLDAS: last day (default: ~4 months ago)")
    d.add_argument("--chunk-years", type=int, default=5, help="GLDAS: years per API request")
    d.add_argument("--workers", type=int, default=4, help="GLDAS: parallel requests")
    d.add_argument("--probe", action="store_true", help="GLDAS: one small test request, prints the raw response")

    sub.add_parser("inspect", help="Show the downloaded CAMELS-CH layout and columns")

    b = sub.add_parser("build", help="Parse, filter and compute all trend tables")
    b.add_argument("--source", choices=["camels", "gldas"], default="camels")
    b.add_argument("--gauge", action="append", help="GLDAS: catchment id (repeatable; default: CAMELS-CH selection)")
    b.add_argument("--min-elevation", type=float, default=1500.0, help="Minimum mean catchment elevation (m)")
    b.add_argument("--max-area", type=float, default=500.0, help="Maximum catchment area (km²)")
    b.add_argument("--max-reservoirs", type=int, default=0, help="Maximum number of reservoirs (-1 = no limit)")
    b.add_argument("--min-years", type=int, default=None, help="Minimum valid years (default 30 CAMELS-CH, 20 GLDAS)")
    b.add_argument("--window-years", type=int, default=10, help="Length of comparison windows (years)")
    b.add_argument("--hydro-year-start", type=int, default=10, help="First month of the hydrological year")

    rp = sub.add_parser("report", help="Write HTML figures and CSV tables")
    rp.add_argument("--source", choices=["camels", "gldas"], default="camels")
    rp.add_argument("--gauge", action="append", help="Gauge id for single-catchment figures (repeatable)")
    rp.add_argument("--out", default=None, help="Output folder (default data/exports/trend[_gldas])")

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    try:
        _run(args)
    except (RuntimeError, FileNotFoundError, PermissionError) as exc:
        if args.verbose:
            raise
        raise SystemExit(f"Error: {exc}") from None


def _run(args) -> None:
    if args.command == "download":
        if args.source == "gldas":
            _download_gldas(args)
        else:
            path = camels_ch.download(record_id=args.record, latest=not args.exact, file_name=args.file)
            print(f"CAMELS-CH extracted to {path}")
    elif args.command == "inspect":
        print(camels_ch.describe(camels_ch.find_dataset_root(TrendSettings().raw_dir)))
    elif args.command == "build":
        s = _settings(args)
        r = pipeline.build_gldas(s, args.gauge) if args.source == "gldas" else pipeline.build(s)
        print(r.selection_log.to_string(index=False))
        print(f"Windows: {', '.join(r.meta['windows'])}")
        print(f"Saved to {s.processed_dir}")
    elif args.command == "report":
        _report(args)


if __name__ == "__main__":
    main()
