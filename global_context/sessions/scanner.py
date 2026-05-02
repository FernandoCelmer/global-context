"""Locate Claude Code session log files on disk."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from global_context.paths import claude_dir


@dataclass(frozen=True)
class SessionFile:
    session_id: str
    project_slug: str
    project_path: str
    path: Path
    size: int
    modified_at: datetime


def projects_root() -> Path:
    return claude_dir() / "projects"


def _slug_to_path(slug: str) -> str:
    return slug.replace("-", "/", 1).replace("-", "/")


def discover_sessions(root: Path | None = None) -> list[SessionFile]:
    """Return all `*.jsonl` session files under the Claude projects root."""
    base = root or projects_root()
    if not base.exists():
        return []

    sessions: list[SessionFile] = []
    for jsonl in base.glob("*/*.jsonl"):
        if jsonl.parent == base:
            continue

        stat = jsonl.stat()
        slug = jsonl.parent.name
        sessions.append(
            SessionFile(
                session_id=jsonl.stem,
                project_slug=slug,
                project_path=_slug_to_path(slug),
                path=jsonl,
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )

    sessions.sort(key=lambda s: s.modified_at, reverse=True)
    return sessions
