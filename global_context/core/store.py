from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from global_context.backends.base import SearchHit, VectorBackend
from global_context.backends.chroma import ChromaBackend
from global_context.core.models import Entry
from global_context.graph.kg import KnowledgeGraph


class ContextStore:
    def __init__(
        self,
        root: str | Path,
        backend: Optional[VectorBackend] = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.backend: VectorBackend = backend or ChromaBackend(self.root / "vectors")
        self.graph = KnowledgeGraph(self.root / "graph.sqlite")

    def add(
        self,
        content: str,
        scope: str,
        topic: str = "general",
        source: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Entry:
        entry = Entry(
            scope=scope,
            topic=topic,
            content=content,
            source=source,
            metadata=metadata or {},
        )
        self.backend.upsert([entry])
        return entry

    def add_many(self, entries: Iterable[Entry]) -> int:
        items = list(entries)
        if not items:
            return 0
        self.backend.upsert(items)
        return len(items)

    def search(
        self,
        query: str,
        k: int = 5,
        scope: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> list[SearchHit]:
        return self.backend.search(query, k=k, scope=scope, topic=topic)

    def warmup(self, query: str = "recent context", k: int = 10) -> list[SearchHit]:
        return self.search(query, k=k)

    def stats(self) -> dict:
        return {
            "root": str(self.root),
            "backend": type(self.backend).__name__,
            "entries": self.backend.count(),
            "scopes": self.backend.list_scopes(),
        }

    def close(self) -> None:
        self.backend.close()
        self.graph.close()
