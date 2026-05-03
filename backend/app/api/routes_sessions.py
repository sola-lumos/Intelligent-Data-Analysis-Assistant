"""会话 CRUD 与消息历史。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.schemas.session import MessageOut, SessionCreate, SessionOut, SessionPatch, VizInsightOut
from app.services import session_service
from app.services.viz_insight_service import generate_viz_insight

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions() -> list[SessionOut]:
    rows = session_service.list_sessions()
    return [SessionOut.model_validate(r) for r in rows]


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(payload: SessionCreate) -> SessionOut:
    row = session_service.create_session(title=payload.title)
    return SessionOut.model_validate(row)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(session_id: str) -> list[MessageOut]:
    if session_service.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    rows = session_service.list_messages(session_id)
    return [MessageOut.model_validate(r) for r in rows]


@router.post(
    "/sessions/{session_id}/messages/{message_id}/insight",
    response_model=VizInsightOut,
)
async def post_message_viz_insight(session_id: str, message_id: str) -> VizInsightOut:
    """按需生成助手某条消息的数据洞察（写入 ``assistant_meta.viz_insight``）。"""
    if not settings.dashscope_api_key:
        raise HTTPException(
            status_code=503,
            detail="未配置 DASHSCOPE_API_KEY，无法生成洞察",
        )
    if session_service.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    rows = session_service.list_messages(session_id)
    target: dict | None = None
    prev_user = ""
    for i, r in enumerate(rows):
        if r.get("id") != message_id:
            continue
        target = r
        for j in range(i - 1, -1, -1):
            if (rows[j].get("role") or "").strip() == "user":
                prev_user = str(rows[j].get("content") or "")
                break
        break

    if target is None:
        raise HTTPException(status_code=404, detail="消息不存在或不属于该会话")
    if (target.get("role") or "").strip() != "assistant":
        raise HTTPException(status_code=400, detail="仅支持助手消息的洞察生成")

    meta = target.get("assistant_meta")
    if not isinstance(meta, dict):
        raise HTTPException(status_code=400, detail="该消息无可用的 assistant_meta")
    table = meta.get("table")
    if not isinstance(table, dict) or not table.get("columns"):
        raise HTTPException(status_code=400, detail="该消息无可分析的结果表，请先完成一次查询")

    columns = list(table["columns"])
    row_data = list(table.get("rows") or [])
    truncated = bool((table.get("meta") or {}).get("truncated"))
    sql = target.get("sql_text")

    insight, insight_err = await asyncio.to_thread(
        generate_viz_insight,
        user_question=prev_user.strip() or "（无对应用户问题）",
        sql=sql if isinstance(sql, str) else None,
        columns=columns,
        rows=row_data,
        truncated=truncated,
    )
    if not insight or not str(insight).strip():
        raise HTTPException(
            status_code=503,
            detail=insight_err or "洞察生成失败或未返回内容，请稍后重试",
        )

    ok = session_service.merge_assistant_meta(message_id, {"viz_insight": insight})
    if not ok:
        raise HTTPException(status_code=500, detail="写入洞察失败")

    return VizInsightOut(viz_insight=insight)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def patch_session_endpoint(session_id: str, payload: SessionPatch) -> SessionOut:
    row = session_service.patch_session(session_id, title=payload.title)
    if row is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return SessionOut.model_validate(row)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_endpoint(session_id: str) -> Response:
    ok = session_service.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
