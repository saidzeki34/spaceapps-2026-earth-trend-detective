"""JSON cache only: no pickle, no credentials, atomic replacement."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from mountain_water.contracts import utc_now


def cache_key(**scientific_identity) -> str:
    payload = json.dumps(scientific_identity, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class JsonCache:
    def __init__(self, directory: Path, ttl_hours=24):
        self.directory = directory
        self.ttl_hours = ttl_hours

    def get(self, key):
        path = self.directory / f"{key}.json"
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            age = datetime.now(timezone.utc) - datetime.fromisoformat(obj["saved_at"])
            return obj["payload"] if age.total_seconds() < self.ttl_hours * 3600 else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, key, payload):
        self.directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                         dir=self.directory, delete=False) as stream:
            path = Path(stream.name)
            json.dump({"saved_at": utc_now(), "payload": payload}, stream, allow_nan=False)
        os.replace(path, self.directory / f"{key}.json")
