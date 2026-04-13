import asyncio
from R1.memory.store import MemoryStore


async def _test_logic(store):
    await store.set_fact("user.location", "Dhaka", category="personal")
    await store.add_message("session-a", "user", "Please remember this context")
    store.add_tool_call("session-a", "shell", {"command": "echo hi"}, "hi", True)


def test_memory_store_mirrors_into_graph(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(str(db_path))

    # Run async operations
    asyncio.run(_test_logic(store))

    graph = store.graph
    assert graph is not None

    location_node = graph.get_node("fact:user.location")
    assert location_node is not None
    assert location_node.data["value"] == "Dhaka"

    session_neighbors = graph.get_related("session:session-a", "contains")
    assert any(node.type == "conversation" for node in session_neighbors)

