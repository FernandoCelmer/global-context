from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from global_context.core.models import Entry
from global_context.core.store import ContextStore


def _iter_jsonl(path: Path) -> Iterator[dict]:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _extract_text(payload: dict) -> str:
    msg = payload.get("message") or payload
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                t = part.get("text") or part.get("content") or ""
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(p for p in parts if p)
    return ""


def mine_transcripts(
    store: ContextStore,
    root: str | Path,
    scope: str,
    topic: str = "conversations",
) -> int:
    base = Path(root).expanduser().resolve()
    paths = list(base.rglob("*.jsonl")) if base.is_dir() else [base]
    entries: list[Entry] = []
    for path in paths:
        for record in _iter_jsonl(path):
            text = _extract_text(record)
            if not text.strip():
                continue
            role = (record.get("message") or {}).get("role") or record.get("role") or "unknown"
            entries.append(
                Entry(
                    scope=scope,
                    topic=topic,
                    content=text,
                    source=str(path),
                    metadata={"role": role, "session": path.stem},
                )
            )
    return store.add_many(entries)
