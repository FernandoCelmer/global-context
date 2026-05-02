from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from global_context.core.store import ContextStore


def _default_root() -> Path:
    env = os.environ.get("GLOBAL_CONTEXT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".global-context"


def _format_hits(hits: list, header: str) -> str:
    if not hits:
        return ""
    lines = [f"## {header}", ""]
    for h in hits:
        src = h.entry.source or "-"
        lines.append(f"### [{h.score:.2f}] {h.entry.scope}/{h.entry.topic} — {src}")
        lines.append(h.entry.content.strip())
        lines.append("")
    return "\n".join(lines)


def _emit(event: str, additional_context: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": additional_context,
        }
    }
    print(json.dumps(payload))


def _read_stdin_json() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def session_start() -> None:
    data = _read_stdin_json()
    scope = os.environ.get("GLOBAL_CONTEXT_SCOPE")
    k = int(os.environ.get("GLOBAL_CONTEXT_RECALL_K", "8"))
    cwd = data.get("cwd") or os.getcwd()
    query = scope or Path(cwd).name
    store = ContextStore(_default_root())
    try:
        hits = store.warmup(query=query, k=k)
        ctx = _format_hits(hits, f"global-context: warmup for '{query}'")
        _emit("SessionStart", ctx)
    finally:
        store.close()


def user_prompt_submit() -> None:
    data = _read_stdin_json()
    prompt = data.get("prompt") or data.get("user_prompt") or ""
    if not prompt.strip():
        _emit("UserPromptSubmit", "")
        return
    scope = os.environ.get("GLOBAL_CONTEXT_SCOPE")
    k = int(os.environ.get("GLOBAL_CONTEXT_RECALL_K", "5"))
    store = ContextStore(_default_root())
    try:
        hits = store.search(prompt, k=k, scope=scope)
        ctx = _format_hits(hits, "global-context: relevant memories")
        _emit("UserPromptSubmit", ctx)
    finally:
        store.close()


def main() -> None:
    event = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HOOK_EVENT") or "").lower()
    if event in {"sessionstart", "session-start", "session_start"}:
        session_start()
    elif event in {"userpromptsubmit", "user-prompt-submit", "user_prompt_submit"}:
        user_prompt_submit()
    else:
        _emit("Unknown", "")


if __name__ == "__main__":
    main()
