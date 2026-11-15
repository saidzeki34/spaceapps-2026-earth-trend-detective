"""What the person has selected on screen, as sent by the web page with each request.

The page itself remembers the selection (in the address bar). The server is
stateless: every request carries the full selection and is checked here.
"""

from __future__ import annotations

from dataclasses import dataclass

from mountain_water.ui import controls

_ASSESSMENT_IDS = {a.id for a in controls.ASSESSMENTS}
_METHOD_IDS = {m["id"] for m in controls.METHODS}


@dataclass(frozen=True)
class Selection:
    river: str
    year: int | None  # None: let the server pick the latest complete year
    method: str
    occupation: str
    variables: tuple[str, ...]
    sections: tuple[str, ...]
    usual: bool  # also draw the usual year for comparison

    @classmethod
    def from_query(cls, query: dict[str, list[str]]) -> Selection:
        """Read a selection from the address parameters, dropping anything unknown."""

        def first(name: str) -> str:
            return (query.get(name) or [""])[0]

        def many(name: str) -> list[str]:
            return [part for part in first(name).split(",") if part]

        year = first("year")
        method = first("method")
        occupation = first("occupation")
        return cls(
            river=first("river"),
            year=int(year) if year.lstrip("-").isdigit() else None,
            method=method if method in _METHOD_IDS else controls.METHOD_MONTHLY,
            occupation=occupation if occupation in controls.OCCUPATIONS_BY_ID else controls.OCCUPATIONS[0].id,
            variables=tuple(v for v in many("variables") if v in controls.VARIABLES_BY_ID),
            sections=tuple(s for s in many("sections") if s in _ASSESSMENT_IDS),
            usual=first("usual") == "1",
        )
