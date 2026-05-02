"""Backend factory and selection."""

from __future__ import annotations

import os
from functools import lru_cache

from global_context.storage.base import StorageBackend
from global_context.storage.json_backend import JsonBackend
from global_context.storage.sql_backend import SqlBackend


_BACKENDS = {
    "json": JsonBackend,
    "sql": SqlBackend,
    "sqlite": SqlBackend,
}


def available_backends() -> list[str]:
    names = ["json", "sql"]
    try:
        from global_context.storage.chroma_backend import ChromaBackend  # noqa: F401

        names.append("chroma")
    except Exception:
        pass

    return names


@lru_cache(maxsize=4)
def get_backend(name: str | None = None) -> StorageBackend:
    """Resolve a backend by name. Defaults to `GCTX_BACKEND` env or `sql`."""
    selected = (name or os.environ.get("GCTX_BACKEND") or "chroma").lower()

    if selected == "chroma":
        from global_context.storage.chroma_backend import ChromaBackend

        backend: StorageBackend = ChromaBackend()
    else:
        cls = _BACKENDS.get(selected)
        if cls is None:
            raise ValueError(f"Unknown backend: {selected!r}")
        backend = cls()

    backend.init()
    return backend
