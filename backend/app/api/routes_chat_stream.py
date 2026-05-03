"""流式对话（SSE，§4.6 主方案）。

**为何体感「慢」**

1. **首字节晚**：在 ``yield`` 任何 ``answer`` 之前必须先 ``await run_chat``。``run_chat`` 内部是
   LangGraph ReAct ``agent.invoke``（多轮 LLM + 工具），耗时常达数秒～数十秒，这段时间客户端只能等。
2. **打字机**：历史实现曾在每块 ``answer`` 后 ``sleep(0.015)``，长文会额外累积数秒；现已改为可配置
   ``sse_typing_delay_seconds``（默认 0）。
3. **网络**：DashScope API RTT 与模型推理时间不在本模块内优化。

缓解手段：下发 ``status`` 事件作占位；记录 ``run_chat`` 耗时日志；调小 ``sse_typing_delay_seconds``、
调大 ``sse_answer_chunk_chars``（见 ``Settings``）。
数据洞察改为用户在前端点击按钮后调用 ``POST .../insight`` 按需生成，不在此管道内阻塞。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.chat import ChatRequest

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """与 ``POST /api/chat`` 同款业务逻辑（``run_chat``），按事件推送 SSE。"""

    svc = getattr(request.app.state, "chat_service", None)
    if svc is None:
        raise HTTPException(status_code=500, detail="ChatService 未初始化")

    async def gen():
        chunk_size = max(1, int(settings.sse_answer_chunk_chars))
        typing_delay = max(0.0, float(settings.sse_typing_delay_seconds))
        try:
            yield _sse(
                "status",
                {
                    "phase": "invoke",
                    "message": "正在分析问题并调用 NL2SQL（完成后开始推送正文）…",
                },
            )

            t0 = time.perf_counter()
            chat_response = await asyncio.to_thread(svc.run_chat, body)
            elapsed = time.perf_counter() - t0
            ans = chat_response.answer or ""
            log.info(
                "SSE run_chat 结束 elapsed_s=%.3f answer_chars=%d session_id=%s",
                elapsed,
                len(ans),
                getattr(body, "session_id", None) or "",
            )
            if elapsed > 15.0:
                log.warning(
                    "SSE run_chat 耗时较长 elapsed_s=%.3f，多为 LLM/工具轮次或网络",
                    elapsed,
                )

            for i in range(0, len(ans), chunk_size):
                yield _sse(
                    "answer",
                    {"content": ans[i : i + chunk_size]},
                )
                if typing_delay > 0:
                    await asyncio.sleep(typing_delay)

            sql_text = chat_response.sql
            if sql_text:
                yield _sse("sql", {"sql": sql_text})

            yield _sse(
                "table",
                chat_response.table.model_dump(mode="json"),
            )
            yield _sse(
                "chart",
                {"viz_spec": chat_response.viz_spec.model_dump(mode="json")},
            )

            yield _sse(
                "done",
                {
                    "session_id": chat_response.session_id,
                    "message_id": chat_response.message_id,
                    "viz_insight": chat_response.viz_insight,
                },
            )
        except LookupError as exc:
            log.info("SSE chat 会话不存在 %s", exc)
            yield _sse(
                "error",
                {"message": str(exc), "code": "not_found"},
            )
        except ValueError as exc:
            log.info("SSE chat 不可用 %s", exc)
            yield _sse(
                "error",
                {"message": str(exc), "code": "service_unavailable"},
            )
        except Exception:  # noqa: BLE001
            log.exception("SSE chat_stream 异常")
            yield _sse(
                "error",
                {
                    "message": "服务端处理出错，请稍后重试",
                    "code": "internal_error",
                },
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )
