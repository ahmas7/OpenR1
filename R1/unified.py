"""
R1 - Unified System Integration
Combines all subsystems into a single cohesive AI assistant
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger("R1:unified")


class R1UnifiedSystem:
    def __init__(self):
        self.cognitive = None
        self.voice = None
        self.cybersecurity = None
        self.infrastructure = None
        self.analytics = None
        self.diagnostics = None
        self.decisions = None
        self.planning = None
        self.emergency = None
        
        self.initialized = False
        
    async def initialize(self):
        if self.initialized:
            return
        
        try:
            from R1.cognitive import get_cognitive_system
            self.cognitive = get_cognitive_system()
            logger.info("Cognitive system initialized")
        except Exception as e:
            logger.error(f"Cognitive init error: {e}")
        
        try:
            from R1.voice import get_voice_system
            self.voice = get_voice_system()
            await self.voice.initialize()
            logger.info("Voice system initialized")
        except Exception as e:
            logger.error(f"Voice init error: {e}")
        
        try:
            from R1.cybersecurity import get_cybersecurity_system
            self.cybersecurity = get_cybersecurity_system()
            await self.cybersecurity.initialize()
            logger.info("Cybersecurity system initialized")
        except Exception as e:
            logger.error(f"Cybersecurity init error: {e}")
        
        try:
            from R1.infrastructure import get_infrastructure_system
            self.infrastructure = get_infrastructure_system()
            logger.info("Infrastructure system initialized")
        except Exception as e:
            logger.error(f"Infrastructure init error: {e}")
        
        try:
            from R1.analytics import get_analytics_system
            self.analytics = get_analytics_system()
            logger.info("Analytics system initialized")
        except Exception as e:
            logger.error(f"Analytics init error: {e}")
        
        try:
            from R1.diagnostics import get_diagnostics_system
            self.diagnostics = get_diagnostics_system()
            logger.info("Diagnostics system initialized")
        except Exception as e:
            logger.error(f"Diagnostics init error: {e}")
        
        try:
            from R1.decisions import get_decision_system
            self.decisions = get_decision_system()
            logger.info("Decision system initialized")
        except Exception as e:
            logger.error(f"Decisions init error: {e}")
        
        try:
            from R1.planning import get_planning_system
            self.planning = get_planning_system()
            logger.info("Planning system initialized")
        except Exception as e:
            logger.error(f"Planning init error: {e}")
        
        try:
            from R1.emergency import get_emergency_system
            self.emergency = get_emergency_system()
            logger.info("Emergency system initialized")
        except Exception as e:
            logger.error(f"Emergency init error: {e}")
        
        self.initialized = True
        logger.info("R1 Unified System initialized")
    
    async def process_command(self, command: str, context: Dict = None) -> Dict:
        command_lower = command.lower()
        
        if any(w in command_lower for w in ["analyze", "reason", "think"]):
            if self.cognitive:
                return await self.cognitive.process(command, context.get("session_id", "default") if context else "default")
        
        if any(w in command_lower for w in ["speak", "voice", "say"]):
            if self.voice:
                text = command.replace("say", "").replace("speak", "").strip()
                await self.voice.respond(text)
                return {"success": True, "action": "speak", "text": text}
        
        if any(w in command_lower for w in ["security", "scan", "protect"]):
            if self.cybersecurity:
                if "scan" in command_lower:
                    path = context.get("path", ".") if context else "."
                    return self.cybersecurity.scan_for_malware(path)
                return {"success": True, "action": "security_check"}
        
        if any(w in command_lower for w in ["diagnose", "diagnostic", "check health"]):
            if self.diagnostics:
                return await self.diagnostics.run_diagnostics()
        
        if any(w in command_lower for w in ["predict", "forecast", "risk"]):
            if self.analytics:
                if "risk" in command_lower:
                    return self.analytics.analyze_risk("general", context or {} if context else {})
                return {"success": True, "action": "analytics"}
        
        if any(w in command_lower for w in ["device", "control", "automation"]):
            if self.infrastructure:
                return {"success": True, "action": "infrastructure"}
        
        if any(w in command_lower for w in ["plan", "mission", "schedule"]):
            if self.planning:
                return {"success": True, "action": "planning"}
        
        if any(w in command_lower for w in ["emergency", "shutdown", "alert"]):
            if self.emergency:
                if "shutdown" in command_lower:
                    return await self.emergency.emergency_shutdown("emergency" in command_lower)
                return {"success": True, "action": "emergency"}
        
        if any(w in command_lower for w in ["decide", "decision", "approve"]):
            if self.decisions:
                return await self.decisions.make_decision(command, context or {}, 3)
        
        return {
            "success": False,
            "message": "Command not recognized or system not available",
            "command": command
        }
    
    def get_system_status(self) -> Dict:
        return {
            "initialized": self.initialized,
            "systems": {
                "cognitive": self.cognitive is not None,
                "voice": self.voice is not None,
                "cybersecurity": self.cybersecurity is not None,
                "infrastructure": self.infrastructure is not None,
                "analytics": self.analytics is not None,
                "diagnostics": self.diagnostics is not None,
                "decisions": self.decisions is not None,
                "planning": self.planning is not None,
                "emergency": self.emergency is not None
            }
        }
    
    async def get_full_status(self) -> Dict:
        status = self.get_system_status()
        
        if self.diagnostics:
            try:
                status["health"] = await self.diagnostics.run_diagnostics()
            except:
                pass
        
        if self.emergency:
            try:
                status["emergency"] = self.emergency.get_system_status()
            except:
                pass
        
        return status


_r1_system: Optional[R1UnifiedSystem] = None

def get_r1_system() -> R1UnifiedSystem:
    global _r1_system
    if _r1_system is None:
        _r1_system = R1UnifiedSystem()
    return _r1_system


async def initialize_r1():
    system = get_r1_system()
    await system.initialize()
    return system
