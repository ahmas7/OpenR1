"""
R1 - Persistent Memory System
Stores conversations, user profiles, and learns from interactions
"""
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


MEMORY_DIR = Path("E:/MYAI/R1/data")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Conversation:
    id: str
    timestamp: str
    user_message: str
    ai_response: str
    context: Dict[str, Any]


@dataclass
class UserProfile:
    name: str
    first_seen: str
    last_seen: str
    preferences: Dict[str, Any]
    habits: List[str]
    important_dates: Dict[str, str]
    notes: str


class PersistentMemory:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(MEMORY_DIR / "orion_memory.db")
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                context TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                first_seen TEXT,
                last_seen TEXT,
                preferences TEXT,
                habits TEXT,
                important_dates TEXT,
                notes TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_key TEXT UNIQUE NOT NULL,
                fact_value TEXT NOT NULL,
                category TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills_learned (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT UNIQUE NOT NULL,
                description TEXT,
                examples TEXT,
                learned_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp 
            ON conversations(timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def save_conversation(self, user_msg: str, ai_msg: str, context: Dict = None):
        """Save a conversation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        conv_id = f"conv_{datetime.now().timestamp()}"
        timestamp = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
            (conv_id, timestamp, user_msg, ai_msg, json.dumps(context or {}))
        )
        
        conn.commit()
        conn.close()
        
        self._extract_facts(user_msg, ai_msg)
        return conv_id
    
    def _extract_facts(self, user_msg: str, ai_msg: str):
        """Extract facts from conversation"""
        facts = []
        
        name_match = user_msg.lower().replace("my name is", "").replace("i'm", "").replace("i am", "").strip()
        if name_match and len(name_match) < 30 and name_match.replace(" ", "").isalpha():
            facts.append(("user_name", name_match.title(), "personal"))
        
        location_words = ["i live in", "i'm from", "i stay in", "located in"]
        for word in location_words:
            if word in user_msg.lower():
                idx = user_msg.lower().find(word)
                loc = user_msg[idx + len(word):].strip().split()[0:2]
                if loc:
                    facts.append(("location", " ".join(loc), "personal"))
        
        import re
        email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', user_msg)
        if email_match:
            facts.append(("email", email_match.group(), "contact"))
        
        phone_match = re.search(r'\b\d{10,}\b', user_msg.replace(" ", ""))
        if phone_match:
            facts.append(("phone", phone_match.group(), "contact"))
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for fact_key, fact_value, category in facts:
            cursor.execute(
                "INSERT OR REPLACE INTO facts (fact_key, fact_value, category, created_at) VALUES (?, ?, ?, ?)",
                (fact_key, fact_value, category, datetime.now().isoformat())
            )
        
        conn.commit()
        conn.close()
    
    def get_conversations(self, limit: int = 50) -> List[Conversation]:
        """Get recent conversations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, timestamp, user_message, ai_response, context FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Conversation(
                id=row[0],
                timestamp=row[1],
                user_message=row[2],
                ai_response=row[3],
                context=json.loads(row[4]) if row[4] else {}
            )
            for row in rows
        ]
    
    def get_user_profile(self) -> UserProfile:
        """Get user profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_profile WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return UserProfile(
                name=row[1] or "Unknown",
                first_seen=row[2] or "",
                last_seen=row[3] or "",
                preferences=json.loads(row[4]) if row[4] else {},
                habits=json.loads(row[5]) if row[5] else [],
                important_dates=json.loads(row[6]) if row[6] else {},
                notes=row[7] or ""
            )
        
        return UserProfile(
            name="",
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            preferences={},
            habits=[],
            important_dates={},
            notes=""
        )
    
    def update_user_profile(self, profile: UserProfile):
        """Update user profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        profile.last_seen = datetime.now().isoformat()
        
        cursor.execute(
            """INSERT OR REPLACE INTO user_profile 
               (id, name, first_seen, last_seen, preferences, habits, important_dates, notes)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.name,
                profile.first_seen,
                profile.last_seen,
                json.dumps(profile.preferences),
                json.dumps(profile.habits),
                json.dumps(profile.important_dates),
                profile.notes
            )
        )
        
        conn.commit()
        conn.close()
    
    def search_conversations(self, query: str) -> List[Conversation]:
        """Search past conversations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT id, timestamp, user_message, ai_response, context 
               FROM conversations 
               WHERE user_message LIKE ? OR ai_response LIKE ?
               ORDER BY timestamp DESC LIMIT 20""",
            (f"%{query}%", f"%{query}%")
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Conversation(
                id=row[0],
                timestamp=row[1],
                user_message=row[2],
                ai_response=row[3],
                context=json.loads(row[4]) if row[4] else {}
            )
            for row in rows
        ]
    
    def get_facts(self, category: str = None) -> Dict[str, str]:
        """Get stored facts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute(
                "SELECT fact_key, fact_value FROM facts WHERE category = ?",
                (category,)
            )
        else:
            cursor.execute("SELECT fact_key, fact_value FROM facts")
        
        rows = cursor.fetchall()
        conn.close()
        
        return {row[0]: row[1] for row in rows}
    
    def learn_skill(self, skill_name: str, description: str, examples: List[str]):
        """Learn a new skill"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO skills_learned (skill_name, description, examples, learned_at) VALUES (?, ?, ?, ?)",
            (skill_name, description, json.dumps(examples), datetime.now().isoformat())
        )
        
        conn.commit()
        conn.close()
    
    def get_conversation_context(self, max_messages: int = 10) -> str:
        """Get conversation context for LLM"""
        convos = self.get_conversations(max_messages)
        
        if not convos:
            return ""
        
        context_parts = []
        for conv in reversed(convos):
            context_parts.append(f"User: {conv.user_message}")
            context_parts.append(f"Orion: {conv.ai_response}")
        
        return "\n".join(context_parts)
    
    def get_user_context(self) -> str:
        """Get user context for LLM"""
        profile = self.get_user_profile()
        facts = self.get_facts()
        
        context_parts = []
        
        if profile.name:
            context_parts.append(f"User's name: {profile.name}")
        
        for key, value in facts.items():
            context_parts.append(f"User {key}: {value}")
        
        return "\n".join(context_parts)


memory = PersistentMemory()
