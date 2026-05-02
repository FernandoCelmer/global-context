"""Import discovered Claude sessions into the storage backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from global_context.core.models import EntryKind, MemoryEntry
from global_context.sessions.parser import SessionParser
from global_context.sessions.scanner import SessionFile, discover_sessions
from global_context.storage.base import StorageBackend


@dataclass
class ImportStats:
    scanned: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0


class SessionImporter:
    """Drive ingestion of Claude session logs into a backend."""

    def __init__(self, backend: StorageBackend) -> None:
        self.backend = backend

    def import_one(self, session: SessionFile, force: bool = False) -> bool:
        existing = self.backend.get_conversation(session.session_id)
        if existing is not None and not force:
            existing_ts = existing.metadata.get("source_mtime")
            if existing_ts and existing_ts >= session.modified_at.isoformat():
                return False

        parser = SessionParser(session.path)
        convo = parser.to_conversation(session.session_id, session.project_path)
        convo.metadata.update(
            {
                "source": "claude-code",
                "source_path": str(session.path),
                "source_slug": session.project_slug,
                "source_mtime": session.modified_at.isoformat(),
                "size_bytes": session.size,
            }
        )

        if not convo.messages:
            return False

        self.backend.save_conversation(convo)
        self._index_for_search(convo)
        return True

    def _index_for_search(self, convo) -> None:
        text = convo.as_text()
        if not text.strip():
            return

        entry = MemoryEntry(
            id=f"session:{convo.id}",
            kind=EntryKind.CONVERSATION,
            project=convo.project,
            title=convo.title or convo.id,
            content=text,
            tags=["claude-session"],
            metadata={
                "conversation_id": convo.id,
                "source_path": convo.metadata.get("source_path", ""),
                "message_count": len(convo.messages),
            },
            created_at=convo.created_at,
            updated_at=convo.updated_at,
        )
        self.backend.save_entry(entry)

    def sync(
        self,
        root: Path | None = None,
        force: bool = False,
        project: str | None = None,
    ) -> ImportStats:
        stats = ImportStats()
        for session in discover_sessions(root):
            stats.scanned += 1
            if project and project not in session.project_path:
                stats.skipped += 1
                continue
            try:
                if self.import_one(session, force=force):
                    stats.imported += 1
                else:
                    stats.skipped += 1
            except Exception:
                stats.failed += 1

        return stats


def sync_sessions(
    backend: StorageBackend,
    root: Path | None = None,
    force: bool = False,
    project: str | None = None,
) -> ImportStats:
    return SessionImporter(backend).sync(root=root, force=force, project=project)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
