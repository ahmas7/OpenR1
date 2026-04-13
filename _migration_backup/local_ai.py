"""
R1 - Self-Contained AI Engine
No external dependencies - works completely offline
"""
import re
import random
import json
from datetime import datetime
from typing import Dict, List, Optional


class SelfContainedAI:
    """
    A self-contained AI that works without Ollama or any external services.
    Uses pattern matching and rule-based responses for instant replies.
    """
    
    def __init__(self):
        self.name = "R1-Orion"
        self.version = "STABLE 2.0"
        self.conversation_count = 0
        self.user_name = None
        
        # Knowledge base - facts R1 knows
        self.knowledge = {
            "who are you": "I am R1, also known as Orion. I'm an advanced AI assistant built to help you with anything you need.",
            "what are you": "I'm R1, your personal AI assistant. Think of me as a modern version of JARVIS from Iron Man.",
            "your name": "My name is R1, but you can call me Orion.",
            "version": f"I am version {self.version}. Built for speed and efficiency.",
        }
        
        # Response patterns
        self.patterns = {
            # Greetings
            r"hi|hello|hey|howdy": [
                "Hello! I'm R1. What can I help you with today?",
                "Hey there! Orion at your service.",
                "Hi! I'm online and ready to assist.",
            ],
            # How are you
            r"how are you|how do you do": [
                "I'm doing great! Always ready to help.",
                "All systems optimal. How can I assist you?",
                "Running at full capacity. What's on your mind?",
            ],
            # Thanks
            r"thank|thanks|appreciate": [
                "You're welcome! Happy to help.",
                "Anytime! That's what I'm here for.",
                "My pleasure. Anything else you need?",
            ],
            # Goodbye
            r"bye|goodbye|see you|farewell": [
                "Goodbye! Talk to you soon.",
                "Until next time!",
                "Farewell! Don't hesitate to call on me again.",
            ],
            # Help
            r"help|what can you do|capabilities": [
                "I can: answer questions, run commands, manage files, check system status, send emails, browse the web, and much more!",
                "My abilities include: file management, system monitoring, code execution, web browsing, and intelligent conversation.",
            ],
            # System info
            r"cpu|memory|disk|system info|status": "system_info",
            r"time|what time": "time",
            r"date|today": "date",
            # Files
            r"list files|directory|folder": "list_dir",
            r"read file|cat|show file": "read_file",
            r"create file|write file": "write_file",
            r"delete file|remove file": "delete_file",
            # Commands
            r"run command|execute|shell": "run_shell",
            r"python|code|script": "run_code",
            # Weather (offline approximation)
            r"weather": [
                "I don't have internet access for live weather, but I can tell you it's a great day for coding!",
            ],
            # Jokes
            r"joke|funny": [
                "Why do programmers prefer dark mode? Because light attracts bugs!",
                "A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?'",
                "There are only 10 types of people in the world: those who understand binary and those who don't.",
            ],
            # Who created
            r"who made you|who created|your creator": [
                "I was created by the development team at Orion Industries.",
                "I was built from advanced AI technology.",
            ],
        }
        
    def process(self, message: str) -> str:
        """Process a message and return response"""
        self.conversation_count += 1
        message_lower = message.lower().strip()
        
        # Check for user name
        name_match = re.search(r"(?:my name is|i am|i'm)\s+(\w+)", message_lower)
        if name_match:
            self.user_name = name_match.group(1)
        
        # Check knowledge base first
        for key, value in self.knowledge.items():
            if key in message_lower:
                return value
        
        # Check patterns
        for pattern, response in self.patterns.items():
            if re.search(pattern, message_lower):
                if response == "system_info":
                    return self._get_system_info()
                elif response == "time":
                    return f"The current time is {datetime.now().strftime('%I:%M %p')}"
                elif response == "date":
                    return f"Today is {datetime.now().strftime('%B %d, %Y')}"
                elif response == "list_dir":
                    return "I can list directories. Tell me which folder you'd like to explore."
                elif response == "read_file":
                    return "I can read files. Tell me the file path."
                elif response == "write_file":
                    return "I can create files. Tell me what to write and where."
                elif response == "delete_file":
                    return "I can delete files. Be careful - tell me which file."
                elif response == "run_shell":
                    return "I can run shell commands. What would you like to execute?"
                elif response == "run_code":
                    return "I can execute Python code. What would you like me to run?"
                elif isinstance(response, list):
                    return random.choice(response)
        
        # Smart response for unknown queries
        return self._smart_response(message_lower)
    
    def _get_system_info(self) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return f"System Status:\n🖥️ CPU: {cpu}%\n💾 Memory: {mem.percent}%\n💿 Disk: {disk.percent}%"
        except:
            return "System monitoring unavailable."
    
    def _smart_response(self, message: str) -> str:
        """Generate smart responses for unrecognized queries"""
        
        # Questions
        if message.endswith('?') or 'what is' in message or 'how do' in message:
            responses = [
                f"That's an interesting question! As your AI assistant, I'm here to help with that.",
                f"I understand you're asking about that. Let me help you with that.",
                f"Great question! I'd be happy to assist with that.",
            ]
            return random.choice(responses)
        
        # Commands/instructions
        if any(w in message for w in ["please", "can you", "could you", "would you"]):
            return f"I'll help you with that. Give me a moment."
        
        # Default
        responses = [
            f"I understand. Let me help you with that.",
            f"Got it! Working on that now.",
            f"Sure thing! What would you like to know?",
            f"I'm listening. Tell me more.",
        ]
        return random.choice(responses)
    
    def get_status(self) -> Dict:
        """Get AI status"""
        return {
            "name": self.name,
            "version": self.version,
            "conversations": self.conversation_count,
            "user": self.user_name,
            "mode": "self-contained",
            "external_dependencies": "none"
        }


# Global instance
orion_ai = SelfContainedAI()


def get_orion_ai() -> SelfContainedAI:
    return orion_ai
