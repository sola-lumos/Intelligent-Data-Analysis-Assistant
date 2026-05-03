"""在安全 SQL 上执行只读查询。"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from app.core.config import settings
from app.db import sqlite
from app.utils import sql_guard

log = logging.getLogger(__name__)


def run_readonly_select(
    sql: str,
) -> tuple[list[str], list[dict[str, Any]], str, bool]:
    """校验、补充 LIMIT，并执行只读查询；返回列名、行字典列表、规范化后的 SQL。"""
    safe_sql = sql_guard.validate_and_clamp_select(sql)
    conn = sqlite.connect()
    try:
        try:
            conn.execute("PRAGMA query_only=ON")
        except sqlite3.DatabaseError:
            log.debug("PRAGMA query_only 不可用，仍依赖 SQLGuard")
        cur = conn.execute(safe_sql)
        rows_raw = cur.fetchall()
        colnames = [d[0] for d in cur.description] if cur.description else []
        rows: list[dict[str, Any]] = [dict(zip(colnames, list(r))) for r in rows_raw]
        max_r = max(1, int(settings.max_query_rows))
        truncated = len(rows) >= max_r
        return colnames, rows, safe_sql, truncated
    finally:
        try:
            conn.execute("PRAGMA query_only=OFF")
        except sqlite3.DatabaseError:
            pass
        conn.close()
