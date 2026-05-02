from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_id(*parts: str) -> str:
    h = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return h[:16]


class Entry(BaseModel):
    id: str = ""
    scope: str
    topic: str
    content: str
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict = Field(default_factory=dict)

    def model_post_init(self, _ctx) -> None:
        if not self.id:
            object.__setattr__(
                self,
                "id",
                _hash_id(self.scope, self.topic, self.content, self.created_at.isoformat()),
            )


class Topic(BaseModel):
    name: str
    scope: str
    description: Optional[str] = None


class Scope(BaseModel):
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
