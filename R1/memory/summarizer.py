"""
R1 v1 - Memory Summarizer
Compress conversation history into summaries.
"""
from typing import List, Dict
from .store import MemoryStore


class MemorySummarizer:
    def __init__(self, memory: MemoryStore):
        self.memory = memory

    def should_summarize(self, session_id: str, threshold: int = 30) -> bool:
        messages = self.memory.get_conversation(session_id, 100)
        return len(messages) >= threshold

    def summarize_conversation(self, session_id: str) -> str:
        messages = self.memory.get_conversation(session_id, 50)
        if not messages:
            return ""
        
        summary_parts = []
        
        user_msgs = [m["content"] for m in messages if m["role"] == "user"]
        if user_msgs:
            summary_parts.append(f"User discussed {len(user_msgs)} messages")
            summary_parts.append(f"Last user message: {user_msgs[-1][:100]}...")
        
        ai_msgs = [m["content"] for m in messages if m["role"] == "assistant"]
        if ai_msgs:
            summary_parts.append(f"AI responded {len(ai_msgs)} times")
        
        return " | ".join(summary_parts)
