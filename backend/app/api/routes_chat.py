"""非流式聊天（Phase 3）。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def post_chat(request: Request, body: ChatRequest) -> ChatResponse:
    svc = getattr(request.app.state, "chat_service", None)
    if svc is None:
        raise HTTPException(status_code=500, detail="ChatService 未初始化")
    try:
        return await asyncio.to_thread(svc.run_chat, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
