"""Zero-config bootstrap. Runs once on first import."""

from __future__ import annotations

import os
from pathlib import Path

from global_context.paths import (
    claude_skills_dir,
    data_dir,
    ensure_dirs,
)


_FLAG_NAME = ".bootstrapped"


def ensure_bootstrapped() -> None:
    """Create dirs and install bundled Claude skill once per machine."""
    if os.environ.get("GCTX_NO_BOOTSTRAP"):
        return

    ensure_dirs()
    flag = data_dir() / _FLAG_NAME
    if flag.exists():
        return

    try:
        install_skill()
    except Exception:
        pass

    flag.write_text("ok", encoding="utf-8")


def install_skill(target: Path | None = None) -> Path:
    """Copy bundled SKILL.md into the user's Claude skills directory."""
    from global_context.skill import bundled_skill_path

    src = bundled_skill_path()
    dest_dir = target or claude_skills_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "SKILL.md"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest
