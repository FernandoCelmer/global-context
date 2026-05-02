"""Backend conformance tests."""

from __future__ import annotations

import pytest

from global_context.core.models import EntryKind, MemoryEntry, Message, Conversation, Role
from global_context.storage.json_backend import JsonBackend
from global_context.storage.sql_backend import SqlBackend


@pytest.fixture(params=["json", "sql"])
def backend(request, tmp_path):
    if request.param == "json":
        b = JsonBackend(path=tmp_path / "store.json")
    else:
        b = SqlBackend(url=f"sqlite:///{tmp_path / 'store.db'}")

    b.init()
    yield b
    b.close()


def test_save_and_get_entry(backend):
    entry = MemoryEntry(title="hello", content="world", kind=EntryKind.NOTE)
    backend.save_entry(entry)

    fetched = backend.get_entry(entry.id)
    assert fetched is not None
    assert fetched.title == "hello"
    assert fetched.content == "world"


def test_list_filtering(backend):
    backend.save_entry(MemoryEntry(title="a", content="x", project="p1"))
    backend.save_entry(MemoryEntry(title="b", content="y", project="p2"))
    backend.save_entry(MemoryEntry(title="c", content="z", project="p1"))

    p1 = backend.list_entries(project="p1")
    assert len(p1) == 2


def test_search_finds_content(backend):
    backend.save_entry(MemoryEntry(title="auth", content="oauth flow notes"))
    backend.save_entry(MemoryEntry(title="db", content="sqlite migration"))

    results = backend.search("oauth")
    assert len(results) == 1
    assert results[0].entry.title == "auth"


def test_delete_entry(backend):
    entry = MemoryEntry(title="x", content="y")
    backend.save_entry(entry)
    assert backend.delete_entry(entry.id) is True
    assert backend.get_entry(entry.id) is None


def test_conversation_roundtrip(backend):
    convo = Conversation(
        project="proj",
        title="t",
        messages=[Message(role=Role.USER, content="hi")],
    )
    backend.save_conversation(convo)

    fetched = backend.get_conversation(convo.id)
    assert fetched is not None
    assert len(fetched.messages) == 1
    assert fetched.messages[0].content == "hi"
