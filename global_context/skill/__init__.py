"""Bundled Claude Code skill."""

from __future__ import annotations

from pathlib import Path


def bundled_skill_path() -> Path:
    return Path(__file__).resolve().parent / "SKILL.md"
