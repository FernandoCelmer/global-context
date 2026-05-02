"""Tests for Claude session ingestion."""

from __future__ import annotations

import json
from pathlib import Path

from global_context.core.models import EntryKind
from global_context.sessions.importer import SessionImporter
from global_context.sessions.parser import parse_session_file
from global_context.sessions.scanner import discover_sessions
from global_context.storage.json_backend import JsonBackend


def _write_session(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def test_discover_sessions(tmp_path):
    root = tmp_path / "projects"
    _write_session(root / "-Users-x/abc.jsonl", [{"type": "user", "content": "hi"}])
    _write_session(root / "-Users-y/def.jsonl", [{"type": "user", "content": "yo"}])

    sessions = discover_sessions(root)
    assert {s.session_id for s in sessions} == {"abc", "def"}


def test_parse_session_extracts_messages(tmp_path):
    path = tmp_path / "s.jsonl"
    _write_session(
        path,
        [
            {"type": "user", "content": "first question", "timestamp": "2026-01-01T00:00:00Z"},
            {
                "type": "assistant",
                "content": [{"type": "text", "text": "answer"}],
                "timestamp": "2026-01-01T00:00:01Z",
            },
            {"type": "file-history-snapshot", "snapshot": {}},
        ],
    )

    convo = parse_session_file(path, project="demo")
    assert convo.project == "demo"
    assert len(convo.messages) == 2
    assert convo.messages[0].content == "first question"
    assert convo.title and "first question" in convo.title


def test_importer_round_trip_and_search(tmp_path):
    root = tmp_path / "projects"
    _write_session(
        root / "-Users-demo/sess-1.jsonl",
        [
            {"type": "user", "content": "talk about kafka topics", "timestamp": "2026-01-01T00:00:00Z"},
            {"type": "assistant", "content": "kafka uses partitions", "timestamp": "2026-01-01T00:00:01Z"},
        ],
    )

    backend = JsonBackend(path=tmp_path / "store.json")
    backend.init()
    stats = SessionImporter(backend).sync(root=root)
    assert stats.imported == 1

    results = backend.search("kafka", kind=EntryKind.CONVERSATION)
    assert len(results) == 1
    assert "kafka" in results[0].entry.content.lower()
