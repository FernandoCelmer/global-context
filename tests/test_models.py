from global_context import Entry


def test_entry_id_autogen():
    e = Entry(scope="s1", topic="t1", content="hello")
    assert e.id
    assert len(e.id) == 16


def test_entry_id_stable_for_same_inputs():
    from datetime import datetime, timezone

    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = Entry(scope="s", topic="t", content="x", created_at=ts)
    b = Entry(scope="s", topic="t", content="x", created_at=ts)
    assert a.id == b.id
