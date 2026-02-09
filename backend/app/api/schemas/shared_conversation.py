"""Shared conversation schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SharedConversationCreate(BaseModel):
    """Schema for creating a shared conversation."""

    request_id: UUID
    privacy: str = Field(default="unlisted", pattern="^(public|private|unlisted)$")


class SharedConversationUpdate(BaseModel):
    """Schema for updating a shared conversation."""

    privacy: Optional[str] = Field(None, pattern="^(public|private|unlisted)$")
    is_active: Optional[bool] = None


class SharedConversationResponse(BaseModel):
    """Schema for shared conversation response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    share_id: str
    privacy: str
    view_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    share_url: str


class PublicConversationResponse(BaseModel):
    """Schema for public conversation view."""

    model_config = ConfigDict(from_attributes=True)

    share_id: str
    content: str
    response_content: str
    confidence: float
    execution_time: float
    total_cost: float
    models_used: list
    execution_mode: str
    created_at: datetime
    view_count: int
