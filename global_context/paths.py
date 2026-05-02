"""Filesystem paths for storage, skills, and hooks."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "global-context"
APP_AUTHOR = "fernandocelmer"


def data_dir() -> Path:
    """Return base data directory, honoring `GCTX_HOME` override."""
    override = os.environ.get("GCTX_HOME")
    if override:
        return Path(override).expanduser().resolve()

    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def storage_dir() -> Path:
    return data_dir() / "storage"


def sqlite_path() -> Path:
    return storage_dir() / "context.db"


def json_path() -> Path:
    return storage_dir() / "context.json"


def chroma_dir() -> Path:
    return storage_dir() / "chroma"


def claude_dir() -> Path:
    return Path.home() / ".claude"


def claude_skills_dir() -> Path:
    return claude_dir() / "skills" / "global-context"


def ensure_dirs() -> None:
    for path in (data_dir(), storage_dir(), chroma_dir()):
        path.mkdir(parents=True, exist_ok=True)
