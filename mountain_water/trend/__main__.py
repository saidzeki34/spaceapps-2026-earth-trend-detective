"""Command line for the trend pipeline.

    python -m mountain_water.trend download            # fetch CAMELS-CH from Zenodo into data/raw/camels_ch
    python -m mountain_water.trend inspect             # print the real file layout / columns
    python -m mountain_water.trend build               # parse, filter, compute -> data/processed/trend
    python -m mountain_water.trend report [--gauge ID] # write interactive HTML figures to data/exports/trend
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import camels_ch, pipeline, plots
from .settings import TrendSettings


def _settings(args) -> TrendSettings:
    s = TrendSettings()
    s.filters.min_mean_elevation_m = args.min_elevation
    s.filters.max_area_km2 = args.max_area
    s.filters.max_reservoirs = None if args.max_reservoirs < 0 else args.max_reservoirs
    s.filters.min_valid_years = args.min_years
    s.window_years = args.window_years
    s.hydro_year_start_month = args.hydro_year_start
    return s


def _report(args) -> None:
    r = pipeline.load()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    figures = {
        "selection": plots.selection_summary(r),
        "trends_volume": plots.trend_heatmap(r, "volume"),
        "trends_timing": plots.trend_heatmap(r, "timing"),
        "trends_drivers": plots.trend_heatmap(r, "driver"),
        "map_mean_flow": plots.trend_map(r, "mean_flow") if {"lat", "lon"} <= set(r.attributes) else None,
        "map_com_doy": plots.trend_map(r, "com_doy") if {"lat", "lon"} <= set(r.attributes) else None,
        "decades_mean_flow": plots.window_change_heatmap(r, "mean_flow"),
        "decades_com_doy": plots.window_change_heatmap(r, "com_doy"),
        "correlation_all": plots.correlation_matrix(r),
        "attribution": plots.attribution_bars(r),
        "elevation_vs_com_trend": plots.trend_vs_attribute(r, "com_doy", "elevation") if "elevation" in r.attributes else None,
    }
    for gauge_id in args.gauge or r.gauges[:1]:
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
    for name, fig in figures.items():
        if fig is not None:
            fig.write_html(out / f"{name}.html", include_plotlyjs="cdn")
    for name in ("trends", "window_comparison", "correlation_summary", "attribution", "selection_log"):
        getattr(r, name).to_csv(out / f"{name}.csv", index=False)
    print(f"Wrote {sum(f is not None for f in figures.values())} figures and tables to {out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m mountain_water.trend", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("download", help="Download CAMELS-CH from Zenodo")
    d.add_argument("--record", default=camels_ch.DEFAULT_RECORD_ID, help="Zenodo record id")
    d.add_argument("--exact", action="store_true", help="Use exactly this record instead of the latest version")
    d.add_argument("--file", default=None, help="File name inside the record (default: the CAMELS-CH zip)")

    sub.add_parser("inspect", help="Show the downloaded dataset layout and columns")

    b = sub.add_parser("build", help="Parse, filter and compute all trend tables")
    b.add_argument("--min-elevation", type=float, default=1500.0, help="Minimum mean catchment elevation (m)")
    b.add_argument("--max-area", type=float, default=500.0, help="Maximum catchment area (km²)")
    b.add_argument("--max-reservoirs", type=int, default=0, help="Maximum number of reservoirs (-1 = no limit)")
    b.add_argument("--min-years", type=int, default=30, help="Minimum number of valid years")
    b.add_argument("--window-years", type=int, default=10, help="Length of comparison windows (years)")
    b.add_argument("--hydro-year-start", type=int, default=10, help="First month of the hydrological year")

    rp = sub.add_parser("report", help="Write HTML figures and CSV tables")
    rp.add_argument("--gauge", action="append", help="Gauge id for single-catchment figures (repeatable)")
    rp.add_argument("--out", default="data/exports/trend")

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    if args.command == "download":
        path = camels_ch.download(record_id=args.record, latest=not args.exact, file_name=args.file)
        print(f"CAMELS-CH extracted to {path}")
    elif args.command == "inspect":
        print(camels_ch.describe(camels_ch.find_dataset_root(TrendSettings().raw_dir)))
    elif args.command == "build":
        r = pipeline.build(_settings(args))
        print(r.selection_log.to_string(index=False))
        print(f"Windows: {', '.join(r.meta['windows'])}")
        print(f"Saved to {TrendSettings().processed_dir}")
    elif args.command == "report":
        _report(args)


if __name__ == "__main__":
    main()
