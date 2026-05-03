"""会话与历史消息契约。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = Field(default="新会话", min_length=1, max_length=200)


class SessionPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    title: str
    created_at: int
    updated_at: int


class MessageOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    session_id: str
    role: str
    content: str
    sql_text: Optional[str] = None
    assistant_meta: Optional[dict] = None
    created_at: int


class VizInsightOut(BaseModel):
    viz_insight: str
