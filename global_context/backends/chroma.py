from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from global_context.backends.base import SearchHit, VectorBackend
from global_context.core.models import Entry

_COLLECTION = "global_context_entries"


class ChromaBackend(VectorBackend):
    def __init__(self, path: str | Path, collection: str = _COLLECTION) -> None:
        import chromadb
        from chromadb.config import Settings

        self.path = Path(path).expanduser().resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.path),
            settings=Settings(anonymized_telemetry=False, allow_reset=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, entries: Iterable[Entry]) -> None:
        items = list(entries)
        if not items:
            return
        self._collection.upsert(
            ids=[e.id for e in items],
            documents=[e.content for e in items],
            metadatas=[
                {
                    "scope": e.scope,
                    "topic": e.topic,
                    "source": e.source or "",
                    "created_at": e.created_at.isoformat(),
                    "extra": json.dumps(e.metadata, default=str),
                }
                for e in items
            ],
        )

    def search(
        self,
        query: str,
        k: int = 5,
        scope: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> list[SearchHit]:
        where: dict = {}
        if scope and topic:
            where = {"$and": [{"scope": scope}, {"topic": topic}]}
        elif scope:
            where = {"scope": scope}
        elif topic:
            where = {"topic": topic}

        result = self._collection.query(
            query_texts=[query],
            n_results=k,
            where=where or None,
        )
        hits: list[SearchHit] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i, eid in enumerate(ids):
            meta = metas[i] or {}
            try:
                extra = json.loads(meta.get("extra") or "{}")
            except json.JSONDecodeError:
                extra = {}
            try:
                created_dt = datetime.fromisoformat(meta.get("created_at") or "")
            except ValueError:
                created_dt = datetime.now(timezone.utc)
            entry = Entry(
                id=eid,
                scope=meta.get("scope", ""),
                topic=meta.get("topic", ""),
                content=docs[i],
                source=meta.get("source") or None,
                created_at=created_dt,
                metadata=extra,
            )
            score = 1.0 - float(dists[i]) if dists else 0.0
            hits.append(SearchHit(entry=entry, score=score))
        return hits

    def delete(self, entry_ids: Iterable[str]) -> None:
        ids = list(entry_ids)
        if ids:
            self._collection.delete(ids=ids)

    def count(self) -> int:
        return int(self._collection.count())

    def list_scopes(self) -> list[str]:
        result = self._collection.get(include=["metadatas"])
        scopes = {(m or {}).get("scope", "") for m in (result.get("metadatas") or [])}
        return sorted(s for s in scopes if s)

    def close(self) -> None:
        return None
