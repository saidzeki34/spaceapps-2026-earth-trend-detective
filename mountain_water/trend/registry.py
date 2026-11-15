"""Labels, units and kinds of the annual metrics produced by the trend pipeline.

kind:
    volume      how much water (relative change in % is meaningful)
    timing      when water arrives (day of hydrological year; change reported in days)
    variability how variable the flow is
    driver      meteorological/snow drivers from the observed CAMELS-CH series
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricInfo:
    label: str
    unit: str
    kind: str
    description: str
    # False where a % change is meaningless (dates, temperatures): changes are reported in units.
    relative: bool = True


METRICS: dict[str, MetricInfo] = {
    # volume
    "mean_flow": MetricInfo("Mean flow", "m³/s", "volume", "Mean daily discharge over the hydrological year"),
    "runoff_mm": MetricInfo("Annual runoff", "mm", "volume", "Specific discharge summed over the year (depth over the catchment)"),
    "volume_hm3": MetricInfo("Annual volume", "hm³", "volume", "Total discharged volume (million m³)"),
    "winter_mean_flow": MetricInfo("Winter mean flow", "m³/s", "volume", "Mean discharge Oct–Mar"),
    "summer_mean_flow": MetricInfo("Summer mean flow", "m³/s", "volume", "Mean discharge Apr–Sep"),
    "q95_low": MetricInfo("Low flow (Q95)", "m³/s", "volume", "Flow exceeded on 95 % of the days of the year"),
    "min7_flow": MetricInfo("7-day minimum flow", "m³/s", "volume", "Lowest 7-day mean discharge of the year"),
    "q10_high": MetricInfo("High flow (Q10)", "m³/s", "volume", "Flow exceeded on 10 % of the days of the year"),
    "peak_flow": MetricInfo("Peak flow", "m³/s", "volume", "Highest daily discharge of the year"),
    "days_below_q347": MetricInfo("Days below Q347", "days", "volume", "Days below the long-term Q347 (Swiss minimum-flow reference)"),
    # timing
    "com_doy": MetricInfo("Centre of mass", "day of hydro year", "timing", "Flow-weighted mean day of the year", relative=False),
    "half_volume_doy": MetricInfo("Half-volume date", "day of hydro year", "timing", "Day when 50 % of the annual volume has passed", relative=False),
    "peak_doy": MetricInfo("Peak date", "day of hydro year", "timing", "Day of the highest daily discharge", relative=False),
    "onset_doy": MetricInfo("High-flow onset", "day of hydro year", "timing", "Start of the high-flow (snowmelt) season, cumulative-departure method", relative=False),
    "low_flow_doy": MetricInfo("Low-flow date", "day of hydro year", "timing", "Centre day of the lowest 7-day mean discharge", relative=False),
    # variability
    "cv_daily": MetricInfo("Daily flow CV", "-", "variability", "Coefficient of variation of daily discharge within the year"),
    "flashiness": MetricInfo("Flashiness", "-", "variability", "Richards-Baker index: sum of day-to-day changes / total flow"),
    # drivers
    "precip_total_mm": MetricInfo("Precipitation", "mm", "driver", "Annual precipitation"),
    "precip_winter_mm": MetricInfo("Winter precipitation", "mm", "driver", "Precipitation Oct–Mar"),
    "precip_summer_mm": MetricInfo("Summer precipitation", "mm", "driver", "Precipitation Apr–Sep"),
    "snowfall_frac": MetricInfo("Snowfall fraction", "-", "driver", "Share of precipitation falling as snow (GLDAS: modelled snowfall; CAMELS-CH: days with mean temperature ≤ 0 °C)"),
    "snowmelt_total_mm": MetricInfo("Snowmelt", "mm", "driver", "Annual snowmelt (GLDAS)"),
    "evap_total_mm": MetricInfo("Evapotranspiration", "mm", "driver", "Annual evapotranspiration (GLDAS)"),
    "temp_mean": MetricInfo("Mean temperature", "°C", "driver", "Annual mean air temperature", relative=False),
    "temp_spring": MetricInfo("Spring temperature", "°C", "driver", "Mean air temperature Mar–May", relative=False),
    "temp_summer": MetricInfo("Summer temperature", "°C", "driver", "Mean air temperature Jun–Aug", relative=False),
    "swe_max_mm": MetricInfo("Peak snow water equivalent", "mm", "driver", "Highest daily SWE of the year"),
    "swe_peak_doy": MetricInfo("SWE peak date", "day of hydro year", "driver", "Day of the highest SWE", relative=False),
    "swe_meltout_doy": MetricInfo("Snow melt-out date", "day of hydro year", "driver", "First day after the SWE peak with SWE ≤ 5 % of the peak", relative=False),
    "sun_mean_pct": MetricInfo("Relative sunshine", "%", "driver", "Mean relative sunshine duration"),
    "runoff_ratio": MetricInfo("Runoff ratio", "-", "driver", "Annual runoff / annual precipitation"),
}

FLOW_METRICS = [m for m, i in METRICS.items() if i.kind in ("volume", "timing", "variability")]
DRIVER_METRICS = [m for m, i in METRICS.items() if i.kind == "driver"]


def info(metric: str) -> MetricInfo:
    return METRICS.get(metric, MetricInfo(metric, "", "other", ""))


def axis_label(metric: str) -> str:
    i = info(metric)
    return f"{i.label} ({i.unit})" if i.unit and i.unit != "-" else i.label
