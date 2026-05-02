"""Top-level Typer application."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from global_context.bootstrap import ensure_bootstrapped, install_skill
from global_context.core.models import (
    Conversation,
    EntryKind,
    MemoryEntry,
)
from global_context.paths import (
    claude_dir,
    claude_skills_dir,
    data_dir,
    storage_dir,
)
from global_context.sessions.importer import sync_sessions
from global_context.sessions.scanner import discover_sessions
from global_context.storage.factory import available_backends, get_backend


app = typer.Typer(
    name="gctx",
    help="Persistent context store for Claude Code.",
    no_args_is_help=True,
)
convo_app = typer.Typer(name="convo", help="Manage stored conversations.")
skill_app = typer.Typer(name="skill", help="Manage the bundled Claude Code skill.")
hook_app = typer.Typer(name="hook", help="Manage Claude Code hooks.")
sessions_app = typer.Typer(name="sessions", help="Ingest Claude Code session logs.")

app.add_typer(convo_app)
app.add_typer(skill_app)
app.add_typer(hook_app)
app.add_typer(sessions_app)

console = Console()


BackendOpt = Annotated[
    Optional[str],
    typer.Option("--backend", "-b", help="Storage backend (json|sql|chroma)."),
]


@app.command()
def init(backend: BackendOpt = None) -> None:
    """Initialize storage and bundled skill."""
    ensure_bootstrapped()
    backend_obj = get_backend(backend)
    console.print(f"[green]Initialized[/green] backend=[bold]{backend_obj.name}[/bold]")
    console.print(f"data dir: {data_dir()}")


@app.command()
def status(backend: BackendOpt = None) -> None:
    """Show storage status and counts."""
    backend_obj = get_backend(backend)
    entries = backend_obj.list_entries(limit=10_000)
    convos = backend_obj.list_conversations(limit=10_000)

    table = Table(title="global-context status")
    table.add_column("key")
    table.add_column("value")
    table.add_row("backend", backend_obj.name)
    table.add_row("data_dir", str(data_dir()))
    table.add_row("storage_dir", str(storage_dir()))
    table.add_row("entries", str(len(entries)))
    table.add_row("conversations", str(len(convos)))
    table.add_row("available", ", ".join(available_backends()))
    console.print(table)


@app.command()
def save(
    title: str = typer.Option(..., "--title", "-t"),
    content: str = typer.Option(..., "--content", "-c"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    kind: EntryKind = typer.Option(EntryKind.NOTE, "--kind", "-k"),
    tag: list[str] = typer.Option([], "--tag"),
    backend: BackendOpt = None,
) -> None:
    """Save a memory entry."""
    entry = MemoryEntry(
        title=title,
        content=content,
        project=project,
        kind=kind,
        tags=tag,
    )
    get_backend(backend).save_entry(entry)
    console.print(f"[green]saved[/green] {entry.id}")


@app.command(name="list")
def list_cmd(
    kind: Optional[EntryKind] = typer.Option(None, "--kind", "-k"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    limit: int = typer.Option(20, "--limit", "-n"),
    backend: BackendOpt = None,
) -> None:
    """List stored entries."""
    rows = get_backend(backend).list_entries(kind=kind, project=project, limit=limit)
    if not rows:
        console.print("[yellow]no entries[/yellow]")
        return

    table = Table()
    table.add_column("id")
    table.add_column("kind")
    table.add_column("project")
    table.add_column("title")
    table.add_column("updated")
    for entry in rows:
        table.add_row(
            entry.id[:8],
            entry.kind.value,
            entry.project or "-",
            entry.title or "-",
            entry.updated_at.isoformat(timespec="seconds"),
        )
    console.print(table)


@app.command()
def show(entry_id: str, backend: BackendOpt = None) -> None:
    """Show a single entry as JSON."""
    entry = _resolve_entry(entry_id, backend)
    if entry is None:
        raise typer.Exit(code=1)

    console.print_json(entry.model_dump_json(indent=2))


@app.command()
def search(
    query: str,
    kind: Optional[EntryKind] = typer.Option(None, "--kind", "-k"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    limit: int = typer.Option(10, "--limit", "-n"),
    backend: BackendOpt = None,
) -> None:
    """Search stored entries."""
    results = get_backend(backend).search(query, kind=kind, project=project, limit=limit)
    if not results:
        console.print("[yellow]no results[/yellow]")
        return

    table = Table(title=f"results for {query!r}")
    table.add_column("score")
    table.add_column("id")
    table.add_column("kind")
    table.add_column("project")
    table.add_column("title")
    for r in results:
        table.add_row(
            f"{r.score:.3f}",
            r.entry.id[:8],
            r.entry.kind.value,
            r.entry.project or "-",
            r.entry.title or "-",
        )
    console.print(table)


@app.command()
def delete(entry_id: str, backend: BackendOpt = None) -> None:
    """Delete an entry by id (prefix match allowed)."""
    entry = _resolve_entry(entry_id, backend)
    if entry is None:
        raise typer.Exit(code=1)

    get_backend(backend).delete_entry(entry.id)
    console.print(f"[red]deleted[/red] {entry.id}")


@convo_app.command("save")
def convo_save(
    file: Path = typer.Argument(..., exists=True, readable=True),
    backend: BackendOpt = None,
) -> None:
    """Save a conversation from a JSON file."""
    payload = file.read_text(encoding="utf-8")
    convo = Conversation.model_validate_json(payload)
    get_backend(backend).save_conversation(convo)
    console.print(f"[green]saved[/green] conversation {convo.id}")


@convo_app.command("list")
def convo_list(
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    limit: int = typer.Option(20, "--limit", "-n"),
    backend: BackendOpt = None,
) -> None:
    """List recent conversations."""
    rows = get_backend(backend).list_conversations(project=project, limit=limit)
    if not rows:
        console.print("[yellow]no conversations[/yellow]")
        return

    table = Table()
    table.add_column("id")
    table.add_column("project")
    table.add_column("title")
    table.add_column("messages")
    table.add_column("updated")
    for c in rows:
        table.add_row(
            c.id[:8],
            c.project or "-",
            c.title or "-",
            str(len(c.messages)),
            c.updated_at.isoformat(timespec="seconds"),
        )
    console.print(table)


@convo_app.command("show")
def convo_show(conversation_id: str, backend: BackendOpt = None) -> None:
    """Show a conversation as JSON."""
    convo = get_backend(backend).get_conversation(conversation_id)
    if convo is None:
        candidates = [
            c for c in get_backend(backend).list_conversations(limit=10_000)
            if c.id.startswith(conversation_id)
        ]
        if len(candidates) != 1:
            console.print(f"[red]not found[/red] {conversation_id}")
            raise typer.Exit(code=1)
        convo = candidates[0]

    console.print_json(convo.model_dump_json(indent=2))


@skill_app.command("install")
def skill_install(target: Optional[Path] = typer.Option(None, "--target")) -> None:
    """Install bundled SKILL.md into the Claude skills dir."""
    dest = install_skill(target)
    console.print(f"[green]installed[/green] {dest}")


@skill_app.command("path")
def skill_path() -> None:
    """Print expected skill install path."""
    console.print(str(claude_skills_dir() / "SKILL.md"))


def _hook_payload() -> dict:
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup",
                    "hooks": [
                        {"type": "command", "command": "gctx sessions sync >/dev/null 2>&1; gctx boot || true"}
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {"type": "command", "command": "gctx live --limit 5 || true"}
                    ]
                }
            ],
        }
    }


@hook_app.command("install")
def hook_install(
    apply: bool = typer.Option(False, "--apply", help="Merge into ~/.claude/settings.json"),
    settings: Optional[Path] = typer.Option(None, "--settings", help="Override settings.json path"),
) -> None:
    """Install Claude Code hooks. Default prints snippet; --apply writes to settings."""
    snippet = _hook_payload()
    if not apply:
        console.print_json(json.dumps(snippet))
        return

    target = settings or (claude_dir() / "settings.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    current: dict = {}
    if target.exists():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = target.with_suffix(".json.bak")
            target.replace(backup)
            console.print(f"[yellow]invalid JSON, backed up to {backup}[/yellow]")
            current = {}

    hooks = current.setdefault("hooks", {})
    for event, blocks in snippet["hooks"].items():
        existing = hooks.setdefault(event, [])
        for block in blocks:
            if block not in existing:
                existing.append(block)

    target.write_text(json.dumps(current, indent=2), encoding="utf-8")
    console.print(f"[green]installed[/green] {target}")


@hook_app.command("uninstall")
def hook_uninstall(
    settings: Optional[Path] = typer.Option(None, "--settings"),
) -> None:
    """Remove gctx hook entries from settings.json."""
    target = settings or (claude_dir() / "settings.json")
    if not target.exists():
        console.print("[yellow]no settings.json[/yellow]")
        return

    current = json.loads(target.read_text(encoding="utf-8"))
    payload = _hook_payload()
    hooks = current.get("hooks", {})
    for event, blocks in payload["hooks"].items():
        existing = hooks.get(event, [])
        hooks[event] = [b for b in existing if b not in blocks]
        if not hooks[event]:
            hooks.pop(event)

    target.write_text(json.dumps(current, indent=2), encoding="utf-8")
    console.print(f"[green]uninstalled[/green] {target}")


@app.command()
def boot(
    limit: int = typer.Option(8, "--limit", "-n"),
    backend: BackendOpt = None,
) -> None:
    """Emit broad project context at session start."""
    cwd = os.getcwd()
    project = Path(cwd).name
    backend_obj = get_backend(backend)

    queries = [project, cwd, Path(cwd).parent.name]
    seen: set[str] = set()
    bullets: list[str] = []

    for q in queries:
        if not q:
            continue
        for r in backend_obj.search(q, limit=limit):
            if r.entry.id in seen:
                continue
            seen.add(r.entry.id)
            snippet = r.entry.content.strip().replace("\n", " ")[:200]
            bullets.append(f"- [{r.entry.kind.value}] {r.entry.title or r.entry.id}: {snippet}")
            if len(bullets) >= limit:
                break
        if len(bullets) >= limit:
            break

    if not bullets:
        print(
            "INSTRUCTION: At the very start of your first reply this session, "
            "show the user this exact block before anything else:\n\n"
            "📚 Contexto carregado: nenhum match para projeto atual.\n"
        )
        return

    block = "\n".join(
        [
            f"📚 Contexto do projeto `{project}` ({cwd}):",
            *bullets,
        ]
    )
    print(
        "INSTRUCTION: At the very start of your first reply this session, "
        "show the user this exact block verbatim before anything else, "
        "then briefly state you are ready.\n\n"
        + block
    )


@app.command()
def live(
    query: Optional[str] = typer.Argument(None),
    limit: int = typer.Option(5, "--limit", "-n"),
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    invoke_skill: bool = typer.Option(False, "--invoke-skill"),
    backend: BackendOpt = None,
) -> None:
    """Live context feed. Reads stdin JSON when invoked from a Claude hook."""
    text = query
    cwd_project: str | None = project

    if text is None and not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            payload = {}
        text = payload.get("prompt") or payload.get("user_prompt") or ""
        cwd_project = cwd_project or payload.get("cwd") or os.getcwd()

    if not text:
        return

    if invoke_skill:
        directive = (
            "BEFORE answering this turn, you MUST invoke the Skill tool with "
            "skill=\"global-context\" to load relevant prior session context. "
            f"Pass the user prompt as args. User prompt: {text!r}"
        )
        print(directive)
        return

    backend_obj = get_backend(backend)
    results = backend_obj.search(text, project=None, limit=limit)
    if not results:
        return

    lines = ["<global-context>"]
    for r in results:
        title = (r.entry.title or r.entry.id).strip().replace("\n", " ")[:80]
        lines.append(f"- {title}")
    lines.append("</global-context>")
    print("\n".join(lines))


@sessions_app.command("list")
def sessions_list(limit: int = typer.Option(20, "--limit", "-n")) -> None:
    """List Claude session files on disk."""
    files = discover_sessions()
    if not files:
        console.print("[yellow]no sessions found[/yellow]")
        return

    table = Table(title=f"sessions ({len(files)} total)")
    table.add_column("session")
    table.add_column("project")
    table.add_column("size")
    table.add_column("modified")
    for sf in files[:limit]:
        table.add_row(
            sf.session_id[:8],
            sf.project_path,
            f"{sf.size / 1024:.1f}K",
            sf.modified_at.isoformat(timespec="seconds"),
        )
    console.print(table)


@sessions_app.command("sync")
def sessions_sync(
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    force: bool = typer.Option(False, "--force", "-f"),
    backend: BackendOpt = None,
) -> None:
    """Ingest all Claude sessions into storage."""
    stats = sync_sessions(get_backend(backend), force=force, project=project)
    console.print(
        f"[green]synced[/green] scanned={stats.scanned} "
        f"imported={stats.imported} skipped={stats.skipped} failed={stats.failed}"
    )


@sessions_app.command("search")
def sessions_search(
    query: str,
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    limit: int = typer.Option(10, "--limit", "-n"),
    backend: BackendOpt = None,
) -> None:
    """Search inside ingested Claude session content."""
    results = get_backend(backend).search(
        query, kind=EntryKind.CONVERSATION, project=project, limit=limit
    )
    if not results:
        console.print("[yellow]no results[/yellow]")
        return

    table = Table(title=f"session matches for {query!r}")
    table.add_column("score")
    table.add_column("session")
    table.add_column("project")
    table.add_column("title")
    for r in results:
        sid = r.entry.metadata.get("conversation_id", r.entry.id)
        table.add_row(
            f"{r.score:.3f}",
            sid[:8],
            r.entry.project or "-",
            (r.entry.title or "-")[:60],
        )
    console.print(table)


@sessions_app.command("active")
def sessions_active() -> None:
    """List sessions with active claude processes."""
    files = discover_sessions()
    if not files:
        console.print("[yellow]no sessions[/yellow]")
        return

    import subprocess

    out = subprocess.run(["pgrep", "-fl", "claude"], capture_output=True, text=True)
    pids = [line.split()[0] for line in out.stdout.splitlines() if line.strip()]

    from datetime import datetime, timedelta, timezone

    threshold = datetime.now(timezone.utc) - timedelta(minutes=10)
    active = [s for s in files if s.modified_at >= threshold]

    table = Table(title=f"active sessions ({len(active)}); claude pids={','.join(pids) or '-'}")
    table.add_column("session")
    table.add_column("project")
    table.add_column("modified")
    for s in active[:20]:
        table.add_row(
            s.session_id[:8],
            s.project_path,
            s.modified_at.isoformat(timespec="seconds"),
        )
    console.print(table)


@sessions_app.command("tail")
def sessions_tail(
    session_id: Optional[str] = typer.Argument(None, help="Session id or prefix; default = newest"),
    lines: int = typer.Option(20, "--lines", "-n"),
    follow: bool = typer.Option(False, "--follow", "-f"),
) -> None:
    """Tail recent messages from a session log."""
    files = discover_sessions()
    if not files:
        console.print("[yellow]no sessions[/yellow]")
        raise typer.Exit(1)

    if session_id:
        candidates = [s for s in files if s.session_id.startswith(session_id)]
        if not candidates:
            console.print(f"[red]not found[/red] {session_id}")
            raise typer.Exit(1)
        target = candidates[0]
    else:
        target = files[0]

    from global_context.sessions.parser import SessionParser

    convo = SessionParser(target.path).to_conversation(target.session_id, target.project_path)
    msgs = convo.messages[-lines:]
    console.print(f"[bold]{target.session_id}[/bold] {target.project_path}")
    for m in msgs:
        snippet = m.content.strip().replace("\n", " ")[:200]
        console.print(f"[dim]{m.timestamp.isoformat(timespec='seconds')}[/dim] [{m.role.value}] {snippet}")

    if not follow:
        return

    import time

    last_size = target.path.stat().st_size
    while True:
        time.sleep(2)
        size = target.path.stat().st_size
        if size <= last_size:
            continue
        with target.path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(last_size)
            new = fh.read()
        last_size = size
        for line in new.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            from global_context.sessions.parser import _extract_message

            ext = _extract_message(rec)
            if ext is None:
                continue
            role, text, ts = ext
            snippet = text.strip().replace("\n", " ")[:200]
            console.print(f"[dim]{ts.isoformat(timespec='seconds')}[/dim] [{role.value}] {snippet}")


def _resolve_entry(entry_id: str, backend: BackendOpt) -> MemoryEntry | None:
    backend_obj = get_backend(backend)
    entry = backend_obj.get_entry(entry_id)
    if entry is not None:
        return entry

    candidates = [
        e for e in backend_obj.list_entries(limit=10_000) if e.id.startswith(entry_id)
    ]
    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        console.print(f"[red]not found[/red] {entry_id}")
    else:
        console.print(f"[red]ambiguous[/red] {len(candidates)} matches for {entry_id}")

    return None


if __name__ == "__main__":
    app()
