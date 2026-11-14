import pandas as pd
import plotly.express as px


def event_figure(exposure):
    rows = exposure.get("events", [])
    table = pd.DataFrame(rows)
    if table.empty:
        return None, {"status": "no_observed_events"}
    table["duration_days"] = table.duration_seconds / 86400
    figure = px.bar(table, x="start", y="duration_days", color="deficit_volume_m3",
        hover_data=["end", "start_censored", "end_censored"],
        labels={"start": "Observed event start", "duration_days": "Observed duration (days)",
                "deficit_volume_m3": "Deficit (m³)"}, color_continuous_scale="Oranges")
    figure.update_layout(template="plotly_white", height=320)
    return figure, {"meaning": exposure["event_interpretation"]}
