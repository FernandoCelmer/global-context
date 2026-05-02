from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from global_context.core.store import ContextStore
from global_context.mining.transcripts import mine_transcripts


def _default_root() -> Path:
    env = os.environ.get("GLOBAL_CONTEXT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".global-context"


def autosave_transcript(
    transcript_path: str | Path,
    scope: str,
    topic: str = "conversations",
    root: Optional[Path] = None,
) -> int:
    store = ContextStore(root or _default_root())
    try:
        return mine_transcripts(store, transcript_path, scope=scope, topic=topic)
    finally:
        store.close()


def cli_entry() -> None:
    payload = sys.stdin.read().strip()
    data: dict = {}
    if payload:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = {}
    transcript = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH")
    scope = data.get("scope") or os.environ.get("GLOBAL_CONTEXT_SCOPE") or "default"
    if not transcript:
        print(json.dumps({"ok": False, "reason": "no transcript_path"}))
        return
    n = autosave_transcript(transcript, scope=scope)
    print(json.dumps({"ok": True, "saved": n}))


if __name__ == "__main__":
    cli_entry()
