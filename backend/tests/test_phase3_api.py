"""Phase 3：sessions API 与 `/api/chat`（ChatService mock）。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db import bootstrap
from app.main import create_app
from app.schemas.chat import ChatRequest, ChatResponse, TableData, VizSpec


@pytest.fixture()
def iso_app(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "sqlite_db_path", str(tmp_path / "phase3.db"))
    bootstrap.init_db()
    return create_app()


class _DummyChatSvc:
    def run_chat(self, req: ChatRequest) -> ChatResponse:
        sid = req.session_id or "fallback_session"
        return ChatResponse(
            session_id=sid,
            message_id="m_fixture",
            answer="stub",
            sql="SELECT 1 AS n WHERE 1=0",
            table=TableData(columns=["n"], rows=[]),
            viz_spec=VizSpec(chart_type="table"),
        )


class _DummyRaisesLookup(_DummyChatSvc):
    def run_chat(self, req: ChatRequest) -> ChatResponse:
        raise LookupError("会话不存在: x")


class _DummyRaisesValue(_DummyChatSvc):
    def run_chat(self, req: ChatRequest) -> ChatResponse:
        raise ValueError("未配置")


@pytest.mark.asyncio
async def test_sessions_crud(iso_app) -> None:
    transport = ASGITransport(app=iso_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/sessions", json={"title": "A"})
        assert r.status_code == 201
        sid = r.json()["id"]
        assert len(sid) == 32

        r2 = await client.get("/api/sessions")
        assert r2.status_code == 200
        items = r2.json()
        assert isinstance(items, list)
        assert any(x["id"] == sid for x in items)

        r3 = await client.get(f"/api/sessions/{sid}/messages")
        assert r3.status_code == 200
        assert r3.json() == []

        r4 = await client.patch(
            "/api/sessions/" + sid, json={"title": "Renamed"}
        )
        assert r4.status_code == 200
        assert r4.json()["title"] == "Renamed"

        r5 = await client.delete("/api/sessions/" + sid)
        assert r5.status_code == 204

        r6 = await client.get(f"/api/sessions/{sid}/messages")
        assert r6.status_code == 404


@pytest.mark.asyncio
async def test_chat_uses_stub_service(iso_app) -> None:
    iso_app.state.chat_service = _DummyChatSvc()
    transport = ASGITransport(app=iso_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/chat", json={"message": "你好"})
        assert r.status_code == 200
        body = r.json()
        assert body["answer"] == "stub"
        assert body["table"]["columns"] == ["n"]


@pytest.mark.asyncio
async def test_chat_404_unknown_session(iso_app) -> None:
    iso_app.state.chat_service = _DummyRaisesLookup()
    transport = ASGITransport(app=iso_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/chat",
            json={"session_id": "deadbeefdeadbeefdeadbeefdeadbeef", "message": "x"},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_chat_503_no_api_key(iso_app) -> None:
    iso_app.state.chat_service = _DummyRaisesValue()
    transport = ASGITransport(app=iso_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/chat", json={"message": "x"})
        assert r.status_code == 503


@pytest.mark.asyncio
async def test_create_session_via_messages_after_chat(iso_app) -> None:
    """占位：第一轮 chat mock 不涉及 DB；会话 API 仍可独立使用。"""
    transport = ASGITransport(app=iso_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/sessions", json={})
        assert r.status_code == 201
        assert r.json()["title"] == "新会话"


@pytest.mark.asyncio
async def test_post_message_viz_insight(monkeypatch, iso_app) -> None:
    from app.core.config import settings
    from app.services import session_service

    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(
        "app.api.routes_sessions.generate_viz_insight",
        lambda **kwargs: ("按需洞察示例", None),
    )

    transport = ASGITransport(app=iso_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/sessions", json={})
        sid = r.json()["id"]
        session_service.append_message(sid, role="user", content="大区销量？")
        meta = {
            "viz_spec": {"chart_type": "table"},
            "table": {"columns": ["region", "amt"], "rows": [{"region": "华东", "amt": 100}]},
        }
        persisted = session_service.append_message(
            sid,
            role="assistant",
            content="见图表",
            sql_text="SELECT 1",
            assistant_meta=meta,
        )
        mid = persisted["id"]
        r2 = await client.post(
            f"/api/sessions/{sid}/messages/{mid}/insight",
            json={},
        )
        assert r2.status_code == 200
        assert r2.json()["viz_insight"] == "按需洞察示例"
