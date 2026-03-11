"""Pydantic models shared across all agents - source of truth for inter-service communication."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActivityLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Plan(BaseModel):
    """Message from coordinator to agent - task to execute."""

    id: str
    objective_id: str
    agent_type: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Result(BaseModel):
    """Result from agent to coordinator - task completion status."""

    plan_id: str
    agent_type: str
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationRequest(BaseModel):
    """Request from agent to coordinator - needs human approval."""

    id: str
    plan_id: str
    agent_type: str
    action: str
    description: str
    data: dict[str, Any] | None = None
    expires_at: datetime
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationResponse(BaseModel):
    """Response from coordinator to agent - approval decision."""

    validation_id: str
    approved: bool
    response: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ActivityReport(BaseModel):
    """Activity log from agent to coordinator - for activity feed."""

    agent_type: str
    action: str
    message: str
    data: dict[str, Any] | None = None
    level: ActivityLevel = ActivityLevel.INFO
    timestamp: datetime = Field(default_factory=datetime.utcnow)
