from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from global_context.core.store import ContextStore


def _default_root() -> Path:
    env = os.environ.get("GLOBAL_CONTEXT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".global-context"


def build_server(root: Optional[Path] = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "mcp extra not installed. Install with: pip install global-context[mcp]"
        ) from exc

    server = FastMCP("global-context")
    store = ContextStore(root or _default_root())

    @server.tool()
    def add_entry(content: str, scope: str, topic: str = "general", source: Optional[str] = None) -> dict:
        entry = store.add(content=content, scope=scope, topic=topic, source=source)
        return {"id": entry.id, "scope": entry.scope, "topic": entry.topic}

    @server.tool()
    def search_entries(
        query: str,
        k: int = 5,
        scope: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> list[dict]:
        hits = store.search(query, k=k, scope=scope, topic=topic)
        return [
            {
                "id": h.entry.id,
                "scope": h.entry.scope,
                "topic": h.entry.topic,
                "content": h.entry.content,
                "source": h.entry.source,
                "score": h.score,
            }
            for h in hits
        ]

    @server.tool()
    def warmup(query: str = "recent context", k: int = 10) -> list[dict]:
        hits = store.warmup(query, k=k)
        return [
            {
                "scope": h.entry.scope,
                "topic": h.entry.topic,
                "content": h.entry.content,
                "score": h.score,
            }
            for h in hits
        ]

    @server.tool()
    def stats() -> dict:
        return store.stats()

    @server.tool()
    def list_scopes() -> list[str]:
        return store.backend.list_scopes()

    @server.tool()
    def delete_entry(entry_id: str) -> dict:
        store.backend.delete([entry_id])
        return {"deleted": entry_id}

    @server.tool()
    def graph_add_node(node_id: str, kind: str, name: str) -> dict:
        store.graph.add_node(node_id, kind, name)
        return {"id": node_id}

    @server.tool()
    def graph_add_edge(src: str, dst: str, relation: str) -> dict:
        edge_id = store.graph.add_edge(src, dst, relation)
        return {"edge_id": edge_id}

    @server.tool()
    def graph_neighbors(node_id: str, relation: Optional[str] = None) -> list[dict]:
        return store.graph.neighbors(node_id, relation=relation)

    @server.tool()
    def graph_timeline(node_id: str) -> list[dict]:
        return store.graph.timeline(node_id)

    return server


def run(root: Optional[Path] = None) -> None:
    server = build_server(root)
    server.run()


if __name__ == "__main__":
    run()
