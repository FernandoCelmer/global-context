"""SQLAlchemy 2.x backend (SQLite by default)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    DateTime,
    String,
    Text,
    and_,
    create_engine,
    delete,
    or_,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from global_context.core.models import (
    Conversation,
    EntryKind,
    MemoryEntry,
    SearchResult,
)
from global_context.paths import sqlite_path
from global_context.storage.base import StorageBackend


class _Base(DeclarativeBase):
    pass


class _EntryRow(_Base):
    __tablename__ = "memory_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    project: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    extra: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class _ConversationRow(_Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class SqlBackend(StorageBackend):
    """SQLAlchemy-backed store. Defaults to local SQLite file."""

    name = "sql"

    def __init__(self, url: str | None = None) -> None:
        if url is None:
            path = sqlite_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{path}"

        self.url = url
        self.engine = create_engine(url, future=True)
        self._sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def init(self) -> None:
        _Base.metadata.create_all(self.engine)

    def _session(self) -> Session:
        return self._sessionmaker()

    def save_entry(self, entry: MemoryEntry) -> MemoryEntry:
        with self._session() as s, s.begin():
            row = s.get(_EntryRow, entry.id)
            data = _to_row(entry)
            if row is None:
                s.add(_EntryRow(**data))
            else:
                for key, value in data.items():
                    setattr(row, key, value)

        return entry

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        with self._session() as s:
            row = s.get(_EntryRow, entry_id)
            return _from_row(row) if row else None

    def delete_entry(self, entry_id: str) -> bool:
        with self._session() as s, s.begin():
            result = s.execute(delete(_EntryRow).where(_EntryRow.id == entry_id))
            return result.rowcount > 0

    def list_entries(
        self,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        stmt = select(_EntryRow).order_by(_EntryRow.updated_at.desc()).limit(limit)
        if kind is not None:
            stmt = stmt.where(_EntryRow.kind == kind.value)
        if project is not None:
            stmt = stmt.where(_EntryRow.project == project)

        with self._session() as s:
            rows = s.execute(stmt).scalars().all()
            return [_from_row(r) for r in rows]

    def search(
        self,
        query: str,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        cleaned = query.strip()
        if not cleaned:
            return []

        tokens = [t for t in cleaned.lower().split() if len(t) >= 2]
        if not tokens:
            tokens = [cleaned.lower()]

        token_clauses = []
        for tok in tokens:
            needle = f"%{tok}%"
            token_clauses.append(
                or_(_EntryRow.title.ilike(needle), _EntryRow.content.ilike(needle))
            )

        stmt = select(_EntryRow).where(or_(*token_clauses))
        if kind is not None:
            stmt = stmt.where(_EntryRow.kind == kind.value)
        if project is not None:
            stmt = stmt.where(_EntryRow.project == project)

        stmt = stmt.order_by(_EntryRow.updated_at.desc()).limit(limit * 5)

        with self._session() as s:
            rows = s.execute(stmt).scalars().all()

        scored: list[SearchResult] = []
        for row in rows:
            haystack = f"{row.title}\n{row.content}".lower()
            hits = sum(1 for t in tokens if t in haystack)
            if hits == 0:
                continue
            score = hits / len(tokens)
            scored.append(SearchResult(entry=_from_row(row), score=score))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    def save_conversation(self, conversation: Conversation) -> Conversation:
        payload = conversation.model_dump_json()
        with self._session() as s, s.begin():
            row = s.get(_ConversationRow, conversation.id)
            data = {
                "id": conversation.id,
                "project": conversation.project,
                "title": conversation.title,
                "payload": payload,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
            }
            if row is None:
                s.add(_ConversationRow(**data))
            else:
                for key, value in data.items():
                    setattr(row, key, value)

        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._session() as s:
            row = s.get(_ConversationRow, conversation_id)
            return Conversation.model_validate_json(row.payload) if row else None

    def list_conversations(
        self, project: str | None = None, limit: int = 50
    ) -> list[Conversation]:
        stmt = (
            select(_ConversationRow)
            .order_by(_ConversationRow.updated_at.desc())
            .limit(limit)
        )
        if project is not None:
            stmt = stmt.where(_ConversationRow.project == project)

        with self._session() as s:
            rows = s.execute(stmt).scalars().all()
            return [Conversation.model_validate_json(r.payload) for r in rows]

    def close(self) -> None:
        self.engine.dispose()


def _to_row(entry: MemoryEntry) -> dict:
    return {
        "id": entry.id,
        "kind": entry.kind.value,
        "project": entry.project,
        "title": entry.title,
        "content": entry.content,
        "tags": list(entry.tags),
        "extra": dict(entry.metadata),
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def _from_row(row: _EntryRow) -> MemoryEntry:
    return MemoryEntry(
        id=row.id,
        kind=EntryKind(row.kind),
        project=row.project,
        title=row.title,
        content=row.content,
        tags=list(row.tags or []),
        metadata=dict(row.extra or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _ensure_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


_ = json  # keep import for type tooling
