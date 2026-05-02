from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

from global_context.core.models import Entry
from global_context.core.store import ContextStore

_TEXT_EXT = {
    ".md", ".txt", ".rst", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".kt", ".rb", ".php", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".swift", ".sh", ".yml", ".yaml",
    ".toml", ".json", ".sql", ".html", ".css", ".scss",
}

_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea", ".vscode"}


def _walk(root: Path, exts: set[str]) -> Iterator[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in exts:
            yield path


def _chunk(text: str, size: int = 1500, overlap: int = 200) -> Iterable[str]:
    if len(text) <= size:
        yield text
        return
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        yield text[start:end]
        if end == len(text):
            return
        start = end - overlap


def mine_files(
    store: ContextStore,
    root: str | Path,
    scope: str,
    topic: str = "files",
    extensions: Iterable[str] | None = None,
    chunk_size: int = 1500,
) -> int:
    base = Path(root).expanduser().resolve()
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in (extensions or _TEXT_EXT)}
    entries: list[Entry] = []
    for path in _walk(base, exts):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not text.strip():
            continue
        rel = str(path.relative_to(base))
        for i, chunk in enumerate(_chunk(text, size=chunk_size)):
            entries.append(
                Entry(
                    scope=scope,
                    topic=topic,
                    content=chunk,
                    source=rel,
                    metadata={"chunk": i, "path": str(path)},
                )
            )
    return store.add_many(entries)
