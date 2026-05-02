"""JSON-file storage backend. Fallback when SQL/Chroma unavailable."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from global_context.core.models import (
    Conversation,
    EntryKind,
    MemoryEntry,
    SearchResult,
)
from global_context.paths import json_path
from global_context.storage.base import StorageBackend


class JsonBackend(StorageBackend):
    """Simple file-backed store. Good for single-user, no extra services."""

    name = "json"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or json_path()
        self._lock = threading.Lock()
        self._cache: dict[str, dict] = {"entries": {}, "conversations": {}}

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._flush()
        else:
            self._load()

    def _load(self) -> None:
        with self.path.open("r", encoding="utf-8") as fh:
            self._cache = json.load(fh)

        self._cache.setdefault("entries", {})
        self._cache.setdefault("conversations", {})

    def _flush(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(self._cache, fh, indent=2, default=_json_default)

        tmp.replace(self.path)

    def save_entry(self, entry: MemoryEntry) -> MemoryEntry:
        with self._lock:
            self._cache["entries"][entry.id] = entry.model_dump(mode="json")
            self._flush()

        return entry

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        raw = self._cache["entries"].get(entry_id)
        return MemoryEntry.model_validate(raw) if raw else None

    def delete_entry(self, entry_id: str) -> bool:
        with self._lock:
            removed = self._cache["entries"].pop(entry_id, None) is not None
            if removed:
                self._flush()

        return removed

    def list_entries(
        self,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        items = [MemoryEntry.model_validate(v) for v in self._cache["entries"].values()]
        if kind is not None:
            items = [e for e in items if e.kind == kind]
        if project is not None:
            items = [e for e in items if e.project == project]

        items.sort(key=lambda e: e.updated_at, reverse=True)
        return items[:limit]

    def search(
        self,
        query: str,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        needle = query.lower().strip()
        if not needle:
            return []

        results: list[SearchResult] = []
        for entry in self.list_entries(kind=kind, project=project, limit=10_000):
            haystack = f"{entry.title}\n{entry.content}\n{' '.join(entry.tags)}".lower()
            score = _score(haystack, needle)
            if score > 0:
                results.append(SearchResult(entry=entry, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def save_conversation(self, conversation: Conversation) -> Conversation:
        with self._lock:
            self._cache["conversations"][conversation.id] = conversation.model_dump(mode="json")
            self._flush()

        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        raw = self._cache["conversations"].get(conversation_id)
        return Conversation.model_validate(raw) if raw else None

    def list_conversations(
        self, project: str | None = None, limit: int = 50
    ) -> list[Conversation]:
        items = [Conversation.model_validate(v) for v in self._cache["conversations"].values()]
        if project is not None:
            items = [c for c in items if c.project == project]

        items.sort(key=lambda c: c.updated_at, reverse=True)
        return items[:limit]


def _score(haystack: str, needle: str) -> float:
    if needle in haystack:
        base = haystack.count(needle)
        return float(base) + 1.0 / (1 + len(haystack))

    tokens = [t for t in needle.split() if t]
    hits = sum(1 for t in tokens if t in haystack)
    return hits / max(len(tokens), 1)


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()

    raise TypeError(f"Unserializable type: {type(value).__name__}")
