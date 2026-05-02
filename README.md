# global-context

Local-first AI memory. Verbatim storage, semantic search, pluggable vector backend, temporal knowledge graph. Zero cloud calls.

## Install

```bash
pip install -e .
pip install -e ".[mcp]"
```

## Concepts

- **Entry** — verbatim text unit (smallest indexable item)
- **Topic** — subject grouping inside a scope
- **Scope** — top-level namespace (project, person, agent)

Search can be scoped (`scope`, `topic`) instead of running flat.

## Quickstart (CLI)

```bash
gctx init
gctx add "switched to GraphQL because REST pagination was painful" --scope myapp --topic decisions
gctx mine ~/projects/myapp --scope myapp
gctx mine ~/.claude/projects --mode transcripts --scope myapp
gctx search "why GraphQL"
gctx warmup
gctx stats
```

## Quickstart (Python)

```python
from global_context import ContextStore

store = ContextStore("~/.global-context")
store.add("token expiry uses < not <=", scope="auth-bug", topic="fix")
hits = store.search("token expiry", k=5)
for h in hits:
    print(h.score, h.entry.content)
```

## Knowledge graph

```python
store.graph.add_node("user:alice", kind="person", name="Alice")
store.graph.add_node("proj:api", kind="project", name="API")
edge = store.graph.add_edge("user:alice", "proj:api", relation="owns")
store.graph.neighbors("user:alice", relation="owns")
store.graph.invalidate_edge(edge)
store.graph.timeline("user:alice")
```

## MCP server

```bash
python -m global_context.mcp.server
```

Tools: `add_entry`, `search_entries`, `warmup`, `stats`, `list_scopes`, `delete_entry`, `graph_add_node`, `graph_add_edge`, `graph_neighbors`, `graph_timeline`.

## Claude Code hooks

Cross-session memory: every session writes the transcript to the store, every new session reads relevant entries back as additional context. Drop the snippet from [global_context/hooks/example_settings.json](global_context/hooks/example_settings.json) into `~/.claude/settings.json`.

| Event | Command | Effect |
|-------|---------|--------|
| `SessionStart` | `python -m global_context.hooks.recall SessionStart` | injects warmup top-k as context |
| `UserPromptSubmit` | `python -m global_context.hooks.recall UserPromptSubmit` | injects entries semantically matching the prompt |
| `Stop` | `python -m global_context.hooks.autosave` | saves the transcript |
| `PreCompact` | `python -m global_context.hooks.autosave` | saves before compaction |

Env vars:
- `GLOBAL_CONTEXT_HOME` — storage root (default `~/.global-context`)
- `GLOBAL_CONTEXT_SCOPE` — default scope for save / filter for recall
- `GLOBAL_CONTEXT_RECALL_K` — top-k entries injected (default 8 on session, 5 on prompt)
- `CLAUDE_TRANSCRIPT_PATH` — transcript path fallback

## Backends

Default: ChromaDB (local persistent). Swap by passing any `VectorBackend` to `ContextStore(backend=...)`.

## License

MIT
