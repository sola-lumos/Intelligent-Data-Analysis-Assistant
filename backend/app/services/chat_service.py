"""编排 NL2SQL、SQLGuard、结果表与可视化元数据（Phase 3）。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, TableData, VizSpec
from app.services import nl2sql, session_service, viz_service
from app.services import query_service

log = logging.getLogger(__name__)

_RECURSION_LIMIT = 42


def _tool_call_name(tc: Any) -> str:
    if hasattr(tc, "name"):
        return str(getattr(tc, "name", "") or "")
    if isinstance(tc, dict):
        return str(tc.get("name") or "")
    return ""


def _tool_call_args(tc: Any) -> Any:
    if hasattr(tc, "args"):
        return getattr(tc, "args", {})
    if isinstance(tc, dict):
        return tc.get("args") or tc.get("function") or {}
    return {}


def _normalize_query(args: Any) -> str | None:
    if args is None:
        return None
    if isinstance(args, str):
        s = args.strip()
        return s or None
    if isinstance(args, dict):
        q = args.get("query")
        if isinstance(q, str):
            qs = q.strip()
            return qs or None
    return None


def extract_last_sql(messages: list[BaseMessage]) -> str | None:
    last: str | None = None
    for msg in messages:
        if isinstance(msg, AIMessage):
            tcs = msg.tool_calls or []
            for tc in tcs:
                if _tool_call_name(tc) != "sql_db_query":
                    continue
                query = _normalize_query(_tool_call_args(tc))
                if query:
                    last = query
    return last


def extract_final_answer(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""


def _messages_to_lc(rows: list[dict[str, Any]]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for r in rows:
        role = (r.get("role") or "").strip()
        body = str(r.get("content") or "")
        if role == "user":
            out.append(HumanMessage(content=body))
        elif role == "assistant":
            out.append(AIMessage(content=body))
    return out


class ChatService:
    """同步 ``run_chat``，由路由经 ``asyncio.to_thread`` 调度。"""

    def __init__(self, *, sqlalchemy_uri: str | None = None) -> None:
        self._sqlalchemy_uri = sqlalchemy_uri
        self._agent = None
        self._cached_nl2sql_revision: int | None = None

    def _ensure_agent(self) -> Any:
        rev = int(getattr(nl2sql, "NL2SQL_PROMPT_REVISION", 0))
        stale = (
            self._agent is None
            or self._cached_nl2sql_revision is None
            or self._cached_nl2sql_revision != rev
        )
        if stale:
            self._agent = nl2sql.build_nl2sql_agent(
                sqlalchemy_uri=self._sqlalchemy_uri,
                streaming=False,
            )
            self._cached_nl2sql_revision = rev
        return self._agent

    def run_chat(self, req: ChatRequest) -> ChatResponse:
        raw_key = settings.dashscope_api_key
        if not raw_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY，无法调用大模型")

        text = req.message.strip()
        if req.session_id:
            sess = session_service.get_session(req.session_id)
            if not sess:
                raise LookupError(f"会话不存在: {req.session_id}")
            session_id = sess["id"]
        else:
            session_id = session_service.create_session()["id"]

        session_service.append_message(session_id, role="user", content=text)
        session_service.touch_session(session_id)

        history_rows = session_service.list_messages(session_id)
        lc_in = _messages_to_lc(history_rows)

        agent = self._ensure_agent()
        log.debug(
            "invoke nl2sql agent session=%s history_turns_db=%s",
            session_id,
            len(lc_in),
        )
        try:
            result = agent.invoke(
                {"messages": lc_in},
                {"recursion_limit": _RECURSION_LIMIT},
            )
        except Exception:
            log.exception("nl2sql agent.invoke 失败 session=%s", session_id)
            raise

        out_msgs_raw = result.get("messages") or []
        out_msgs = [m for m in out_msgs_raw if isinstance(m, BaseMessage)]

        answer = extract_final_answer(out_msgs)
        sql_candidate = extract_last_sql(out_msgs)

        columns: list[str] = []
        rows_as_dicts: list[dict[str, Any]] = []
        sql_out: str | None = None
        truncated = False

        if sql_candidate:
            try:
                columns, rows_as_dicts, sql_out, truncated = (
                    query_service.run_readonly_select(sql_candidate)
                )
            except ValueError as err:
                truncated = False
                log.warning(
                    "SQLGuard 拒绝或校验失败 session=%s err=%s snippet=%s",
                    session_id,
                    err,
                    sql_candidate[:200],
                )
                sql_out = sql_candidate.strip()

        viz_dict = viz_service.build_viz_spec(
            columns=columns,
            rows=rows_as_dicts,
            user_question=text,
        )
        viz = VizSpec.model_validate(viz_dict)

        td_meta: dict[str, Any] | None = None
        if truncated:
            td_meta = {"truncated": True}

        table_model = TableData(
            columns=columns,
            rows=rows_as_dicts,
            meta=td_meta,
        )

        display_answer = answer.strip()

        meta: dict[str, Any] = {
            "viz_spec": viz.model_dump(),
            "table": table_model.model_dump(mode="json"),
        }

        persisted = session_service.append_message(
            session_id,
            role="assistant",
            content=display_answer,
            sql_text=sql_out,
            assistant_meta=meta,
        )

        return ChatResponse(
            session_id=session_id,
            message_id=persisted["id"],
            answer=display_answer,
            sql=sql_out,
            table=table_model,
            viz_spec=viz,
            viz_insight=None,
        )
