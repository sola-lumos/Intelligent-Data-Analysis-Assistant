"""百炼 Qwen（OpenAI Chat Completions 兼容模式）接入 LangChain.

LangChain 官方说明：`ChatOpenAI` + 自定义 ``base_url`` 连接 OpenAI 兼容端点
（见 MCP 检索「OpenAI-compatible endpoints」）。
"""

from langchain_openai import ChatOpenAI

from app.core.config import settings


def llm_factory(*, streaming: bool = False) -> ChatOpenAI:
    """返回绑定 DashScope/OpenAI 兼容 API 的 ``ChatOpenAI``，供 NL2SQL ReAct Agent 使用。"""
    if not settings.dashscope_api_key:
        raise ValueError(
            "未配置 DASHSCOPE_API_KEY，无法初始化 ChatOpenAI。"
            "在 backend/.env 中填入百炼 API Key。",
        )
    return ChatOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=(settings.dashscope_base_url or "").rstrip("/"),
        model=settings.qwen_model,
        temperature=float(settings.qwen_temperature),
        streaming=streaming,
        timeout=90.0,
    )
