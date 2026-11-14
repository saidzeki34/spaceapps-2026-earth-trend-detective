"""Local configuration only. Never include credentials in results or cache keys."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from mountain_water.contracts import Outlet

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    cache_dir: Path
    nve_api_key: str = ""
    earth_engine_project: str = ""
    camels_ch_dir: Path | None = None
    timeout_seconds: float = 30
    cache_ttl_hours: float = 24

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env", override=False)
        archive = os.getenv("CAMELS_CH_DIR", "")
        return cls(Path(os.getenv("WATER_CACHE_DIR", ROOT / "data/cache")),
                   os.getenv("NVE_API_KEY", ""), os.getenv("EARTH_ENGINE_PROJECT", ""),
                   Path(archive) if archive else None)


def load_outlets() -> list[Outlet]:
    rows = json.loads((ROOT / "config/stations.json").read_text(encoding="utf-8"))
    outlets = []
    for row in rows:
        geometry_path = row.pop("geometry_path", None)
        if geometry_path:
            row["geometry"] = json.loads((ROOT / geometry_path).read_text(encoding="utf-8"))
        outlets.append(Outlet(**row))
    return outlets
