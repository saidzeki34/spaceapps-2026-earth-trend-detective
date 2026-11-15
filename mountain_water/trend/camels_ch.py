"""Download and parse the CAMELS-CH dataset (observed daily series + static attributes).

Source: Höge et al. (2023), CAMELS-CH, https://doi.org/10.5281/zenodo.7784632
Only the observation-based daily time series are parsed. Static attributes are
read so catchments can be filtered, labelled and placed on a map.

Expected layout inside the extracted archive (verify with ``python -m
mountain_water.trend inspect`` after downloading)::

    .../timeseries/observation_based/CAMELS_CH_obs_based_<gauge_id>.csv
    .../static_attributes/CAMELS_CH_*_attributes*.csv
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

ZENODO_API = "https://zenodo.org/api/records"
# Any record of the CAMELS-CH concept works; "latest" is resolved through the API.
DEFAULT_RECORD_ID = "10354485"
DEFAULT_RAW_DIR = Path("data/raw/camels_ch")

OBS_DIR_NAME = "observation_based"
OBS_FILE_PATTERN = re.compile(r"CAMELS_CH_obs_based_(?P<gauge_id>[^_.]+)\.csv$", re.IGNORECASE)
_HEADER_UNIT = re.compile(r"^\s*(?P<name>[^(\[]+?)\s*[(\[](?P<unit>[^)\]]*)[)\]]\s*$")




@dataclass
class Provenance:
    doi: str = "10.5281/zenodo.7784632"
    record_id: str = ""
    version: str = ""
    file_name: str = ""
    checksum: str = ""
    license: str = ""
    retrieved_at: str = ""
    extra: dict = field(default_factory=dict)


def _pick_zip(files: list[dict], file_name: str | None) -> dict:
    if file_name:
        for f in files:
            if f["key"] == file_name:
                return f
        raise FileNotFoundError(f"{file_name} not in record; available: {[f['key'] for f in files]}")
    candidates = [
        f for f in files
        if f["key"].lower().endswith(".zip") and "camels_ch" in f["key"].lower() and "caravan" not in f["key"].lower()
    ]
    if not candidates:
        raise FileNotFoundError(f"No CAMELS-CH zip in record; available: {[f['key'] for f in files]}")
    return min(candidates, key=lambda f: len(f["key"]))


def _md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def download(
    raw_dir: Path = DEFAULT_RAW_DIR,
    record_id: str = DEFAULT_RECORD_ID,
    latest: bool = True,
    file_name: str | None = None,
) -> Path:
    """Download and extract CAMELS-CH from Zenodo. Idempotent; returns the extraction dir."""
    import requests

    url = f"{ZENODO_API}/{record_id}" + ("/versions/latest" if latest else "")
    meta = requests.get(url, timeout=60)
    meta.raise_for_status()
    record = meta.json()
    version = record.get("metadata", {}).get("version") or str(record["id"])
    entry = _pick_zip(record["files"], file_name)
    algo, _, expected = entry.get("checksum", "md5:").partition(":")

    target_dir = raw_dir / f"v{version}"
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / entry["key"]
    extract_dir = target_dir / "extracted"

    if not (zip_path.exists() and algo == "md5" and _md5(zip_path) == expected):
        log.info("Downloading %s (%.0f MB) from record %s", entry["key"], entry["size"] / 1e6, record["id"])
        tmp = zip_path.with_suffix(".part")
        with requests.get(entry["links"]["self"], stream=True, timeout=120) as r:
            r.raise_for_status()
            with tmp.open("wb") as fh:
                for block in r.iter_content(chunk_size=1 << 20):
                    fh.write(block)
        if algo == "md5" and _md5(tmp) != expected:
            tmp.unlink()
            raise OSError(f"Checksum mismatch for {entry['key']}")
        tmp.replace(zip_path)

    if not extract_dir.exists():
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

    prov = Provenance(
        record_id=str(record["id"]),
        version=version,
        file_name=entry["key"],
        checksum=entry.get("checksum", ""),
        license=(record.get("metadata", {}).get("license") or {}).get("id", ""),
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    (target_dir / "provenance.json").write_text(json.dumps(prov.__dict__, indent=2))
    return extract_dir




def find_dataset_root(raw_dir: Path = DEFAULT_RAW_DIR) -> Path:
    """Return the directory that contains ``timeseries/observation_based`` (newest version first)."""
    hits = sorted(raw_dir.glob(f"**/{OBS_DIR_NAME}"), key=lambda p: str(p), reverse=True)
    hits = [h for h in hits if h.is_dir()]
    if not hits:
        raise FileNotFoundError(
            f"No '{OBS_DIR_NAME}' folder under {raw_dir}. Run `python -m mountain_water.trend download` first."
        )
    return hits[0].parent.parent


def observed_files(root: Path) -> dict[str, Path]:
    files = {}
    for p in sorted((root / "timeseries" / OBS_DIR_NAME).glob("*.csv")):
        m = OBS_FILE_PATTERN.search(p.name)
        if m:
            files[m.group("gauge_id")] = p
    return files




def split_header(column: str) -> tuple[str, str | None]:
    """'discharge_vol(m3/s)' -> ('discharge_vol', 'm3/s')."""
    m = _HEADER_UNIT.match(column)
    if m:
        return m.group("name").strip(), m.group("unit").strip() or None
    return column.strip(), None


def _sniff(path: Path) -> tuple[str, str, int]:
    """Return (encoding, separator, header_row) for a CSV with optional comment lines."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open(encoding=encoding) as fh:
                lines = [fh.readline() for _ in range(20)]
            break
        except UnicodeDecodeError:
            continue
    header_row = 0
    for i, line in enumerate(lines):
        low = line.lower()
        if low.startswith(("gauge_id", "date")) or ",gauge_id" in low or ";gauge_id" in low:
            header_row = i
            break
    header = lines[header_row]
    sep = ";" if header.count(";") > header.count(",") else ","
    return encoding, sep, header_row


def read_observed_file(path: Path) -> tuple[pd.DataFrame, dict[str, str | None]]:
    encoding, sep, header_row = _sniff(path)
    df = pd.read_csv(path, sep=sep, encoding=encoding, skiprows=header_row)
    units: dict[str, str | None] = {}
    renamed = {}
    for col in df.columns:
        name, unit = split_header(str(col))
        renamed[col] = name
        units[name] = unit
    df = df.rename(columns=renamed)
    df["date"] = pd.to_datetime(df["date"])
    value_cols = [c for c in df.columns if c != "date"]
    df[value_cols] = df[value_cols].apply(pd.to_numeric, errors="coerce")
    return df, units


def load_observed(root: Path, gauge_ids: list[str] | None = None) -> tuple[pd.DataFrame, dict[str, str | None]]:
    """Wide table: gauge_id, date, discharge_vol, discharge_spec, precipitation, ...

    Missing observations stay NaN (never zero).
    """
    files = observed_files(root)
    if gauge_ids is not None:
        files = {g: files[g] for g in gauge_ids if g in files}
    frames, units = [], {}
    for gauge_id, path in files.items():
        df, u = read_observed_file(path)
        df.insert(0, "gauge_id", gauge_id)
        frames.append(df)
        units.update({k: v for k, v in u.items() if v is not None})
    if not frames:
        raise FileNotFoundError(f"No observed series found under {root}")
    obs = pd.concat(frames, ignore_index=True)
    obs["gauge_id"] = obs["gauge_id"].astype(str)
    return obs, units


def attribute_files(root: Path) -> list[Path]:
    static = root / "static_attributes"
    base = static if static.is_dir() else root
    return sorted(p for p in base.rglob("*.csv") if "attribute" in p.name.lower())


def load_attributes(root: Path) -> pd.DataFrame:
    """Merge all static attribute tables into one row per gauge_id."""
    merged: pd.DataFrame | None = None
    for path in attribute_files(root):
        encoding, sep, header_row = _sniff(path)
        df = pd.read_csv(path, sep=sep, encoding=encoding, skiprows=header_row)
        if "gauge_id" not in df.columns:
            log.warning("Skipping %s: no gauge_id column", path.name)
            continue
        df["gauge_id"] = df["gauge_id"].astype(str)
        if df["gauge_id"].duplicated().any():
            log.warning("Skipping %s: not one row per gauge (annual/time-varying table?)", path.name)
            continue
        if merged is None:
            merged = df
        else:
            new_cols = ["gauge_id"] + [c for c in df.columns if c not in merged.columns]
            merged = merged.merge(df[new_cols], on="gauge_id", how="outer")
    if merged is None:
        raise FileNotFoundError(f"No static attribute tables under {root}")
    return merged


def describe(root: Path) -> str:
    """Human-readable summary of the real dataset layout, to verify assumptions in this module."""
    files = observed_files(root)
    lines = [f"Dataset root: {root}", f"Observed series files: {len(files)}"]
    if files:
        first = next(iter(files.values()))
        df, units = read_observed_file(first)
        lines.append(f"Example file: {first.name}")
        lines.append(f"  period: {df['date'].min().date()} .. {df['date'].max().date()}  rows: {len(df)}")
        lines.append("  columns (unit): " + ", ".join(f"{k} ({units.get(k)})" for k in df.columns if k != "date"))
    for path in attribute_files(root):
        encoding, sep, header_row = _sniff(path)
        cols = pd.read_csv(path, sep=sep, encoding=encoding, skiprows=header_row, nrows=1).columns
        lines.append(f"Attributes {path.name}: {', '.join(map(str, cols))}")
    return "\n".join(lines)
