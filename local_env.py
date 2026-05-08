"""Load local environment variables from config/local.env."""

from __future__ import annotations

import os
from pathlib import Path


def default_local_env_path() -> Path:
    return Path(__file__).resolve().parent / "config" / "local.env"


def load_local_env(env_path: str | Path | None = None, override: bool = False) -> dict[str, str]:
    path = Path(env_path) if env_path is not None else default_local_env_path()
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export ") :].strip()
            value = value.strip().strip('"').strip("'")
            loaded[key] = value
            if override or key not in os.environ:
                os.environ[key] = value
    except OSError:
        return {}
    return loaded
