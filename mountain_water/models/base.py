from datetime import date
from typing import Protocol

from mountain_water.contracts import FlowSeries, ForecastResult


class FlowModel(Protocol):
    name: str

    def fit_predict(self, history: FlowSeries, issue_date: date) -> ForecastResult: ...
