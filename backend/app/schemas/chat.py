"""`/api/chat` 请求与响应契约（与设计 §4.7 对齐）。"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """非流式聊天请求。"""

    session_id: Optional[str] = None
    message: Annotated[str, Field(min_length=1, max_length=32_768)]


class VizSpec(BaseModel):
    chart_type: Literal["bar", "line", "pie", "scatter", "table"]
    title: Optional[str] = None
    x_field: Optional[str] = None
    y_field: Optional[str] = None
    category_field: Optional[str] = None
    value_field: Optional[str] = None


class TableData(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    #: 可选元信息（如结果被 LIMIT 裁剪），与 §4 Phase 4 对齐
    meta: Optional[dict[str, Any]] = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sql: Optional[str] = None
    table: TableData
    viz_spec: VizSpec
    #: 基于查询结果与业务规则生成的纯文本数据洞察（可选）
    viz_insight: Optional[str] = None
