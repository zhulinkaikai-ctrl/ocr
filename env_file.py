from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | Path = ".env") -> bool:
    """读取简单 KEY=VALUE 文件，不覆盖已存在的系统环境变量。"""
    env_path = Path(path)
    if not env_path.exists():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")
    return True
