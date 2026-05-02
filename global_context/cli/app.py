from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from global_context.core.store import ContextStore
from global_context.mining.files import mine_files
from global_context.mining.transcripts import mine_transcripts

app = typer.Typer(help="global-context: local-first AI memory.")
console = Console()


def _default_root() -> Path:
    env = os.environ.get("GLOBAL_CONTEXT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".global-context"


def _store(root: Optional[Path] = None) -> ContextStore:
    return ContextStore(root or _default_root())


@app.command()
def init(
    root: Path = typer.Argument(None, help="Storage directory."),
):
    target = root or _default_root()
    store = ContextStore(target)
    console.print(f"[green]initialised[/green] {store.root}")
    store.close()


@app.command()
def add(
    content: str = typer.Argument(..., help="Text to store."),
    scope: str = typer.Option(..., "--scope", "-s"),
    topic: str = typer.Option("general", "--topic", "-t"),
    source: Optional[str] = typer.Option(None, "--source"),
    root: Optional[Path] = typer.Option(None, "--root"),
):
    store = _store(root)
    entry = store.add(content=content, scope=scope, topic=topic, source=source)
    console.print(f"[green]added[/green] {entry.id} scope={scope} topic={topic}")
    store.close()


@app.command()
def search(
    query: str = typer.Argument(..., help="Query text."),
    k: int = typer.Option(5, "--top", "-k"),
    scope: Optional[str] = typer.Option(None, "--scope", "-s"),
    topic: Optional[str] = typer.Option(None, "--topic", "-t"),
    root: Optional[Path] = typer.Option(None, "--root"),
):
    store = _store(root)
    hits = store.search(query, k=k, scope=scope, topic=topic)
    table = Table(title=f"top {len(hits)} for: {query}")
    table.add_column("score", justify="right")
    table.add_column("scope")
    table.add_column("topic")
    table.add_column("source")
    table.add_column("preview")
    for h in hits:
        preview = h.entry.content.replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "..."
        table.add_row(
            f"{h.score:.3f}",
            h.entry.scope,
            h.entry.topic,
            h.entry.source or "-",
            preview,
        )
    console.print(table)
    store.close()


@app.command()
def mine(
    path: Path = typer.Argument(..., help="Directory or file to mine."),
    scope: str = typer.Option(..., "--scope", "-s"),
    mode: str = typer.Option("files", "--mode", "-m", help="files | transcripts"),
    topic: Optional[str] = typer.Option(None, "--topic", "-t"),
    root: Optional[Path] = typer.Option(None, "--root"),
):
    store = _store(root)
    if mode == "files":
        n = mine_files(store, path, scope=scope, topic=topic or "files")
    elif mode == "transcripts":
        n = mine_transcripts(store, path, scope=scope, topic=topic or "conversations")
    else:
        raise typer.BadParameter(f"unknown mode: {mode}")
    console.print(f"[green]mined[/green] {n} entries from {path}")
    store.close()


@app.command()
def warmup(
    query: str = typer.Argument("recent context"),
    k: int = typer.Option(10, "--top", "-k"),
    root: Optional[Path] = typer.Option(None, "--root"),
):
    store = _store(root)
    hits = store.warmup(query=query, k=k)
    for h in hits:
        console.print(f"[bold cyan]{h.entry.scope}/{h.entry.topic}[/bold cyan] [{h.score:.3f}]")
        console.print(h.entry.content)
        console.print("---")
    store.close()


@app.command()
def stats(root: Optional[Path] = typer.Option(None, "--root")):
    store = _store(root)
    info = store.stats()
    for k, v in info.items():
        console.print(f"[bold]{k}[/bold]: {v}")
    store.close()


@app.command()
def delete(
    entry_id: str = typer.Argument(...),
    root: Optional[Path] = typer.Option(None, "--root"),
):
    store = _store(root)
    store.backend.delete([entry_id])
    console.print(f"[red]deleted[/red] {entry_id}")
    store.close()


if __name__ == "__main__":
    app()
