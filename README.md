# global-context

Persistent context store for Claude Code. Saves conversations, project facts,
and notes to a local backend (SQL by default, JSON or Chroma optional). Ships
with a Claude Code skill and CLI (`gctx`) for save / list / search workflows.

## Install

```bash
pip install global-context
```

A `.pth` file fires `ensure_bootstrapped()` on first Python startup — storage
dirs are created and the bundled `SKILL.md` is installed under
`~/.claude/skills/global-context/`.

## Quick start

```bash
gctx init
gctx save --title "auth notes" --content "OAuth flow uses PKCE" --kind note
gctx search "oauth"
gctx sessions sync          # ingest all Claude Code session logs
gctx sessions search "kafka"
```

## Backends

Selected via `GCTX_BACKEND=sql|json|chroma` (or `--backend`).

- `sql` — SQLAlchemy 2.x over SQLite (default, durable).
- `json` — single-file JSON store (no extra deps, good for sync/share).
- `chroma` — ChromaDB vector store for semantic search.

Storage path overridable with `GCTX_HOME`.

## Library

```python
from global_context import get_backend, MemoryEntry

backend = get_backend("sql")
backend.save_entry(MemoryEntry(title="t", content="c", project="repo"))
results = backend.search("c")
```

## License

MIT
