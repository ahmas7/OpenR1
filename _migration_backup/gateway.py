"""
R1 - Gateway Server
WebSocket-based control plane with sessions, presence, and CLI
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime
from enum import Enum
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger("R1:gateway")


class SessionState(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"


@dataclass
class Session:
    id: str
    name: str
    agent_id: str
    created_at: str
    last_active: str
    state: SessionState = SessionState.ACTIVE
    channel: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Agent:
    id: str
    name: str
    model: str = "mistral:latest"
    skills: List[str] = field(default_factory=list)
    persona: Optional[str] = None
    tools: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayConfig:
    host: str = "0.0.0.0"
    port: int = 18789
    ws_path: str = "/ws"
    api_port: int = 8080
    sessions_dir: Optional[str] = None
    config_dir: Optional[str] = None
    verbose: bool = False


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": datetime.now().isoformat(),
            "messages_sent": 0,
            "messages_received": 0,
        }
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
    
    async def send_message(self, client_id: str, message: Dict[str, Any]):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
            self.connection_metadata[client_id]["messages_sent"] += 1
    
    async def broadcast(self, message: Dict[str, Any], exclude: Optional[Set[str]] = None):
        for client_id, websocket in self.active_connections.items():
            if exclude and client_id in exclude:
                continue
            await websocket.send_json(message)
    
    async def send_raw(self, client_id: str, data: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(data)
    
    def get_connection_count(self) -> int:
        return len(self.active_connections)


class Gateway:
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        self.app = FastAPI(title="R1 Gateway", version="1.0.0")
        self.conn_manager = ConnectionManager()
        self.sessions: Dict[str, Session] = {}
        self.agents: Dict[str, Agent] = {}
        self._running = False
        self._message_handler: Optional[Callable] = None
        self._server = None
        
        self._setup_middleware()
        self._setup_routes()
    
    def _setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "connections": self.conn_manager.get_connection_count(),
                "sessions": len(self.sessions),
                "agents": len(self.agents),
            }
        
        @self.app.get("/")
        async def root():
            return {
                "name": "R1 Gateway",
                "version": "1.0.0",
                "docs": "/docs",
            }
        
        @self.app.websocket(self.config.ws_path)
        async def websocket_endpoint(websocket: WebSocket):
            client_id = str(uuid.uuid4())
            await self.conn_manager.connect(websocket, client_id)
            
            try:
                await websocket.send_json({
                    "type": "connected",
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat(),
                })
                
                while True:
                    data = await websocket.receive_text()
                    self.conn_manager.connection_metadata[client_id]["messages_received"] += 1
                    await self._handle_message(client_id, data)
                    
            except WebSocketDisconnect:
                self.conn_manager.disconnect(client_id)
                logger.info(f"Client {client_id} disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.conn_manager.disconnect(client_id)
        
        @self.app.get("/sessions")
        async def list_sessions():
            return {"sessions": [self._session_to_dict(s) for s in self.sessions.values()]}
        
        @self.app.post("/sessions")
        async def create_session(request: Request):
            body = await request.json()
            session = Session(
                id=str(uuid.uuid4()),
                name=body.get("name", "main"),
                agent_id=body.get("agent_id", "default"),
                created_at=datetime.now().isoformat(),
                last_active=datetime.now().isoformat(),
            )
            self.sessions[session.id] = session
            return {"session": self._session_to_dict(session)}
        
        @self.app.get("/sessions/{session_id}")
        async def get_session(session_id: str):
            if session_id not in self.sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            return {"session": self._session_to_dict(self.sessions[session_id])}
        
        @self.app.delete("/sessions/{session_id}")
        async def delete_session(session_id: str):
            if session_id in self.sessions:
                del self.sessions[session_id]
                return {"success": True}
            raise HTTPException(status_code=404, detail="Session not found")
        
        @self.app.get("/agents")
        async def list_agents():
            return {"agents": [self._agent_to_dict(a) for a in self.agents.values()]}
        
        @self.app.post("/agents")
        async def create_agent(request: Request):
            body = await request.json()
            agent = Agent(
                id=str(uuid.uuid4()),
                name=body.get("name", "default"),
                model=body.get("model", "mistral:latest"),
                skills=body.get("skills", []),
                persona=body.get("persona"),
                tools=body.get("tools", []),
                config=body.get("config", {}),
            )
            self.agents[agent.id] = agent
            return {"agent": self._agent_to_dict(agent)}
        
        @self.app.get("/agents/{agent_id}")
        async def get_agent(agent_id: str):
            if agent_id not in self.agents:
                raise HTTPException(status_code=404, detail="Agent not found")
            return {"agent": self._agent_to_dict(self.agents[agent_id])}
        
        @self.app.post("/message/send")
        async def send_message(request: Request):
            body = await request.json()
            to = body.get("to", "")
            message = body.get("message", "")
            
            await self.conn_manager.send_message(to, {
                "type": "message",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            })
            
            return {"success": True}
        
        @self.app.post("/broadcast")
        async def broadcast_message(request: Request):
            body = await request.json()
            message = body.get("message", "")
            
            await self.conn_manager.broadcast({
                "type": "broadcast",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            })
            
            return {"success": True}
    
    async def _handle_message(self, client_id: str, data: str):
        try:
            message = json.loads(data)
            msg_type = message.get("type", "unknown")
            
            if msg_type == "ping":
                await self.conn_manager.send_message(client_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                })
            
            elif msg_type == "chat":
                if self._message_handler:
                    response = await self._message_handler(message)
                    await self.conn_manager.send_message(client_id, {
                        "type": "response",
                        "content": response.get("content", ""),
                        "timestamp": datetime.now().isoformat(),
                    })
            
            elif msg_type == "typing":
                await self.conn_manager.broadcast({
                    "type": "typing",
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat(),
                }, exclude={client_id})
            
            elif msg_type == "session_update":
                session_id = message.get("session_id")
                if session_id in self.sessions:
                    session = self.sessions[session_id]
                    session.last_active = datetime.now().isoformat()
                    if "state" in message:
                        session.state = SessionState(message["state"])
            
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from client {client_id}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def _session_to_dict(self, session: Session) -> Dict[str, Any]:
        return {
            "id": session.id,
            "name": session.name,
            "agent_id": session.agent_id,
            "created_at": session.created_at,
            "last_active": session.last_active,
            "state": session.state.value,
            "channel": session.channel,
            "metadata": session.metadata,
        }
    
    def _agent_to_dict(self, agent: Agent) -> Dict[str, Any]:
        return {
            "id": agent.id,
            "name": agent.name,
            "model": agent.model,
            "skills": agent.skills,
            "persona": agent.persona,
            "tools": agent.tools,
            "config": agent.config,
        }
    
    def set_message_handler(self, handler: Callable):
        self._message_handler = handler
    
    async def start(self):
        self._running = True
        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.api_port,
            log_level="info" if self.config.verbose else "warning",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()
    
    async def stop(self):
        self._running = False
        if self._server:
            self._server.should_exit = True
    
    def is_running(self) -> bool:
        return self._running


class GatewayCLI:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway
    
    async def send_message(self, to: str, message: str):
        await self.gateway.conn_manager.send_message(to, {
            "type": "message",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
    
    async def broadcast(self, message: str):
        await self.gateway.conn_manager.broadcast({
            "type": "broadcast",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
    
    async def create_session(self, name: str = "main", agent_id: str = "default") -> Session:
        session = Session(
            id=str(uuid.uuid4()),
            name=name,
            agent_id=agent_id,
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat(),
        )
        self.gateway.sessions[session.id] = session
        return session
    
    def list_sessions(self) -> List[Session]:
        return list(self.gateway.sessions.values())
    
    def get_session(self, session_id: str) -> Optional[Session]:
        return self.gateway.sessions.get(session_id)
    
    async def delete_session(self, session_id: str) -> bool:
        if session_id in self.gateway.sessions:
            del self.gateway.sessions[session_id]
            return True
        return False


class PresenceManager:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway
        self.presence: Dict[str, Dict[str, Any]] = {}
    
    async def update_presence(self, client_id: str, status: str, detail: str = ""):
        self.presence[client_id] = {
            "status": status,
            "detail": detail,
            "updated_at": datetime.now().isoformat(),
        }
        
        await self.gateway.conn_manager.broadcast({
            "type": "presence_update",
            "client_id": client_id,
            "presence": self.presence[client_id],
            "timestamp": datetime.now().isoformat(),
        })
    
    def get_presence(self, client_id: str) -> Optional[Dict[str, Any]]:
        return self.presence.get(client_id)
    
    def get_all_presence(self) -> Dict[str, Dict[str, Any]]:
        return self.presence.copy()
