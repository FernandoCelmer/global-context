"""Abstract storage backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from global_context.core.models import (
    Conversation,
    EntryKind,
    MemoryEntry,
    SearchResult,
)


class StorageBackend(ABC):
    """Persistent backend for conversations and memory entries."""

    name: str = "base"

    @abstractmethod
    def init(self) -> None:
        """Create schema/files needed by the backend."""

    @abstractmethod
    def save_entry(self, entry: MemoryEntry) -> MemoryEntry:
        """Persist or update a single memory entry."""

    @abstractmethod
    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        """Fetch entry by id."""

    @abstractmethod
    def delete_entry(self, entry_id: str) -> bool:
        """Delete entry. Return True if removed."""

    @abstractmethod
    def list_entries(
        self,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """List entries filtered by kind and project."""

    @abstractmethod
    def search(
        self,
        query: str,
        kind: EntryKind | None = None,
        project: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search entries by text query."""

    @abstractmethod
    def save_conversation(self, conversation: Conversation) -> Conversation:
        """Persist a conversation as one entry per message bundle."""

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Fetch a previously saved conversation."""

    @abstractmethod
    def list_conversations(
        self, project: str | None = None, limit: int = 50
    ) -> list[Conversation]:
        """List recent conversations."""

    def bulk_save(self, entries: Iterable[MemoryEntry]) -> int:
        count = 0
        for entry in entries:
            self.save_entry(entry)
            count += 1

        return count

    def close(self) -> None:
        """Release backend resources. Default no-op."""
        return None
