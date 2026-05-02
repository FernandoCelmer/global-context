from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Optional

from global_context.core.models import Entry


@dataclass
class SearchHit:
    entry: Entry
    score: float


class VectorBackend(ABC):
    @abstractmethod
    def upsert(self, entries: Iterable[Entry]) -> None: ...

    @abstractmethod
    def search(
        self,
        query: str,
        k: int = 5,
        scope: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> list[SearchHit]: ...

    @abstractmethod
    def delete(self, entry_ids: Iterable[str]) -> None: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def list_scopes(self) -> list[str]: ...

    def close(self) -> None:
        return None
