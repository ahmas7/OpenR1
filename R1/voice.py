"""
R1 - Voice Interaction & Communication Systems
Natural language commands, dialogue, multi-language, speech-to-action
"""
import asyncio
import logging
import json
import hashlib
import base64
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import io

logger = logging.getLogger("R1:voice")


class VoiceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceCommand:
    id: str
    raw_text: str
    parsed_intent: Optional[str]
    entities: Dict[str, Any]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DialogueState:
    session_id: str
    turn_count: int = 0
    context_stack: List[Dict] = field(default_factory=list)
    pending_confirmations: List[str] = field(default_factory=list)
    last_intent: Optional[str] = None
    entities_collected: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class SpeechToText:
    def __init__(self):
        self.model = None
        self.initialized = False
        
    async def initialize(self):
        try:
            import whisper
            self.model = whisper.load_model("base")
            self.initialized = True
            logger.info("Speech-to-text initialized with Whisper")
        except Exception as e:
            logger.warning(f"Whisper not available: {e}")
            try:
                import speech_recognition as sr
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                self.initialized = True
                logger.info("Speech-to-text initialized with SpeechRecognition")
            except Exception as e2:
                logger.error(f"Speech recognition unavailable: {e2}")
    
    async def transcribe(self, audio_data: bytes, language: str = None) -> str:
        if not self.initialized:
            await self.initialize()
        
        try:
            if self.model:
                return await self._transcribe_whisper(audio_data, language)
            else:
                return await self._transcribe_fallback(audio_data)
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    async def _transcribe_whisper(self, audio_data: bytes, language: str = None) -> str:
        import whisper
        import numpy as np
        
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        result = self.model.transcribe(audio_np, language=language)
        return result.get("text", "").strip()
    
    async def _transcribe_fallback(self, audio_data: bytes) -> str:
        return "[Audio transcription unavailable]"


class TextToSpeech:
    def __init__(self):
        self.engine = None
        self.initialized = False
        self.voice_settings = {
            "rate": 150,
            "volume": 1.0,
            "voice": None
        }
        
    async def initialize(self):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)
            self.engine.setProperty('rate', self.voice_settings["rate"])
            self.initialized = True
            logger.info("TTS initialized with pyttsx3")
        except Exception as e:
            logger.warning(f"pyttsx3 not available: {e}")
            try:
                import edge_tts
                self.edge_tts = edge_tts
                self.initialized = True
                logger.info("TTS initialized with edge-tts")
            except Exception as e2:
                logger.warning(f"edge-tts not available: {e2}")
    
    async def speak(self, text: str, blocking: bool = False) -> bool:
        if not self.initialized:
            await self.initialize()
        
        if not text:
            return False
        
        try:
            if self.engine:
                if blocking:
                    self.engine.say(text)
                    self.engine.runAndWait()
                else:
                    self.engine.say(text)
                return True
            elif hasattr(self, 'edge_tts'):
                await self._speak_edge_tts(text)
                return True
            else:
                logger.warning("No TTS engine available")
                return False
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False
    
    async def _speak_edge_tts(self, text: str):
        import edge_tts
        communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    
    def set_voice_settings(self, rate: int = None, volume: float = None, voice: str = None):
        if rate:
            self.voice_settings["rate"] = rate
        if volume:
            self.voice_settings["volume"] = volume
        if voice:
            self.voice_settings["voice"] = voice
        
        if self.engine and rate:
            self.engine.setProperty('rate', rate)
        if self.engine and volume:
            self.engine.setProperty('volume', volume)


class VoiceCommandParser:
    def __init__(self):
        self.intent_patterns = {
            "search": [
                r"(?:search|find|look up|google)\s+(?:for\s+)?(.+)",
                r"what (?:is|are|was|were)\s+(.+)",
            ],
            "execute": [
                r"(?:run|execute|do|perform)\s+(.+)",
                r"start\s+(.+)",
            ],
            "create": [
                r"(?:create|make|build|generate)\s+(.+)",
                r"new\s+(.+)",
            ],
            "read": [
                r"(?:read|show|display|open)\s+(.+)",
                r"get\s+(.+)",
            ],
            "write": [
                r"(?:write|save|store|record)\s+(.+)",
                r"save\s+(?:as\s+)?(.+)",
            ],
            "delete": [
                r"(?:delete|remove|erase|clear)\s+(.+)",
            ],
            "send": [
                r"(?:send|email|message)\s+(?:to\s+)?(.+)",
            ],
            "call": [
                r"(?:call|phone|dial)\s+(.+)",
            ],
            "control": [
                r"(?:control|turn|set)\s+(?:the\s+)?(.+)",
                r"(?:open|close|start|stop)\s+(?:the\s+)?(.+)",
            ],
            "analyze": [
                r"(?:analyze|examine|review|check)\s+(.+)",
                r"what'?s?\s+(?:the\s+)?(?:status|state)\s+of\s+(.+)",
            ],
            "schedule": [
                r"(?:schedule|book|reserve)\s+(.+)",
                r"set\s+(?:a\s+)?(?:reminder|alarm)\s+(?:for\s+)?(.+)",
            ],
            "navigate": [
                r"(?:navigate|go to|open)\s+(?:the\s+)?(?:page|site|url)?\s*(.+)",
            ],
        }
        
        self.entity_extractors = {
            "time": self._extract_time,
            "date": self._extract_date,
            "duration": self._extract_duration,
            "number": self._extract_number,
            "path": self._extract_path,
            "url": self._extract_url,
            "email": self._extract_email,
        }
    
    def parse(self, text: str) -> VoiceCommand:
        text_clean = text.strip().lower()
        
        intent = self._detect_intent(text_clean)
        entities = self._extract_entities(text_clean)
        
        confidence = 0.8 if intent else 0.3
        
        command_id = hashlib.md5(f"{text}{datetime.now()}".encode()).hexdigest()[:12]
        
        return VoiceCommand(
            id=command_id,
            raw_text=text,
            parsed_intent=intent,
            entities=entities,
            confidence=confidence
        )
    
    def _detect_intent(self, text: str) -> Optional[str]:
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                import re
                if re.search(pattern, text):
                    return intent
        return None
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        entities = {}
        
        for entity_type, extractor in self.entity_extractors.items():
            result = extractor(text)
            if result:
                entities[entity_type] = result
        
        return entities
    
    def _extract_time(self, text: str) -> Optional[str]:
        import re
        patterns = [
            r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b',
            r'\b(at\s+)?(\d{1,2})\s*(?:o\'?clock)?\s*(am|pm)?\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(0)
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        date_refs = ["today", "tomorrow", "yesterday", "monday", "tuesday", 
                    "wednesday", "thursday", "friday", "saturday", "sunday"]
        for ref in date_refs:
            if ref in text.lower():
                return ref
        return None
    
    def _extract_duration(self, text: str) -> Optional[str]:
        import re
        patterns = [
            r'(\d+)\s*(?:second|sec)s?',
            r'(\d+)\s*(?:minute|min)s?',
            r'(\d+)\s*(?:hour|hr)s?',
            r'(\d+)\s*(?:day|days)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(0)
        return None
    
    def _extract_number(self, text: str) -> Optional[float]:
        import re
        match = re.search(r'\b(\d+(?:\.\d+)?)\b', text)
        if match:
            return float(match.group(1))
        return None
    
    def _extract_path(self, text: str) -> Optional[str]:
        import re
        patterns = [
            r'(?:in|at|from)\s+([/\\][\w\s./\\-]+)',
            r'([C-Z]:[/\\][\w\s./\\-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_url(self, text: str) -> Optional[str]:
        import re
        match = re.search(r'https?://[^\s]+', text)
        if match:
            return match.group(0)
        return None
    
    def _extract_email(self, text: str) -> Optional[str]:
        import re
        match = re.search(r'[\w.-]+@[\w.-]+\.\w+', text)
        if match:
            return match.group(0)
        return None


class DialogueEngine:
    def __init__(self):
        self.sessions: Dict[str, DialogueState] = {}
        self.conversation_handlers: Dict[str, Callable] = {}
        
    def create_session(self, session_id: str = None) -> DialogueState:
        if not session_id:
            session_id = str(uuid.uuid4())
        
        state = DialogueState(session_id=session_id)
        self.sessions[session_id] = state
        return state
    
    def get_session(self, session_id: str) -> Optional[DialogueState]:
        return self.sessions.get(session_id)
    
    def update_turn(self, session_id: str, user_input: str, intent: str, entities: Dict = None):
        state = self.sessions.get(session_id)
        if not state:
            state = self.create_session(session_id)
        
        state.turn_count += 1
        state.last_intent = intent
        
        if entities:
            state.entities_collected.update(entities)
        
        state.context_stack.append({
            "turn": state.turn_count,
            "input": user_input,
            "intent": intent,
            "entities": entities or {},
            "timestamp": datetime.now().isoformat()
        })
        
        if len(state.context_stack) > 10:
            state.context_stack = state.context_stack[-10:]
        
        return state
    
    def add_confirmation(self, session_id: str, confirmation_text: str):
        state = self.sessions.get(session_id)
        if state:
            state.pending_confirmations.append(confirmation_text)
    
    def get_pending_confirmation(self, session_id: str) -> Optional[str]:
        state = self.sessions.get(session_id)
        if state and state.pending_confirmations:
            return state.pending_confirmations[0]
        return None
    
    def clear_confirmation(self, session_id: str):
        state = self.sessions.get(session_id)
        if state:
            state.pending_confirmations.pop(0, None)
    
    def get_context_summary(self, session_id: str) -> Dict:
        state = self.sessions.get(session_id)
        if not state:
            return {}
        
        return {
            "session_id": session_id,
            "turns": state.turn_count,
            "current_intent": state.last_intent,
            "collected_entities": state.entities_collected,
            "pending_confirmations": len(state.pending_confirmations),
            "recent_context": state.context_stack[-3:]
        }


class MultiLanguageSupport:
    def __init__(self):
        self.supported_languages = {
            "en": "English",
            "es": "Spanish", 
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic",
            "ru": "Russian",
            "hi": "Hindi"
        }
        self.language_detection_enabled = True
        
    def detect_language(self, text: str) -> str:
        try:
            import langdetect
            detected = langdetect.detect(text)
            return detected
        except ImportError:
            return "en"
        except Exception:
            return "en"
    
    def is_supported(self, language_code: str) -> bool:
        return language_code in self.supported_languages
    
    def get_language_name(self, code: str) -> str:
        return self.supported_languages.get(code, "Unknown")
    
    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source=from_lang, target=to_lang)
            return translator.translate(text)
        except ImportError:
            logger.warning("deep_translator not available for translation")
            return text
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text


class VoiceAuthenticator:
    def __init__(self):
        self.enrolled_users: Dict[str, Dict] = {}
        self.embedding_model = None
        
    async def enroll(self, user_id: str, voice_sample: bytes, metadata: Dict = None) -> bool:
        try:
            embedding = await self._extract_embedding(voice_sample)
            
            self.enrolled_users[user_id] = {
                "embedding": embedding,
                "metadata": metadata or {},
                "enrolled_at": datetime.now().isoformat()
            }
            
            logger.info(f"Voice enrolled for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Voice enrollment error: {e}")
            return False
    
    async def verify(self, user_id: str, voice_sample: bytes) -> float:
        if user_id not in self.enrolled_users:
            return 0.0
        
        try:
            embedding = await self._extract_embedding(voice_sample)
            stored_embedding = self.enrolled_users[user_id]["embedding"]
            
            similarity = self._cosine_similarity(embedding, stored_embedding)
            
            return similarity
        except Exception as e:
            logger.error(f"Voice verification error: {e}")
            return 0.0
    
    async def _extract_embedding(self, audio_data: bytes) -> List[float]:
        import numpy as np
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        embedding = np.random.randn(128).tolist()
        
        return embedding
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        import numpy as np
        a = np.array(a)
        b = np.array(b)
        
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot / (norm_a * norm_b))


class SpeechToActionPipeline:
    def __init__(self):
        self.command_parser = VoiceCommandParser()
        self.action_registry: Dict[str, Callable] = {}
        
    def register_action(self, intent: str, handler: Callable):
        self.action_registry[intent] = handler
    
    async def execute(self, text: str, context: Dict = None) -> Dict:
        command = self.command_parser.parse(text)
        
        if not command.parsed_intent:
            return {
                "success": False,
                "message": "Could not understand command",
                "original_text": text
            }
        
        if command.parsed_intent in self.action_registry:
            handler = self.action_registry[command.parsed_intent]
            
            try:
                result = await handler(command.entities, context or {})
                
                return {
                    "success": True,
                    "intent": command.parsed_intent,
                    "entities": command.entities,
                    "result": result
                }
            except Exception as e:
                logger.error(f"Action execution error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "intent": command.parsed_intent
                }
        else:
            return {
                "success": False,
                "message": f"No handler for intent: {command.parsed_intent}",
                "intent": command.parsed_intent
            }


class EncryptedAudioRelay:
    def __init__(self):
        self.key = None
        self.algorithm = "AES-256-GCM"
        
    def initialize(self, key: bytes = None):
        if key:
            self.key = key
        else:
            import os
            self.key = os.urandom(32)
    
    def encrypt_audio(self, audio_data: bytes) -> bytes:
        if not self.key:
            self.initialize()
        
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            import os
            
            iv = os.urandom(16)
            
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            ciphertext = encryptor.update(audio_data) + encryptor.finalize()
            
            return iv + encryptor.tag + ciphertext
        except ImportError:
            logger.warning("cryptography not available, returning unencrypted")
            return audio_data
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return audio_data
    
    def decrypt_audio(self, encrypted_data: bytes) -> bytes:
        if not self.key:
            return encrypted_data
        
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            iv = encrypted_data[:16]
            tag = encrypted_data[16:32]
            ciphertext = encrypted_data[32:]
            
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            return decryptor.update(ciphertext) + decryptor.finalize()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return b""


class BriefingGenerator:
    def __init__(self):
        self.template_vars = {}
        
    def generate(self, briefing_type: str, data: Dict) -> str:
        if briefing_type == "status":
            return self._generate_status_briefing(data)
        elif briefing_type == "summary":
            return self._generate_summary_briefing(data)
        elif briefing_type == "alert":
            return self._generate_alert_briefing(data)
        elif briefing_type == "schedule":
            return self._generate_schedule_briefing(data)
        else:
            return self._generate_generic_briefing(data)
    
    def _generate_status_briefing(self, data: Dict) -> str:
        system = data.get("system", "R1")
        status = data.get("status", "operational")
        uptime = data.get("uptime", "unknown")
        
        return f"System status report. {system} is currently {status}. Uptime: {uptime}."
    
    def _generate_summary_briefing(self, data: Dict) -> str:
        summary = data.get("summary", "No summary available")
        key_points = data.get("key_points", [])
        
        briefing = f"Summary: {summary}"
        
        if key_points:
            briefing += " Key points: "
            briefing += ". ".join(key_points)
        
        return briefing
    
    def _generate_alert_briefing(self, data: Dict) -> str:
        alert_level = data.get("level", "info")
        message = data.get("message", "")
        
        prefix = {
            "critical": "Critical alert:",
            "warning": "Warning:",
            "info": "Notice:"
        }.get(alert_level, "Alert:")
        
        return f"{prefix} {message}"
    
    def _generate_schedule_briefing(self, data: Dict) -> str:
        events = data.get("events", [])
        
        if not events:
            return "No upcoming events scheduled."
        
        briefing = "Your schedule: "
        for event in events[:5]:
            time = event.get("time", "TBD")
            title = event.get("title", "Event")
            briefing += f"At {time}, {title}. "
        
        return briefing
    
    def _generate_generic_briefing(self, data: Dict) -> str:
        return f"Briefing: {json.dumps(data)}"


class VoiceInteractionSystem:
    def __init__(self, memory_module=None):
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.parser = VoiceCommandParser()
        self.dialogue = DialogueEngine()
        self.languages = MultiLanguageSupport()
        self.auth = VoiceAuthenticator()
        self.pipeline = SpeechToActionPipeline()
        self.encryptor = EncryptedAudioRelay()
        self.briefing = BriefingGenerator()
        self.state = VoiceState.IDLE
        self.microphone_active = False
        
    async def initialize(self):
        await self.stt.initialize()
        await self.tts.initialize()
        
    async def listen(self, audio_data: bytes) -> str:
        self.state = VoiceState.LISTENING
        
        text = await self.stt.transcribe(audio_data)
        
        self.state = VoiceState.IDLE
        return text
    
    async def process_command(self, text: str, session_id: str = "default") -> Dict:
        self.state = VoiceState.PROCESSING
        
        command = self.parser.parse(text)
        
        self.dialogue.update_turn(
            session_id,
            text,
            command.parsed_intent,
            command.entities
        )
        
        result = await self.pipeline.execute(text, {
            "session_id": session_id,
            "entities": command.entities
        })
        
        self.state = VoiceState.IDLE
        return result
    
    async def respond(self, text: str, blocking: bool = False) -> bool:
        self.state = VoiceState.SPEAKING
        
        success = await self.tts.speak(text, blocking=blocking)
        
        self.state = VoiceState.IDLE
        return success
    
    async def full_interaction(self, audio_data: bytes, session_id: str = "default") -> Dict:
        text = await self.listen(audio_data)
        
        if not text:
            return {
                "success": False,
                "message": "Could not understand audio"
            }
        
        result = await self.process_command(text, session_id)
        
        response_text = result.get("message") or "Command processed"
        
        await self.respond(response_text)
        
        return {
            "transcribed": text,
            "result": result
        }
    
    def register_command_handler(self, intent: str, handler: Callable):
        self.pipeline.register_action(intent, handler)


_voice_system: Optional[VoiceInteractionSystem] = None

def get_voice_system(memory_module=None) -> VoiceInteractionSystem:
    global _voice_system
    if _voice_system is None:
        _voice_system = VoiceInteractionSystem(memory_module)
    return _voice_system
