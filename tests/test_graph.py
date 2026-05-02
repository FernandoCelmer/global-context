from global_context.graph.kg import KnowledgeGraph


def test_node_and_edge(tmp_path):
    kg = KnowledgeGraph(tmp_path / "g.sqlite")
    kg.add_node("a", "person", "Alice")
    kg.add_node("b", "project", "API")
    eid = kg.add_edge("a", "b", "owns")
    n = kg.neighbors("a", relation="owns")
    assert len(n) == 1
    assert n[0]["dst"] == "b"
    kg.invalidate_edge(eid)
    assert kg.neighbors("a", relation="owns") == []
    kg.close()


def test_query_and_timeline(tmp_path):
    kg = KnowledgeGraph(tmp_path / "g.sqlite")
    kg.add_node("a", "person", "Alice")
    kg.add_node("b", "person", "Bob")
    kg.add_edge("a", "b", "knows")
    found = kg.query(kind="person", name_like="Ali")
    assert len(found) == 1
    tl = kg.timeline("a")
    assert len(tl) == 1
    kg.close()
