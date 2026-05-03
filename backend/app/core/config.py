from __future__ import annotations

from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    sqlite_db_path: str = "./data/app.db"

    #: 阿里云百炼 / DashScope（OpenAI 兼容 Chat Completions）；未配置时报错由调用方捕获
    dashscope_api_key: Optional[str] = None
    dashscope_base_url: str = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    #: 需在百炼控制台确认可用名称，例如 qwen-plus、qwen-turbo；Qwen3 名以控制台为准
    qwen_model: str = "qwen-plus"
    qwen_temperature: float = 0.0
    #: 数据洞察二次调用（略高以保证语句自然，仍须严格依从数据）
    qwen_insight_temperature: float = 0.2
    #: 传入洞察模型的结果行数上限（控制 token）
    viz_insight_max_preview_rows: int = 40
    #: 业务规则（可用环境变量 VIZ_INSIGHT_BUSINESS_RULES 覆盖整段）
    viz_insight_business_rules: str = (
        "1. 仅当查询结果中同时存在或可推算「实际」与「目标」时，再写完成率；"
        "完成率=实际/目标，以业务含义为准（金额或数量需与列名一致）。\n"
        "2. 完成率低于 80% 时，在结论中明确为「进度落后」或同类表述。\n"
        "3. 若无目标、无期间对齐，则不得编造完成率；可写排名、区域/产品对比、绝对差距与风险。\n"
        "4. 突出落后产品、区域或代表，并点出与整体或领先者的差距。\n"
        "5. 建议简洁、可执行，避免空话。"
    )

    #: SELECT 结果与 SQLGuard 默认 LIMIT 上限
    max_query_rows: int = 200

    #: SSE「打字机」：`run_chat` 完成后按块推送 answer；块间休眠秒数，0 表示不人为延迟
    sse_typing_delay_seconds: float = 0.0
    #: 每块最大字符数（越大块数越少，推送更快；仍受单次 JSON 体积限制）
    sse_answer_chunk_chars: int = 512

    def cors_origins_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
