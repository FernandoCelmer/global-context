from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    attrs TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    relation TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    attrs TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(src) REFERENCES nodes(id),
    FOREIGN KEY(dst) REFERENCES nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
"""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeGraph:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def add_node(
        self,
        node_id: str,
        kind: str,
        name: str,
        attrs: Optional[dict] = None,
    ) -> None:
        import json

        self._conn.execute(
            "INSERT OR REPLACE INTO nodes(id, kind, name, attrs, created_at) VALUES (?, ?, ?, ?, ?)",
            (node_id, kind, name, json.dumps(attrs or {}, default=str), _utcnow_iso()),
        )
        self._conn.commit()

    def add_edge(
        self,
        src: str,
        dst: str,
        relation: str,
        valid_from: Optional[str] = None,
        attrs: Optional[dict] = None,
    ) -> int:
        import json

        cur = self._conn.execute(
            "INSERT INTO edges(src, dst, relation, valid_from, valid_to, attrs) VALUES (?, ?, ?, ?, NULL, ?)",
            (src, dst, relation, valid_from or _utcnow_iso(), json.dumps(attrs or {}, default=str)),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def invalidate_edge(self, edge_id: int, valid_to: Optional[str] = None) -> None:
        self._conn.execute(
            "UPDATE edges SET valid_to = ? WHERE id = ?",
            (valid_to or _utcnow_iso(), edge_id),
        )
        self._conn.commit()

    def neighbors(
        self,
        node_id: str,
        relation: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict]:
        sql = "SELECT * FROM edges WHERE src = ?"
        args: list = [node_id]
        if relation:
            sql += " AND relation = ?"
            args.append(relation)
        if active_only:
            sql += " AND valid_to IS NULL"
        rows = self._conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def timeline(self, node_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM edges WHERE src = ? OR dst = ? ORDER BY valid_from",
            (node_id, node_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def query(
        self,
        kind: Optional[str] = None,
        name_like: Optional[str] = None,
    ) -> list[dict]:
        sql = "SELECT * FROM nodes WHERE 1=1"
        args: list = []
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        if name_like:
            sql += " AND name LIKE ?"
            args.append(f"%{name_like}%")
        rows = self._conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
