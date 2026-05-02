---
name: global-context
description: ALWAYS invoke at the start of every turn to load relevant past context (Claude session history, project facts, notes). Run `gctx live "<user prompt>"` via Bash and treat its `<global-context>...</global-context>` block as authoritative recall before answering.
---

# global-context skill

Persistent context store for Claude Code. Indexes every past Claude session
(`~/.claude/projects/**/*.jsonl`) plus user notes into a local backend.

## What to do when invoked

1. Read user's most recent prompt.
2. Run via Bash:
   ```bash
   gctx live "<short summary of user prompt>" --limit 5
   ```
3. Read `<global-context>...</global-context>` block.
4. **ALWAYS** show user a visible summary block at top of your reply:
   ```
   📚 Contexto recuperado:
   - <bullet 1>
   - <bullet 2>
   ```
   If empty, write `📚 Contexto: nenhum match relevante.`
5. Then answer normally below.

Never skip — even on greetings. User must see this block every turn.

## Save pattern

When the user shares durable knowledge (decisions, project facts, preferences):

```bash
gctx save --project "$REPO" --kind project --title "..." --content "..."
```

Skip secrets, ephemeral state, and content already in the codebase.

## CLI surface

```bash
gctx live "query"                  # recall (use this every turn)
gctx search "query" [--kind K] [--project P] [--limit N]
gctx save --title T --content C [--project P] [--kind note|project|memory]
gctx list [--kind K] [--project P]
gctx show <entry-id>
gctx delete <entry-id>

gctx sessions list                 # discover Claude session logs on disk
gctx sessions sync [--force]       # ingest all sessions into storage
gctx sessions search "query"

gctx skill install                 # reinstall bundled SKILL.md
gctx hook install [--apply]        # merge hooks into ~/.claude/settings.json
gctx status                        # backend, paths, counts
```

Backend: `GCTX_BACKEND=sql|json|chroma`. Storage path: `GCTX_HOME`.
