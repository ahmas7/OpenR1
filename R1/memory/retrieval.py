"""
R1 v1 - Memory Retrieval
Build context from memory for the agent.
"""
from typing import List, Dict, Any
from .store import MemoryStore
from ..memory_graph import get_memory_graph


class MemoryRetrieval:
    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.graph = get_memory_graph()

    def get_conversation_context(self, session_id: str, limit: int = 10) -> str:
        messages = self.memory.get_conversation(session_id, limit)
        if not messages:
            return ""
        
        lines = []
        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"]
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)

    def get_facts_context(self, categories: List[str] = None) -> str:
        if categories:
            facts = {}
            for cat in categories:
                facts.update(self.memory.get_all_facts(cat))
        else:
            facts = self.memory.get_all_facts()
        
        if not facts:
            return ""
        
        lines = ["Facts:"]
        for key, value in facts.items():
            lines.append(f"- {key}: {value}")
        
        return "\n".join(lines)

    def get_recent_tool_results(self, session_id: str, limit: int = 5) -> str:
        history = self.memory.get_tool_history(session_id, limit)
        if not history:
            return ""
        
        lines = ["Recent tool results:"]
        for call in history[-limit:]:
            status = "OK" if call["success"] else "FAILED"
            result_preview = call["result"]
            if len(result_preview) > 100:
                result_preview = result_preview[:100] + "..."
            lines.append(f"- {call['tool_name']}: {status} - {result_preview}")
        
        return "\n".join(lines)

    def build_context(self, session_id: str) -> Dict[str, Any]:
        return {
            "conversation": self.get_conversation_context(session_id),
            "facts": self.get_facts_context(),
            "tool_history": self.get_recent_tool_results(session_id),
            "graph": self.get_graph_context(session_id),
            "raw_messages": self.memory.get_conversation(session_id, 20)
        }

    def get_graph_context(self, session_id: str, limit: int = 8) -> str:
        session_node = f"session:{session_id}"
        if not self.graph.get_node(session_node):
            return ""

        related = self.graph.get_related(session_node)[:limit]
        if not related:
            return ""

        lines = ["Graph context:"]
        for node in related:
            summary = node.data
            if isinstance(summary, dict):
                text = str(summary)[:120]
            else:
                text = str(summary)[:120]
            lines.append(f"- {node.type}: {text}")
        return "\n".join(lines)

    async def semantic_search(self, query: str, top_k: int = 5) -> str:
        """
        Search memory using semantic similarity.
        Returns formatted context string with relevant memories.
        """
        results = await self.memory.vectors.search_with_embedding(query, top_k)
        if not results:
            return ""

        lines = [f"Relevant memories (semantic search for: {query[:50]}...):"]
        for r in results:
            text = r['text']
            if len(text) > 200:
                text = text[:200] + "..."
            meta = r['metadata']
            source = meta.get('type', 'unknown')
            lines.append(f"- [{source}] {text}")

        return "\n".join(lines)

    async def build_context_with_semantic(self, session_id: str, goal: str = "") -> Dict[str, Any]:
        """Build context including semantic search for relevant memories."""
        base_context = self.build_context(session_id)

        # Add semantic search if goal provided
        if goal:
            semantic_memories = await self.semantic_search(goal, top_k=5)
            base_context["semantic_memories"] = semantic_memories

        return base_context
