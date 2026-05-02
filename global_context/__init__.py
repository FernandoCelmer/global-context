"""Global Context: persistent context store for Claude Code."""

from __future__ import annotations

from global_context.bootstrap import ensure_bootstrapped
from global_context.core.models import (
    Conversation,
    Message,
    MemoryEntry,
    ProjectContext,
)
from global_context.storage.base import StorageBackend
from global_context.storage.factory import get_backend

__all__ = [
    "Conversation",
    "MemoryEntry",
    "Message",
    "ProjectContext",
    "StorageBackend",
    "ensure_bootstrapped",
    "get_backend",
]

__version__ = "0.2.0"

ensure_bootstrapped()
