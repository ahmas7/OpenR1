"""
R1 v1 - Session Manager
Manages per-session state.
"""
import logging
from typing import Dict, Optional
from .state import AgentState, AgentStatus

logger = logging.getLogger("R1")


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, AgentState] = {}

    def create_session(self, session_id: str) -> AgentState:
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        state = AgentState(session_id=session_id)
        self._sessions[session_id] = state
        logger.info(f"Created session: {session_id}")
        return state

    def get_session(self, session_id: str) -> Optional[AgentState]:
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: str) -> AgentState:
        if session_id not in self._sessions:
            return self.create_session(session_id)
        return self._sessions[session_id]

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Removed session: {session_id}")

    def list_sessions(self) -> Dict[str, AgentStatus]:
        return {
            sid: state.status 
            for sid, state in self._sessions.items()
        }

    def clear(self):
        self._sessions.clear()
        logger.info("Cleared all sessions")
