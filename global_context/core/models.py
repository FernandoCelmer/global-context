"""Pydantic domain models for stored context."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class EntryKind(str, Enum):
    CONVERSATION = "conversation"
    PROJECT = "project"
    NOTE = "note"
    MEMORY = "memory"


class Message(BaseModel):
    role: Role
    content: str
    timestamp: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    id: str = Field(default_factory=_new_id)
    project: str | None = None
    title: str | None = None
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def append(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = _utcnow()

    def as_text(self) -> str:
        return "\n".join(f"[{m.role.value}] {m.content}" for m in self.messages)


class ProjectContext(BaseModel):
    name: str
    path: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utcnow)


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=_new_id)
    kind: EntryKind = EntryKind.NOTE
    project: str | None = None
    title: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class SearchResult(BaseModel):
    entry: MemoryEntry
    score: float = 0.0
