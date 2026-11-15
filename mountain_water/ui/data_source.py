"""The single place where the screens ask for values to draw.

No data or calculation module is connected yet, so every request answers
"nothing available" and the screens show an honest empty state.

When the team's sections are ready, connect them here (through
``mountain_water.shared.assessment``) and return a :class:`Series`. The view
and chart files do not need to change.

For judging the layout before data exists there is an optional *sample
preview*. It draws made-up smooth shapes that are clearly marked as samples,
carry no units or magnitudes, and are never mixed with real values.
"""

from __future__ import annotations

import math
import random
import zlib
from dataclasses import dataclass

KIND_OBSERVED = "observed"
KIND_PREDICTED = "predicted"
KIND_SAMPLE = "sample"

#: Set to True by the integration work once real results can be supplied.
CONNECTED = False


@dataclass(frozen=True)
class Series:
    """Values of one variable for one year of one river."""

    variable_id: str
    year: int
    method: str  # "monthly" (12 values) or "native" (the dataset's finest step)
    values: tuple[float | None, ...]  # None marks a missing value; it is never zero
    kind: str  # observed, predicted or sample
    unit: str | None = None


def get_series(
    river_id: str,
    variable_id: str,
    year: int,
    method: str,
    *,
    predicted: bool = False,
    sample_preview: bool = False,
) -> Series | None:
    """Return the values to plot, or None when nothing is available."""
    if CONNECTED:  # pragma: no cover - integration point for the team's sections
        raise NotImplementedError("Connect mountain_water.shared.assessment here.")
    if sample_preview:
        return _sample_series(river_id, variable_id, year, method)
    return None


def _sample_series(river_id: str, variable_id: str, year: int, method: str) -> Series:
    """A made-up seasonal shape between 0 and 1, stable for the same request."""
    seed = zlib.crc32(f"{river_id}|{variable_id}|{year}".encode())
    rng = random.Random(seed)
    count = 12 if method == "monthly" else 365
    peak = rng.uniform(0.25, 0.75)
    wobble = 0.03 if method == "monthly" else 0.05
    values = []
    for i in range(count):
        position = (i + 0.5) / count
        season = 0.5 + 0.38 * math.cos(2 * math.pi * (position - peak))
        values.append(min(1.0, max(0.0, season + rng.uniform(-wobble, wobble))))
    return Series(variable_id, year, method, tuple(values), KIND_SAMPLE, unit=None)
