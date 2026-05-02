"""ChromaDB vector backend for semantic search."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_ENABLED", "False")

import chromadb
from chromadb.config import Settings

for _name in ("chromadb.telemetry", "chromadb.telemetry.product.posthog", "posthog"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)

from global_context.core.models import (
    Conversation,
    EntryKind,
    MemoryEntry,
    SearchResult,
)
from global_context.paths import chroma_dir
from global_context.storage.base import StorageBackend


_ENTRIES = "gctx_entries"
_CONVERSATIONS = "gctx_conversations"


class ChromaBackend(StorageBackend):
    """Vector store backed by ChromaDB persistent client."""

    name = "chroma"

    def __init__(self, persist_dir: str | None = None) -> None:
        path = persist_dir or str(chroma_dir())
        self.client = chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._entries = None
        self._conversations = None

    def init(self) -> None:
        self._entries = self.client.get_or_create_collection(_ENTRIES)
        self._conversations = self.client.get_or_create_collection(_CONVERSATIONS)

    def _ensure(self) -> None:
        if self._entries is None or self._conversations is None:
            self.init()

    def save_entry(self, entry: MemoryEntry) -> MemoryEntry:
        self._ensure()
        document = f"{entry.title}\n{entry.content}".strip()
        metadata = _entry_metadata(entry)
        self._entries.upsert(
            ids=[entry.id],
            documents=[document or entry.id],
            metadatas=[metadata],
        )

        return entry

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        self._ensure()
        result = self._entries.get(ids=[entry_id])
        if not result["ids"]:
            return None

        return _entry_from_chroma(
            entry_id=result["ids"][0],
            document=result["documents"][0],
            metadata=result["metadatas"][0],
        )

    def delete_entry(self, entry_id: str) -> bool:
        self._ensure()
        existing = self._entries.get(ids=[entry_id])
        if not existing["ids"]:
            return False

        self._entries.delete(ids=[entry_id])
        return True

    def list_entries(
        self,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        self._ensure()
        where = _build_where(kind=kind, project=project)
        result = self._entries.get(where=where or None, limit=limit)
        return [
            _entry_from_chroma(eid, doc, meta)
            for eid, doc, meta in zip(
                result["ids"], result["documents"], result["metadatas"], strict=False
            )
        ]

    def search(
        self,
        query: str,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        self._ensure()
        if not query.strip():
            return []

        where = _build_where(kind=kind, project=project)
        result = self._entries.query(
            query_texts=[query],
            n_results=limit,
            where=where or None,
        )
        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        distances = result.get("distances", [[0.0] * len(ids)])[0]

        out: list[SearchResult] = []
        for entry_id, doc, meta, dist in zip(ids, docs, metas, distances, strict=False):
            entry = _entry_from_chroma(entry_id, doc, meta)
            score = 1.0 / (1.0 + float(dist))
            out.append(SearchResult(entry=entry, score=score))

        return out

    def save_conversation(self, conversation: Conversation) -> Conversation:
        self._ensure()
        document = conversation.as_text() or conversation.id
        metadata = {
            "project": conversation.project or "",
            "title": conversation.title or "",
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "payload": conversation.model_dump_json(),
        }
        self._conversations.upsert(
            ids=[conversation.id],
            documents=[document],
            metadatas=[metadata],
        )

        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        self._ensure()
        result = self._conversations.get(ids=[conversation_id])
        if not result["ids"]:
            return None

        payload = result["metadatas"][0]["payload"]
        return Conversation.model_validate_json(payload)

    def list_conversations(
        self, project: str | None = None, limit: int = 50
    ) -> list[Conversation]:
        self._ensure()
        where = {"project": project} if project else None
        result = self._conversations.get(where=where, limit=limit)
        return [Conversation.model_validate_json(m["payload"]) for m in result["metadatas"]]


def _entry_metadata(entry: MemoryEntry) -> dict[str, Any]:
    return {
        "kind": entry.kind.value,
        "project": entry.project or "",
        "title": entry.title,
        "tags": ",".join(entry.tags),
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def _entry_from_chroma(entry_id: str, document: str, metadata: dict[str, Any]) -> MemoryEntry:
    title = metadata.get("title") or ""
    content = document
    if title and document.startswith(title):
        content = document[len(title):].lstrip("\n")

    tags_raw = metadata.get("tags") or ""
    tags = [t for t in tags_raw.split(",") if t]

    return MemoryEntry(
        id=entry_id,
        kind=EntryKind(metadata.get("kind", EntryKind.NOTE.value)),
        project=metadata.get("project") or None,
        title=title,
        content=content,
        tags=tags,
        created_at=_parse_dt(metadata.get("created_at")),
        updated_at=_parse_dt(metadata.get("updated_at")),
    )


def _parse_dt(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()

    return datetime.fromisoformat(raw)


def _build_where(kind: EntryKind | None, project: str | None) -> dict[str, Any]:
    clauses: dict[str, Any] = {}
    if kind is not None:
        clauses["kind"] = kind.value
    if project is not None:
        clauses["project"] = project

    return clauses
