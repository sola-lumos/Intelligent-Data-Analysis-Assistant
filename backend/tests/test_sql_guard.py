"""SQLGuard 单元测试。"""

from __future__ import annotations

import pytest

from app.utils import sql_guard


def test_rejects_multiple_statements() -> None:
    with pytest.raises(ValueError, match="分号"):
        sql_guard.validate_and_clamp_select("SELECT 1; SELECT 2")


def test_rejects_insert() -> None:
    with pytest.raises(ValueError, match="禁止"):
        sql_guard.validate_and_clamp_select("INSERT INTO t VALUES (1)")


def test_accepts_simple_select_append_limit(monkeypatch) -> None:
    monkeypatch.setattr("app.utils.sql_guard.settings.max_query_rows", 10)
    out = sql_guard.validate_and_clamp_select("SELECT 1 AS x")
    assert "LIMIT 10" in out.upper()


def test_clamps_over_limit(monkeypatch) -> None:
    monkeypatch.setattr("app.utils.sql_guard.settings.max_query_rows", 5)
    out = sql_guard.validate_and_clamp_select("SELECT 1 LIMIT 999")
    assert "LIMIT 5" in out.upper()
