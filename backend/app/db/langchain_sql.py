"""LangChain ``SQLDatabase`` 封装 — NL2SQL / SQL toolkit 数据源。"""

from __future__ import annotations

from pathlib import Path

from langchain_community.utilities import SQLDatabase

from app.core.config import settings
from app.db import sqlite


def sqlalchemy_sqlite_uri(db_path: Path) -> str:
    return "sqlite:///" + db_path.as_posix()


def build_langchain_sql_database(*, sqlalchemy_uri: str | None = None) -> SQLDatabase:
    """根据 URI 构造 ``SQLDatabase``；未传时使用 ``settings.sqlite_db_path``。"""
    if sqlalchemy_uri:
        uri = sqlalchemy_uri
    else:
        sqlite.ensure_parent_dir_exists()
        uri = sqlalchemy_sqlite_uri(sqlite.get_db_path())
    return SQLDatabase.from_uri(uri)


def get_langchain_sql_database() -> SQLDatabase:
    """应用默认路径（相对 ``settings.sqlite_db_path``）。"""
    return build_langchain_sql_database()
