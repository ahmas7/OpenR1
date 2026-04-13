"""
R1 API Schemas
Request and response models for the API layer.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: str = Field(default="default", description="Session identifier")


class ChatResponse(BaseModel):
    response: str
    session_id: str
    provider: str


class AgentRunRequest(BaseModel):
    goal: str = Field(..., description="Goal for agent to accomplish")
    session_id: str = Field(default="default", description="Session identifier")


class AgentStatusResponse(BaseModel):
    session_id: str
    status: str
    goal: str
    plan: Dict[str, Any]
    iteration: int
    last_action: Optional[str] = None
    last_result: Optional[Any] = None
    error: Optional[str] = None


class AgentStopResponse(BaseModel):
    success: bool
    session_id: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    provider: str
    model_health: Dict[str, Any]


class ProviderInfo(BaseModel):
    id: str
    name: str
    healthy: bool
    reason: Optional[str] = None


class ProvidersResponse(BaseModel):
    active_provider: str
    providers: List[ProviderInfo]


class ToolsResponse(BaseModel):
    tools: List[str]


class SkillsResponse(BaseModel):
    skills: List[Dict[str, Any]]


class SkillActionRequest(BaseModel):
    name: str = Field(..., description="Skill name")


class SkillLoadRequest(SkillActionRequest):
    pass


class SkillUnloadRequest(SkillActionRequest):
    pass


class SkillReloadRequest(SkillActionRequest):
    pass


class SkillInvokeRequest(BaseModel):
    name: str = Field(..., description="Skill name")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context for skill")


class SkillActionResponse(BaseModel):
    success: bool
    name: str


class SkillInvokeResponse(BaseModel):
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class SkillValidateRequest(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    entrypoint: str = "main.py"
    triggers: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    source: str = "local"


class SkillValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    manifest: Optional[Dict[str, Any]] = None


class MemoryResponse(BaseModel):
    conversation: List[Dict[str, Any]]
    facts: Dict[str, Any]
    tool_history: List[Dict[str, Any]]


class MemoryRememberRequest(BaseModel):
    key: str
    value: str
    category: str = "general"


class MemoryRecallResponse(BaseModel):
    key: str
    value: Optional[str] = None


class SessionInfo(BaseModel):
    session_id: str
    status: str
    goal: str
    iteration: int


class SessionsResponse(BaseModel):
    sessions: List[SessionInfo]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class StackTrainRequest(BaseModel):
    engine: str = Field(default="pytorch", description="Training engine: pytorch or jax")
    run_data_job: bool = Field(default=True, description="Run Spark data prep before training")
    epochs: int = Field(default=200, description="Training epochs")
    lr: float = Field(default=0.05, description="Learning rate")
    rows: int = Field(default=2000, description="Synthetic rows if no data")


class StackTrainResponse(BaseModel):
    success: bool
    output: Optional[Dict[str, Any]] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class StackInferRequest(BaseModel):
    features: List[float]


class StackInferResponse(BaseModel):
    prediction: float


class StackStatusResponse(BaseModel):
    available: bool
    allow_run: bool
    data_job: str
    train_pytorch: str
    train_jax: str
    rust_infer_url: str


# ==================== JOBS SCHEMAS ====================

class JobInfoResponse(BaseModel):
    id: str
    name: str
    interval_seconds: int = 0
    cron_expr: Optional[str] = None
    enabled: bool
    last_run: Optional[str] = None
    last_error: Optional[str] = None
    run_count: int = 0
    running: bool = False


class JobsListResponse(BaseModel):
    jobs: List[JobInfoResponse]


class JobActionResponse(BaseModel):
    success: bool
    job_id: str
    message: str = ""


# ==================== AUDIT SCHEMAS ====================

class AuditEntryResponse(BaseModel):
    timestamp: str
    tool_name: str
    arguments: Dict[str, Any]
    success: bool
    output_preview: str
    error: str = ""


class AuditListResponse(BaseModel):
    entries: List[AuditEntryResponse]
    total: int = 0


# ==================== REMINDERS SCHEMAS ====================

class ReminderCreateRequest(BaseModel):
    session_id: str = Field(default="default", description="Session to deliver reminder to")
    text: str = Field(..., description="Reminder text")
    due_at: str = Field(..., description="ISO 8601 datetime when the reminder is due")


class ReminderResponse(BaseModel):
    id: str
    session_id: str
    text: str
    due_at: str
    created_at: str
    delivered: bool = False
    delivered_at: Optional[str] = None


class RemindersListResponse(BaseModel):
    reminders: List[ReminderResponse]


class ReminderCancelResponse(BaseModel):
    success: bool
    id: str

