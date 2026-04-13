"""
ORION-R1 Memory Graph
Knowledge graph connecting conversations, files, apps, people, tasks
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict
try:
    import networkx as nx
except ImportError:
    class _NoPath(Exception):
        pass

    class _SimpleMultiDiGraph:
        def __init__(self):
            self._nodes = {}
            self._edges = []

        def add_node(self, node_id, **attrs):
            self._nodes[node_id] = attrs

        def add_edge(self, source, target, key=None, **attrs):
            if source not in self._nodes:
                self._nodes[source] = {}
            if target not in self._nodes:
                self._nodes[target] = {}
            self._edges.append((source, target, key, attrs))

        def has_node(self, node_id):
            return node_id in self._nodes

        def remove_node(self, node_id):
            self._nodes.pop(node_id, None)
            self._edges = [e for e in self._edges if e[0] != node_id and e[1] != node_id]

        def has_edge(self, source, target, key=None):
            return any(
                e[0] == source and e[1] == target and (key is None or e[2] == key)
                for e in self._edges
            )

        def remove_edge(self, source, target, key=None):
            for idx, edge in enumerate(self._edges):
                if edge[0] == source and edge[1] == target and (key is None or edge[2] == key):
                    self._edges.pop(idx)
                    return

        def neighbors(self, node_id):
            seen = []
            for source, target, _, _ in self._edges:
                if source == node_id and target not in seen:
                    seen.append(target)
            return seen

    class _SimpleNxModule:
        MultiDiGraph = _SimpleMultiDiGraph
        NetworkXNoPath = _NoPath

        @staticmethod
        def shortest_path(graph, source_id, target_id):
            if source_id == target_id:
                return [source_id]
            queue = [(source_id, [source_id])]
            visited = {source_id}
            while queue:
                node_id, path = queue.pop(0)
                for neighbor in graph.neighbors(node_id):
                    if neighbor == target_id:
                        return path + [neighbor]
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))
            raise _NoPath()

    nx = _SimpleNxModule()

DATA_DIR = Path.home() / ".r1" / "memory_graph"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class MemoryNode:
    def __init__(self, id: str, type: str, data: Dict):
        self.id = id
        self.type = type  # conversation, file, person, app, task, fact, event
        self.data = data
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class MemoryEdge:
    def __init__(self, source: str, target: str, relation: str, weight: float = 1.0):
        self.source = source
        self.target = target
        self.relation = relation  # mentions, created, modified, related_to, contains
        self.weight = weight
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight
        }

class MemoryGraph:
    def __init__(self):
        self.graph_file = DATA_DIR / "graph.json"
        self.graph = nx.MultiDiGraph()
        self.nodes: Dict[str, MemoryNode] = {}
        self.edges: List[MemoryEdge] = []
        self._load()

    def _load(self):
        if self.graph_file.exists():
            try:
                data = json.loads(self.graph_file.read_text())
                for node_data in data.get("nodes", []):
                    node = MemoryNode(
                        id=node_data["id"],
                        type=node_data["type"],
                        data=node_data["data"]
                    )
                    node.created_at = node_data.get("created_at", node.created_at)
                    node.updated_at = node_data.get("updated_at", node.updated_at)
                    self.nodes[node.id] = node
                    self.graph.add_node(node.id, **node.to_dict())

                for edge_data in data.get("edges", []):
                    edge = MemoryEdge(
                        source=edge_data["source"],
                        target=edge_data["target"],
                        relation=edge_data["relation"],
                        weight=edge_data.get("weight", 1.0)
                    )
                    self.edges.append(edge)
                    self.graph.add_edge(
                        edge.source,
                        edge.target,
                        key=edge.relation,
                        relation=edge.relation,
                        weight=edge.weight,
                    )
            except Exception as e:
                print(f"Error loading graph: {e}")

    def _save(self):
        data = {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }
        self.graph_file.write_text(json.dumps(data, indent=2))

    def _generate_id(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:12]

    # === NODE OPERATIONS ===

    def add_node(self, type: str, data: Dict, id: str = None) -> MemoryNode:
        """Add a node to the graph"""
        if id is None:
            id = self._generate_id(json.dumps(data, sort_keys=True))

        if id in self.nodes:
            # Update existing
            self.nodes[id].data = data
            self.nodes[id].updated_at = datetime.now().isoformat()
        else:
            node = MemoryNode(id=id, type=type, data=data)
            self.nodes[id] = node
            self.graph.add_node(id, **node.to_dict())

        self._save()
        return self.nodes[id]

    def get_node(self, id: str) -> Optional[MemoryNode]:
        return self.nodes.get(id)

    def delete_node(self, id: str) -> bool:
        if id in self.nodes:
            del self.nodes[id]
            if self.graph.has_node(id):
                self.graph.remove_node(id)
            self.edges = [e for e in self.edges if e.source != id and e.target != id]
            self._save()
            return True
        return False

    def list_nodes(self, type: str = None) -> List[MemoryNode]:
        if type:
            return [n for n in self.nodes.values() if n.type == type]
        return list(self.nodes.values())

    # === EDGE OPERATIONS ===

    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0) -> MemoryEdge:
        """Add relationship between nodes"""
        edge = MemoryEdge(source=source, target=target, relation=relation, weight=weight)
        self.edges.append(edge)
        self.graph.add_edge(source, target, key=relation, relation=relation, weight=weight)
        self._save()
        return edge

    def remove_edge(self, source: str, target: str, relation: str = None) -> int:
        """Remove edges between nodes"""
        removed = 0
        if relation:
            if self.graph.has_edge(source, target, key=relation):
                self.graph.remove_edge(source, target, key=relation)
                removed = 1
        else:
            while self.graph.has_edge(source, target):
                self.graph.remove_edge(source, target)
                removed += 1

        self.edges = [e for e in self.edges if not (e.source == source and e.target == target and (relation is None or e.relation == relation))]
        self._save()
        return removed

    def get_edges(self, node_id: str) -> List[MemoryEdge]:
        return [e for e in self.edges if e.source == node_id or e.target == node_id]

    # === QUERY OPERATIONS ===

    def search(self, query: str, type: str = None) -> List[Dict]:
        """Search nodes by content"""
        results = []
        query_lower = query.lower()

        for node in self.nodes.values():
            if type and node.type != type:
                continue

            # Search in data
            data_str = json.dumps(node.data).lower()
            if query_lower in data_str:
                results.append({
                    "node": node.to_dict(),
                    "relevance": 1.0
                })

        return sorted(results, key=lambda x: x["relevance"], reverse=True)[:50]

    def get_neighbors(self, node_id: str, depth: int = 1) -> Dict:
        """Get connected nodes"""
        neighbors = set()
        current = {node_id}

        for _ in range(depth):
            next_level = set()
            for n in current:
                if self.graph.has_node(n):
                    for neighbor in self.graph.neighbors(n):
                        if neighbor not in neighbors:
                            next_level.add(neighbor)
            neighbors.update(next_level)
            current = next_level

        return {
            "center": self.nodes.get(node_id),
            "neighbors": [self.nodes.get(n) for n in neighbors if n in self.nodes]
        }

    def find_path(self, source_id: str, target_id: str) -> List[str]:
        """Find path between nodes"""
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            return path
        except nx.NetworkXNoPath:
            return []

    def get_related(self, node_id: str, relation: str = None) -> List[MemoryNode]:
        """Get nodes related by specific relation"""
        related = []
        for edge in self.edges:
            if edge.source == node_id and (relation is None or edge.relation == relation):
                if edge.target in self.nodes:
                    related.append(self.nodes[edge.target])
            elif edge.target == node_id and (relation is None or edge.relation == relation):
                if edge.source in self.nodes:
                    related.append(self.nodes[edge.source])
        return related

    # === SPECIALIZED HELPERS ===

    def add_conversation(self, message: str, role: str, session_id: str = "default") -> MemoryNode:
        node = self.add_node("conversation", {
            "message": message,
            "role": role,
            "session_id": session_id
        })
        # Link to session
        session_node = self.add_node("session", {"id": session_id}, id=f"session:{session_id}")
        self.add_edge(session_node.id, node.id, "contains")
        return node

    def add_file(self, path: str, content: str = None, metadata: Dict = None) -> MemoryNode:
        p = Path(path)
        node = self.add_node("file", {
            "path": str(path),
            "name": p.name,
            "extension": p.suffix,
            "content_preview": content[:500] if content else None,
            "metadata": metadata or {}
        }, id=f"file:{path}")
        return node

    def add_person(self, name: str, contact: Dict = None) -> MemoryNode:
        return self.add_node("person", {
            "name": name,
            "contact": contact or {}
        }, id=f"person:{name.lower().replace(' ', '_')}")

    def add_app(self, name: str, path: str = None) -> MemoryNode:
        return self.add_node("app", {
            "name": name,
            "path": path
        }, id=f"app:{name.lower()}")

    def add_task(self, description: str, status: str = "pending", metadata: Dict = None) -> MemoryNode:
        return self.add_node("task", {
            "description": description,
            "status": status,
            "metadata": metadata or {}
        })

    def add_fact(self, key: str, value: Any, category: str = "general") -> MemoryNode:
        return self.add_node("fact", {
            "key": key,
            "value": value,
            "category": category
        }, id=f"fact:{key}")

    def link_nodes(self, source_id: str, target_id: str, relation: str):
        """Create relationship between existing nodes"""
        return self.add_edge(source_id, target_id, relation)

    def get_stats(self) -> Dict:
        node_types = defaultdict(int)
        for node in self.nodes.values():
            node_types[node.type] += 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": dict(node_types),
            "avg_connections": len(self.edges) / max(len(self.nodes), 1)
        }


# Singleton
_graph = None

def get_memory_graph() -> MemoryGraph:
    global _graph
    if _graph is None:
        _graph = MemoryGraph()
    return _graph
