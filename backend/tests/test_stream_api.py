"""SSE /api/chat/stream 契约测试（模拟 ChatService，无 DashScope）。"""

from __future__ import annotations

import json

from starlette.testclient import TestClient

from app.main import create_app
from app.schemas.chat import ChatRequest, ChatResponse, TableData, VizSpec


class _StubChatService:
    def run_chat(self, _: ChatRequest) -> ChatResponse:
        return ChatResponse(
            session_id="a" * 32,
            message_id="b" * 32,
            answer="你好，这是 SSE 拆分测试。",
            sql="SELECT 1 AS x",
            table=TableData(
                columns=["x"],
                rows=[{"x": 1}],
                meta={"truncated": False},
            ),
            viz_spec=VizSpec(chart_type="table"),
            viz_insight="stub 洞察",
        )


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        blk = block.strip()
        if not blk:
            continue
        evt = ""
        datalines: list[str] = []
        for line in blk.split("\n"):
            if line.startswith("event:"):
                evt = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                datalines.append(line.split(":", 1)[1].lstrip())
        if not datalines:
            continue
        data_raw = "\n".join(datalines)
        events.append((evt, json.loads(data_raw)))
    return events


def test_chat_stream_sse_events_order() -> None:
    app = create_app()
    with TestClient(app) as client:
        app.state.chat_service = _StubChatService()

        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"message": "查一下总数"},
            headers={"accept": "text/event-stream"},
        ) as resp:
            assert resp.status_code == 200
            raw = "".join(part.decode("utf-8") for part in resp.iter_bytes())

        evs = _parse_sse(raw)
        kinds = [e[0] for e in evs]
        if "status" in kinds:
            assert kinds.index("status") < kinds.index("answer")
        assert "answer" in kinds
        assert "sql" in kinds
        idx_sql = kinds.index("sql")
        idx_tb = kinds.index("table")
        idx_ch = kinds.index("chart")
        idx_dn = kinds.index("done")

        assert idx_sql < idx_tb < idx_ch < idx_dn
        if "insight" in kinds:
            assert idx_ch < kinds.index("insight") < idx_dn

        done_payload = evs[idx_dn][1]
        assert "session_id" in done_payload
        assert "message_id" in done_payload
        assert done_payload.get("viz_insight") == "stub 洞察"
