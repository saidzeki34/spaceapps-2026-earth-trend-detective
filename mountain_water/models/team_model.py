"""Said/Nikola model extension point. No equation or coefficients have been supplied.

Implement fit_predict only after documenting units, water-balance boundary,
storage, routing, parameters, weather scenarios and management assumptions.
Do not use observed future drivers. Use models.validation before comparison.
"""
from mountain_water.contracts import ForecastResult


class TeamModel:
    name = "team_equation"

    def fit_predict(self, history, issue_date):
        return ForecastResult("unavailable", str(issue_date), model=self.name,
            assumptions=["The team's equation, parameters and required future driver scenarios have not been supplied.",
                         "No formula or result is invented. Use the seasonal baseline for comparison."])
