#!/usr/bin/env python3
"""结合 LangChain 官方文档（建议在 Cursor 中启用 Docs by LangChain MCP）核对后端集成：

- Qwen（百炼）经 OpenAI 兼容端点：`ChatOpenAI` + ``DASHSCOPE_BASE_URL``
  （MCP：`/oss/python/concepts/providers-and-models` → OpenAI-compatible endpoints）。
- NL2SQL：`SQLDatabaseToolkit` + Agent；PyPI ``langchain<0.4`` 使用 LangGraph ``create_react_agent``
  替代教程中的 ``create_agent``（MCP：`/oss/python/langchain/sql-agent`）。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ping-qwen",
        action="store_true",
        help="若已配置 DASHSCOPE_API_KEY，调用一次最简单的 invoke（产生计费）。",
    )
    args = parser.parse_args()

    from langchain_community.agent_toolkits import SQLDatabaseToolkit
    from langchain_community.utilities import SQLDatabase
    from langchain_core.language_models.fake_chat_models import ParrotFakeChatModel

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as fh:
        tpath = Path(fh.name)
    cx = sqlite3.connect(str(tpath))
    cx.execute("CREATE TABLE sanity (id INTEGER PRIMARY KEY)")
    cx.commit()
    cx.close()

    uri = f"sqlite:///{tpath.as_posix()}"
    try:
        db = SQLDatabase.from_uri(uri)
        llm = ParrotFakeChatModel()
        tools = SQLDatabaseToolkit(db=db, llm=llm).get_tools()
        names = {t.name for t in tools}
        print("[1] SQLDatabaseToolkit:", sorted(names))

        missing = {
            "sql_db_query",
            "sql_db_schema",
            "sql_db_list_tables",
            "sql_db_query_checker",
        }
        if not missing <= names or len(names & missing) != 4:
            print("❌ toolkit 不完整", file=sys.stderr)
            return 1

        print(
            "[2] Qwen(ChatOpenAI) 工厂：需在 .env 中配置 "
            "DASHSCOPE_API_KEY、QWEN_MODEL。"
        )

        if args.ping_qwen:
            from app.core import llm_factory as lf_mod

            key = lf_mod.settings.dashscope_api_key
            if not key:
                print("❌ 未配置密钥，跳过 --ping-qwen", file=sys.stderr)
                return 2
            from app.core.llm_factory import llm_factory as factory

            m = factory(streaming=False)
            r = m.invoke("Reply with OK only.")
            print("[3] Qwen ping:", getattr(r, "content", str(r)))

        print("✅ NL2SQL 组件集齐；按需使用 --ping-qwen 实测千问。")
    finally:
        try:
            tpath.unlink(missing_ok=True)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
