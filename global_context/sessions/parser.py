"""Parse Claude Code `.jsonl` session logs into domain models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from global_context.core.models import Conversation, Message, Role


_TEXT_ROLES = {"user", "assistant", "system", "tool"}


class SessionParser:
    """Stateful parser for one session file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def iter_records(self) -> Iterable[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def to_conversation(
        self,
        session_id: str,
        project: str | None,
    ) -> Conversation:
        messages: list[Message] = []
        first_ts: datetime | None = None
        last_ts: datetime | None = None
        title: str | None = None

        for record in self.iter_records():
            extracted = _extract_message(record)
            if extracted is None:
                continue

            role, text, ts = extracted
            if not text.strip():
                continue

            messages.append(Message(role=role, content=text, timestamp=ts))

            if first_ts is None:
                first_ts = ts
            last_ts = ts

            if title is None and role == Role.USER:
                title = text.strip().splitlines()[0][:120]

        now = datetime.now(timezone.utc)
        return Conversation(
            id=session_id,
            project=project,
            title=title,
            messages=messages,
            created_at=first_ts or now,
            updated_at=last_ts or now,
            metadata={"source": "claude-code", "path": str(self.path)},
        )


def parse_session_file(
    path: Path,
    session_id: str | None = None,
    project: str | None = None,
) -> Conversation:
    parser = SessionParser(path)
    return parser.to_conversation(session_id or path.stem, project)


def _extract_message(record: dict[str, Any]) -> tuple[Role, str, datetime] | None:
    nested = record.get("message")
    merged = {**record, **nested} if isinstance(nested, dict) else dict(record)

    role_raw = merged.get("role") or record.get("type")
    if role_raw not in _TEXT_ROLES:
        return None

    text = _flatten_content(merged.get("content"))
    if not text:
        return None

    ts = _parse_ts(record.get("timestamp") or merged.get("timestamp") or merged.get("ts"))
    return Role(role_raw), text, ts


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if "text" in block and isinstance(block["text"], str):
                    parts.append(block["text"])
                elif block.get("type") == "tool_use":
                    name = block.get("name", "tool")
                    parts.append(f"[tool_use:{name}]")
                elif block.get("type") == "tool_result":
                    result = block.get("content")
                    parts.append(_flatten_content(result))
        return "\n".join(p for p in parts if p)

    return str(content)


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass

    return datetime.now(timezone.utc)
