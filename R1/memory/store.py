"""
R1 v1 - Memory Store
Persistent memory with session, facts, and task history buckets.
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..memory_graph import get_memory_graph
from .embeddings import VectorMemory

logger = logging.getLogger("R1")


class MemoryStore:
    def __init__(self, db_path: str = ""):
        from ..config.settings import settings
        self.db_path = Path(db_path or settings.memory_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = get_memory_graph()

        # Vector memory for semantic search
        self.vectors = VectorMemory()

        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                value TEXT,
                category TEXT,
                updated_at TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                goal TEXT,
                plan TEXT,
                status TEXT,
                result TEXT,
                created_at TEXT,
                completed_at TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_history (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                tool_name TEXT,
                arguments TEXT,
                result TEXT,
                success INTEGER,
                timestamp TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    async def add_message(self, session_id: str, role: str, content: str):
        """Add message to memory store and index for semantic search."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        try:
            self.graph.add_conversation(content, role, session_id=session_id)
        except Exception as e:
            logger.debug(f"Memory graph add_message mirror failed: {e}")

        # Index for semantic search (non-blocking, fire-and-forget)
        try:
            await self.vectors.add(content, metadata={"session_id": session_id, "role": role, "type": "message"})
        except Exception as e:
            logger.debug(f"Vector indexing failed: {e}")

    def get_conversation(self, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        messages = [
            {"role": row[0], "content": row[1], "timestamp": row[2]}
            for row in cursor.fetchall()
        ]
        conn.close()
        return list(reversed(messages))

    async def set_fact(self, key: str, value: str, category: str = "general"):
        """Store a fact and index for semantic search."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO facts (key, value, category, updated_at) VALUES (?, ?, ?, ?)",
            (key, value, category, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        try:
            self.graph.add_fact(key, value, category=category)
        except Exception as e:
            logger.debug(f"Memory graph set_fact mirror failed: {e}")

        # Index for semantic search
        try:
            await self.vectors.add(
                f"{key}: {value}",
                metadata={"key": key, "category": category, "type": "fact"}
            )
        except Exception as e:
            logger.debug(f"Vector indexing failed: {e}")

    def get_fact(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT value FROM facts WHERE key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_all_facts(self, category: str = "") -> Dict[str, str]:
        conn = sqlite3.connect(self.db_path)
        if category:
            cursor = conn.execute("SELECT key, value FROM facts WHERE category = ?", (category,))
        else:
            cursor = conn.execute("SELECT key, value FROM facts")
        facts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return facts

    def save_task(self, session_id: str, goal: str, plan: Dict[str, Any], status: str):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO tasks (session_id, goal, plan, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, goal, json.dumps(plan), status, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        try:
            task_node = self.graph.add_task(goal, status=status, metadata={"plan": plan, "session_id": session_id})
            self.graph.link_nodes(f"session:{session_id}", task_node.id, "contains")
        except Exception as e:
            logger.debug(f"Memory graph save_task mirror failed: {e}")

    def update_task(self, session_id: str, goal: str, status: str, result: str = ""):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE tasks SET status = ?, result = ?, completed_at = ? WHERE session_id = ? AND goal = ?",
            (status, result, datetime.now().isoformat(), session_id, goal)
        )
        conn.commit()
        conn.close()
        try:
            self.graph.add_task(goal, status=status, metadata={"result": result, "session_id": session_id})
        except Exception as e:
            logger.debug(f"Memory graph update_task mirror failed: {e}")

    def get_tasks(self, session_id: str = "", status: str = "") -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        if session_id and status:
            cursor = conn.execute(
                "SELECT session_id, goal, plan, status, result, created_at, completed_at FROM tasks WHERE session_id = ? AND status = ?",
                (session_id, status)
            )
        elif session_id:
            cursor = conn.execute(
                "SELECT session_id, goal, plan, status, result, created_at, completed_at FROM tasks WHERE session_id = ?",
                (session_id,)
            )
        else:
            cursor = conn.execute(
                "SELECT session_id, goal, plan, status, result, created_at, completed_at FROM tasks"
            )
        
        tasks = [
            {
                "session_id": row[0],
                "goal": row[1],
                "plan": json.loads(row[2]) if row[2] else {},
                "status": row[3],
                "result": row[4],
                "created_at": row[5],
                "completed_at": row[6]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return tasks

    def add_tool_call(self, session_id: str, tool_name: str, arguments: Dict, result: str, success: bool):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO tool_history (session_id, tool_name, arguments, result, success, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, tool_name, json.dumps(arguments), result, 1 if success else 0, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        try:
            tool_node = self.graph.add_node(
                "tool_call",
                {
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result_preview": result[:500],
                    "success": success,
                },
                id=f"tool:{session_id}:{tool_name}:{hash(json.dumps(arguments, sort_keys=True))}",
            )
            self.graph.link_nodes(f"session:{session_id}", tool_node.id, "used")
        except Exception as e:
            logger.debug(f"Memory graph add_tool_call mirror failed: {e}")

    def get_tool_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT tool_name, arguments, result, success, timestamp FROM tool_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        history = [
            {
                "tool_name": row[0],
                "arguments": json.loads(row[1]) if row[1] else {},
                "result": row[2],
                "success": bool(row[3]),
                "timestamp": row[4]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return list(reversed(history))


_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
