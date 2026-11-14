import plotly.graph_objects as go


def catchment_map(outlet):
    figure = go.Figure()
    if outlet.geometry:
        polygons = ([outlet.geometry["coordinates"]] if outlet.geometry["type"] == "Polygon"
                    else outlet.geometry["coordinates"])
        for polygon in polygons:
            for ring in polygon:
                figure.add_trace(go.Scattermap(lon=[p[0] for p in ring], lat=[p[1] for p in ring],
                    mode="lines", line={"width": 2, "color": "#137b80"},
                    name="Upstream catchment", showlegend=False))
    if outlet.latitude is not None and outlet.longitude is not None:
        figure.add_trace(go.Scattermap(lat=[outlet.latitude], lon=[outlet.longitude],
            mode="markers", marker={"size": 13, "color": "#e76e3c"},
            text=[outlet.name], name="Measured outlet", hovertemplate="%{text}<extra></extra>"))
    figure.update_layout(map={"style": "open-street-map", "zoom": 9,
        "center": {"lat": outlet.latitude or 47, "lon": outlet.longitude or 10}},
        height=350, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    return figure, {"source": outlet.catchment_source, "geometry_available": outlet.geometry is not None,
                    "tiles": "OpenStreetMap contributors", "crs": "EPSG:4326"}
