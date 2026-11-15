"""SI-use disclosure for code and derived outputs; scientific values are unchanged."""

from copy import deepcopy
from functools import lru_cache
from html import escape
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _record() -> dict:
    return json.loads(Path(__file__).with_name("si-use.json").read_text(encoding="utf-8"))


def disclosure() -> dict:
    """Return independent metadata so callers cannot change the shared record."""
    return deepcopy(_record())


def write_csv(table, path: Path, **kwargs) -> None:
    """Keep ordinary CSV headers and values; append explicit SI metadata columns."""
    fields = _record()["csv_fields"]
    if set(fields) & set(table.columns):
        raise ValueError("CSV already contains reserved SI metadata columns.")
    table.assign(**fields).to_csv(path, **kwargs)
    path.with_suffix(path.suffix + ".metadata.json").write_text(
        json.dumps({"file": path.name, "si_assistance": disclosure()}, indent=2), encoding="utf-8")


def write_figure_html(figure, path: Path) -> None:
    """Attach visible code-use credit and metadata to standalone data reports."""
    original_meta = figure.layout.meta
    try:
        figure.layout.meta = {"source_metadata": original_meta, "si_assistance": disclosure()}
        html = figure.to_html(include_plotlyjs="cdn")
    finally:
        figure.layout.meta = original_meta
    notice = '<p id="si-disclosure">' + escape(_record()["description"]) + '</p>'
    path.write_text(html.replace("</body>", notice + "</body>"), encoding="utf-8")
