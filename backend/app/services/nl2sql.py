"""NL2SQL：LangChain ``SQLDatabaseToolkit`` + LangGraph ``create_react_agent``.

LangChain MCP 教程（`/oss/python/langchain/sql-agent`）推荐使用 ``SQLDatabaseToolkit`` 与 Agent。
教程中的 ``langchain.agents.create_agent`` 当前 PyPI ``langchain<0.4`` 尚不可用，
语义等价做法是 ``langgraph.prebuilt.create_react_agent``。
"""

from __future__ import annotations

from typing import FrozenSet

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
from app.core.llm_factory import llm_factory
from app.db import sqlite
from app.db.langchain_sql import build_langchain_sql_database, get_langchain_sql_database

EXPECTED_SQL_TOOLS: FrozenSet[str] = frozenset(
    {"sql_db_query", "sql_db_schema", "sql_db_list_tables", "sql_db_query_checker"}
)


def nl2sql_system_prompt(db: SQLDatabase, *, top_k: int | None = None) -> str:
    k = int(settings.max_query_rows) if top_k is None else top_k
    return (
        """
You are an agent designed to interact with a read-only SQLite database via tools.
Answer in the same language as the user when possible.

Rules:
- First list tables when needed; then inspect schemas of relevant tables.
- Generate syntactically correct {dialect} queries; ALWAYS limit SELECT to at most {top_k} rows unless the user insists on a precise count strategy.
- Only query columns that matter for the answer.
- NEVER run DML / DDL (INSERT, UPDATE, DELETE, DROP, ...).
- If execution fails, read the DB error and fix the SQL.

You MUST double-check generated SQL via the checker tool before executing destructive-looking queries.

If the user speaks Chinese, reply in concise Chinese unless they ask English.

When answering in Chinese, your FINAL reply must be SHORT prose only (2–6 sentences):
- Interpret the question and state the business takeaway or conclusion direction.
- Output PLAIN TEXT ONLY: do NOT use Markdown. Forbidden in the final reply: # headings, ** or * emphasis, ` backticks, ``` fences, - or * list markers at line starts, [text](url) links, pipe tables (lines containing | column separators). Describe tabular numbers in sentences instead (e.g. “1月销售额为…；2月为…”).
- Do NOT invent numbers; base conclusions on values returned by your SQL queries.

Keep tooling traces out of the final user-visible message body.
"""
    ).strip().format(dialect=db.dialect, top_k=k)


# 修改 ``nl2sql_system_prompt`` 后递增该值；``ChatService`` 会丢弃旧 Agent 单例并重载。
NL2SQL_PROMPT_REVISION = 7


def build_nl2sql_agent(*, sqlalchemy_uri: str | None = None, streaming: bool = False):
    """构造可 ``invoke({'messages': [...]})`` 的 LangGraph ReAct Agent。"""
    sqlite.ensure_parent_dir_exists()
    llm = llm_factory(streaming=streaming)
    db = (
        build_langchain_sql_database(sqlalchemy_uri=sqlalchemy_uri)
        if sqlalchemy_uri
        else get_langchain_sql_database()
    )
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()
    return create_react_agent(
        llm,
        tools,
        prompt=nl2sql_system_prompt(db),
    )
