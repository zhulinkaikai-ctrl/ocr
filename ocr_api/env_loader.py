from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: str | Path | None = None) -> bool:
    """Load simple KEY=VALUE environment files without overriding existing values.

    Priority when no path is provided:
    1. ENV_FILE environment variable
    2. .env
    """
    env_path = _resolve_env_path(path)
    if env_path is None or not env_path.exists():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if not name or name in os.environ:
            continue
        os.environ[name] = value.strip().strip('"').strip("'")
    return True


def _resolve_env_path(path: str | Path | None) -> Path | None:
    if path is not None:
        return _absolute_path(path)

    configured = os.environ.get("ENV_FILE")
    if configured:
        return _absolute_path(configured)

    default_env = PROJECT_ROOT / ".env"
    return default_env if default_env.exists() else None


def _absolute_path(path: str | Path) -> Path:
    env_path = Path(path)
    if env_path.is_absolute():
        return env_path
    return PROJECT_ROOT / env_path
