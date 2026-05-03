"""数据洞察：基于用户问题、SQL 与查询结果 + 业务规则，二次调用 LLM 生成纯文本结论。"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

log = logging.getLogger(__name__)

_SYSTEM = """你是医药与渠道销售分析顾问。只根据用户问题、已执行 SQL 与「查询结果」中的数据写结论，使用中文日常表述。
输出要求：纯文本，不要使用 Markdown（禁止 # 标题、** 加粗、列表符号、代码块），不要重复或解释 SQL，不要说明你的推理过程，不要编造未出现在查询结果中的数字或对象名称。
若数据不足以计算完成率，据实说明，不臆造目标或达成率。
关注：完成率与目标对比（仅当结果列支持时）、明显落后或偏低的地区/产品/代表、差距与业务风险、完成率低于业务规则中的阈值时须点明为进度落后。结尾给 2～4 条简洁、可执行的业务建议。"""


def _format_query_result(
    columns: list[str],
    rows: list[dict[str, Any]],
    *,
    truncated: bool,
    max_rows: int,
) -> str:
    parts: list[str] = []
    if truncated:
        parts.append("说明：因行数上限，查询结果在库内已被截断，以下仅为返回给分析器的部分行。")
    if not columns:
        parts.append("（无列信息）")
        return "\n".join(parts)
    parts.append("列名：" + " | ".join(columns))
    if not rows:
        parts.append("数据行数：0（空结果）。")
        return "\n".join(parts)
    show = rows[: max(1, max_rows)]
    for i, row in enumerate(show, 1):
        cells = [f"{c}={row.get(c)!s}" for c in columns]
        parts.append(f"第{i}行：" + "；".join(cells))
    if len(rows) > len(show):
        parts.append(f"... 共 {len(rows)} 行，此处仅展示前 {len(show)} 行。")
    return "\n".join(parts)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # OpenAI Chat Completions：{"type":"text","text":"..."}
                if isinstance(block.get("text"), str):
                    parts.append(block["text"])
                    continue
                for key in ("content", "message", "reasoning"):
                    v = block.get(key)
                    if isinstance(v, str) and v.strip():
                        parts.append(v)
                        break
        return "".join(parts)
    return str(content or "")


def _strip_markdown_noise(text: str) -> str:
    """弱化偶然生成的 Markdown，保留可读句子。"""
    s = text.strip()
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s.strip()


def _safe_insight_error(exc: BaseException) -> str:
    """不向客户端泄露密钥与原始栈，仅返回可操作建议。"""
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return "调用模型超时，请稍后重试"
    if "401" in msg or "403" in msg or "api key" in msg or "incorrect api key" in msg:
        return "模型 API 鉴权失败，请检查 DASHSCOPE_API_KEY 与模型名称"
    if "429" in msg or "rate limit" in msg:
        return "模型调用频率受限，请稍后重试"
    if "connection" in msg or "connect" in msg or "refused" in msg:
        return "无法连接模型服务，请检查网络或 DASHSCOPE_BASE_URL"
    return "洞察生成失败，请稍后重试"


def generate_viz_insight(
    *,
    user_question: str,
    sql: str | None,
    columns: list[str],
    rows: list[dict[str, Any]],
    truncated: bool,
) -> tuple[str | None, str | None]:
    """返回 (洞察正文, 面向用户的失败说明)。

    成功时第二项为 ``None``；失败时第一项为 ``None``，第二项为简短中文原因。
    """
    if not settings.dashscope_api_key:
        return None, "未配置模型密钥"

    br = (settings.viz_insight_business_rules or "").strip() or "（无额外业务规则）"
    qres = _format_query_result(
        columns,
        rows,
        truncated=truncated,
        max_rows=max(1, int(settings.viz_insight_max_preview_rows)),
    )
    user_block = f"""请根据用户问题、SQL 查询结果和业务规则，生成数据洞察结论。

用户问题：
{user_question.strip()}

SQL：
{(sql or "").strip() or "（本次无有效执行 SQL）"}

查询结果：
{qres}

业务规则：
{br}"""

    try:
        llm = ChatOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=(settings.dashscope_base_url or "").rstrip("/"),
            model=settings.qwen_model,
            temperature=float(settings.qwen_insight_temperature),
            timeout=90.0,
        )
        out = llm.invoke(
            [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=user_block),
            ]
        )
        try:
            if isinstance(out, BaseMessage):
                text = out.text()
            else:
                text = _message_content_to_text(getattr(out, "content", ""))
        except Exception:
            log.warning("viz_insight BaseMessage.text() 失败，回退按 content 解析")
            text = _message_content_to_text(getattr(out, "content", ""))

        text = _strip_markdown_noise((text or "").strip())
        if not text:
            preview = getattr(out, "content", "")
            log.warning(
                "viz_insight 模型返回正文为空 type=%s content_preview=%r",
                type(out).__name__,
                preview if isinstance(preview, str) else str(preview)[:800],
            )
            return None, (
                "模型未返回有效正文（常见于 content 为多段结构）。"
                "请确认 QWEN_MODEL 与百炼控制台一致，或稍后重试。"
            )
        return text, None
    except Exception as exc:
        log.exception("viz_insight 生成失败")
        return None, _safe_insight_error(exc)
