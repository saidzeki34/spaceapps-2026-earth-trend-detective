import plotly.express as px


def comparison_figures(points):
    hover = ["outlet", "years", "baseline", "season", "n", "coverage", "uncertainty", "regulation"]
    labels = {"quantity_pct_decade": "Quantity (% / decade)", "timing_days_decade": "Timing (days / decade)",
              "variability_pct": "Detrended variability (%)"}
    three = px.scatter_3d(points, x="quantity_pct_decade", y="timing_days_decade", z="variability_pct",
                          color="outlet", hover_data=hover, labels=labels)
    two = px.scatter(points, x="quantity_pct_decade", y="timing_days_decade", color="variability_pct",
                     hover_data=hover, labels=labels, color_continuous_scale="Teal")
    three.update_layout(height=470, margin={"t": 10, "b": 10})
    two.update_traces(marker_size=14)
    two.update_layout(template="plotly_white", height=370)
    return (three, two), {"meaning": "Each point is one outlet and analysis window. No combined risk score."}


def seasonal_figure(periods):
    figure = px.bar(periods, x="year", y="season_volume_m3", labels={
        "year": "Water year (starting calendar year)", "season_volume_m3": "Complete seasonal volume (m³)"},
        hover_data=["coverage", "half_volume_day", "annual_coverage"])
    figure.update_layout(template="plotly_white", height=310)
    return figure, {"completeness": "100% valid daily coverage required; incomplete periods omitted."}
