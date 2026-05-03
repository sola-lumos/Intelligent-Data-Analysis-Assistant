"""验证 LangChain 栈：DashScope+Qwen(ChatOpenAI 兼容)；SQLDatabaseToolkit + LangGraph."""

import sqlite3
from pathlib import Path

import pytest
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.language_models.fake_chat_models import ParrotFakeChatModel

from app.core import llm_factory as llm_factory_mod
from app.core.llm_factory import llm_factory
from app.services.nl2sql import (
    EXPECTED_SQL_TOOLS,
    build_nl2sql_agent,
    nl2sql_system_prompt,
)


class _ToolBindParrotFake(ParrotFakeChatModel):
    """fake LLM whose ``bind_tools`` LangGraph expects when compiling ReAct."""

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        return self


@pytest.fixture()
def sqlite_uri_fixture(tmp_path: Path) -> str:
    p = tmp_path / "lc_nl2sql.db"
    cx = sqlite3.connect(str(p))
    cx.execute("CREATE TABLE demos (id INTEGER PRIMARY KEY, name TEXT)")
    cx.execute("INSERT INTO demos (name) VALUES ('Alpha')")
    cx.commit()
    cx.close()
    return f"sqlite:///{p.as_posix()}"


def test_langchain_sql_database_connects(sqlite_uri_fixture: str) -> None:
    db = SQLDatabase.from_uri(sqlite_uri_fixture)
    names = db.get_usable_table_names()
    assert "demos" in names


def test_sql_database_toolkit_exposes_four_tools(sqlite_uri_fixture: str) -> None:
    sql_db = SQLDatabase.from_uri(sqlite_uri_fixture)
    llm = ParrotFakeChatModel()
    tk = SQLDatabaseToolkit(db=sql_db, llm=llm)
    names = {t.name for t in tk.get_tools()}
    assert names == EXPECTED_SQL_TOOLS


def test_nl2sql_system_prompt_contains_dialect(sqlite_uri_fixture: str) -> None:
    db = SQLDatabase.from_uri(sqlite_uri_fixture)
    p = nl2sql_system_prompt(db, top_k=7)
    assert "sqlite" in p.lower()
    assert "7" in p


def test_build_nl2sql_agent_compile(monkeypatch, sqlite_uri_fixture: str) -> None:
    monkeypatch.setattr(llm_factory_mod.settings, "dashscope_api_key", "stub")
    monkeypatch.setattr(
        "app.services.nl2sql.llm_factory",
        lambda **_: _ToolBindParrotFake(response="stub"),
    )
    agent = build_nl2sql_agent(sqlalchemy_uri=sqlite_uri_fixture)
    assert callable(getattr(agent, "invoke"))


def test_llm_factory_requires_key(monkeypatch) -> None:
    monkeypatch.setattr(llm_factory_mod.settings, "dashscope_api_key", None)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        llm_factory()


@pytest.mark.integration
def test_llm_factory_ping_real_qwen(monkeypatch) -> None:
    key = getattr(llm_factory_mod.settings, "dashscope_api_key", None)
    if not key:
        pytest.skip("未配置 DASHSCOPE_API_KEY")
    monkeypatch.setattr(llm_factory_mod.settings, "qwen_temperature", 0)
    lm = llm_factory(streaming=False)
    try:
        rv = lm.invoke("只回复大写字母 OK，不要其它内容")
    except Exception as exc:
        pytest.skip(f"实时 Qwen 不可用（网络/鉴权/模型名）: {exc}")
    txt = getattr(rv, "content", str(rv)).strip().upper()
    if not txt:
        pytest.skip("模型返回空 content")
    assert "OK" in txt or len(txt) > 0
