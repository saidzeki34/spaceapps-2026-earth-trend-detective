"""The prediction year and the physical-model section.

Neither has a real source yet: the prediction model section is still empty.
Everything returned here is imaginary and marked as such, so the screens have
something to show. Replace the calls to ``imaginary`` when the model exists.
"""

from __future__ import annotations

from mountain_water.ui import controls, imaginary, trend_view
from mountain_water.ui.data_source import RiverData

_DISCHARGE = controls.VARIABLES_BY_ID["discharge"]
_MONTHS = {"kind": "months", "count": 12}


def chart(data: RiverData, variable_ids: list[str], year: int, with_usual: bool) -> dict:
    """An imaginary prediction for each ticked variable: one value per month of the year ahead."""
    series = []
    for variable_id in variable_ids:
        variable = controls.VARIABLES_BY_ID[variable_id]
        usual = trend_view.usual_monthly(data, variable)
        values = imaginary.predict_monthly(
            usual, f"{data.river.id}|{variable.id}|{year}", additive=variable.id == "temperature"
        )
        series.append({
            "id": variable.id, "label": variable.label, "unit": variable.unit, "color": variable.color,
            "group": variable.group, "values": values, "usual": usual if with_usual else None,
            "imaginary": True, "predicted": True,
        })
    return {"x": {**_MONTHS, "year": year}, "series": series}


def predicted_flow(data: RiverData, year: int) -> list[float | None]:
    """The imaginary predicted discharge of each month, for the risk section."""
    return imaginary.predict_monthly(
        trend_view.usual_monthly(data, _DISCHARGE), f"{data.river.id}|{_DISCHARGE.id}|{year}"
    )


def physical_model(data: RiverData, year: int, predicted: bool) -> dict:
    """Imaginary output of the team's physical flow model next to the discharge of that year."""
    reference = predicted_flow(data, year) if predicted else trend_view.monthly_values(data, _DISCHARGE, year)
    base = [r if r is not None else u for r, u in zip(reference, trend_view.usual_monthly(data, _DISCHARGE))]
    modelled, agreement = imaginary.model_monthly(base, f"{data.river.id}|{year}")
    return {
        "chart": {
            "x": {**_MONTHS, "year": year},
            "series": [
                {"id": "reference", "label": "Predicted discharge" if predicted else "Discharge",
                 "unit": _DISCHARGE.unit, "color": _DISCHARGE.color, "values": reference, "usual": None,
                 "imaginary": predicted or data.is_imaginary(_DISCHARGE.column), "predicted": predicted},
                {"id": "model", "label": "Physical model", "unit": _DISCHARGE.unit, "color": "#a14a76",
                 "values": modelled, "usual": None, "imaginary": True, "predicted": False},
            ],
        },
        "agreement": f"{agreement:.2f}",
        "note": (
            "The team's physical flow model has not been supplied yet. The model line and the agreement "
            "figure are imaginary placeholders."
        ),
    }
