"""根据查询结果推断 ``viz_spec``（规则启发式）。"""

from __future__ import annotations

import re
from typing import Any


_TIME_NAME_HINT = re.compile(r"(time|date|day|month|year|_ts|timestamp)", re.I)


def _is_number(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):  # bool is int subclass
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return False
        try:
            float(s.replace(",", ""))
            return True
        except ValueError:
            return False
    return False


def _col_kind(name: str, sample: Any) -> str:
    n = name.lower()
    if _TIME_NAME_HINT.search(n):
        return "time_like"
    if _is_number(sample):
        return "num"
    return "cat"


def build_viz_spec(
    *,
    columns: list[str],
    rows: list[dict[str, Any]],
    user_question: str = "",
) -> dict[str, Any]:
    """返回可序列化为 :class:`~app.schemas.chat.VizSpec` 的字典。"""
    if not columns or not rows:
        return {"chart_type": "table"}

    kind: dict[str, str] = {}
    first = rows[0]
    for col in columns:
        kind[col] = _col_kind(col, first.get(col))

    nums = [c for c in columns if kind[c] == "num"]
    cats = [c for c in columns if kind[c] == "cat"]
    times = [c for c in columns if kind[c] == "time_like"]

    q = user_question.strip()
    prefer_line_graph = ("趋势" in q or "走势" in q or "按月" in q or "每日" in q)

    if len(nums) >= 2 and len(cats) == 0 and len(times) == 0:
        return {
            "chart_type": "scatter",
            "x_field": nums[0],
            "y_field": nums[1],
        }

    x_col: str | None = None
    y_col: str | None = None
    chart_type = "bar"

    if times and nums:
        x_col = times[0]
        y_col = nums[0]
        chart_type = "line" if prefer_line_graph else "bar"
    elif cats and nums:
        x_col = cats[0]
        y_col = nums[0]
        if len(rows) <= 12 and len(columns) == 2:
            chart_type = "pie"
    #: 单列单行标量（如 COUNT/SUM）：柱状图观感差且在弱布局下易被当成「空白」，直接走表格更清晰
    elif nums and len(nums) == 1 and len(columns) == 1 and len(rows) == 1:
        return {"chart_type": "table"}
    elif nums and len(nums) == 1 and len(columns) == 1:
        x_col = nums[0]
        y_col = nums[0]
        chart_type = "bar"

    if not x_col or not y_col:
        return {"chart_type": "table"}

    if chart_type == "pie":
        return {
            "chart_type": "pie",
            "category_field": x_col,
            "value_field": y_col,
        }
    return {
        "chart_type": chart_type,
        "x_field": x_col,
        "y_field": y_col,
    }
