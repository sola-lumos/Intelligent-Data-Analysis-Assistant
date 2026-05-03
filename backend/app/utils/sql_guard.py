"""只读 SQL 白名单校验与 LIMIT 补强。"""

from __future__ import annotations

import re
from typing import Final

from app.core.config import settings

_FORBIDDEN_WORDS: Final[tuple[str, ...]] = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "analyze",
    "reindex",
)

_LIMIT_RE = re.compile(
    r"\blimit\s+(\d+)\s*(?:;)?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def validate_and_clamp_select(sql: str) -> str:
    """仅允许单条 SELECT；禁止分号多语句；clamp / 追加 LIMIT。"""
    stripped = (sql or "").strip()
    if not stripped:
        raise ValueError("SQL 为空")

    if ";" in stripped:
        raise ValueError("禁止多语句（请勿使用分号）")

    lowered = stripped.lower()
    safe = lowered
    for w in _FORBIDDEN_WORDS:
        if re.search(rf"\b{w}\b", safe):
            raise ValueError(f"禁止关键字: {w.upper()}")

    if not lowered.startswith("select") and not lowered.startswith("with"):
        raise ValueError("仅允许 SELECT（或 WITH … SELECT）语句")

    max_r = max(1, int(settings.max_query_rows))
    m = _LIMIT_RE.search(stripped)
    if m:
        try:
            lim = int(m.group(1))
        except ValueError as err:
            raise ValueError("无效的 LIMIT") from err
        if lim > max_r:
            stripped = _LIMIT_RE.sub(f"LIMIT {max_r}", stripped)
    else:
        stripped = f"{stripped.rstrip()} LIMIT {max_r}"
    return stripped
