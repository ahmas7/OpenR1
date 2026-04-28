"""
R1 - Memory Graph Placeholder
"""
import logging

logger = logging.getLogger("R1:memory_graph")

class MemoryGraph:
    def __init__(self):
        pass
    def add_conversation(self, *args, **kwargs): pass
    def add_fact(self, *args, **kwargs): pass
    def add_task(self, goal, *args, **kwargs):
        class Node: id = "dummy"
        return Node()
    def add_node(self, *args, **kwargs):
        class Node: id = "dummy"
        return Node()
    def link_nodes(self, *args, **kwargs): pass
    def get_stats(self): return {"status": "inactive"}
    def search(self, *args, **kwargs): return []

_graph = None
def get_memory_graph():
    global _graph
    if _graph is None:
        _graph = MemoryGraph()
    return _graph
