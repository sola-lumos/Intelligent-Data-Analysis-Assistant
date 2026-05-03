"""SQLite 会话 / 消息读写。"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from app.db import sqlite


def _now_ms() -> int:
    return int(time.time() * 1000)


def create_session(title: str = "新会话") -> dict[str, Any]:
    sid = uuid.uuid4().hex
    now = _now_ms()
    conn = sqlite.connect()
    try:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
            (sid, title, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": sid, "title": title, "created_at": now, "updated_at": now}


def list_sessions() -> list[dict[str, Any]]:
    conn = sqlite.connect()
    try:
        cur = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_session(session_id: str) -> dict[str, Any] | None:
    conn = sqlite.connect()
    try:
        cur = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id=?",
            (session_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def patch_session(session_id: str, *, title: str) -> dict[str, Any] | None:
    now = _now_ms()
    conn = sqlite.connect()
    try:
        cur = conn.execute(
            "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
            (title, now, session_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id=?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_session(session_id: str) -> bool:
    conn = sqlite.connect()
    try:
        cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def touch_session(session_id: str) -> None:
    now = _now_ms()
    conn = sqlite.connect()
    try:
        conn.execute(
            "UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id)
        )
        conn.commit()
    finally:
        conn.close()


def append_message(
    session_id: str,
    *,
    role: str,
    content: str,
    sql_text: str | None = None,
    assistant_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mid = uuid.uuid4().hex
    now = _now_ms()
    meta_json = json.dumps(assistant_meta, ensure_ascii=False) if assistant_meta else None
    conn = sqlite.connect()
    try:
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, content, sql_text, assistant_meta, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (mid, session_id, role, content, sql_text, meta_json, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": mid, "created_at": now}


def merge_assistant_meta(message_id: str, patch: dict[str, Any]) -> bool:
    """合并写入助手消息的 ``assistant_meta``（用于 SSE 延后写入 ``viz_insight``）。"""
    conn = sqlite.connect()
    try:
        cur = conn.execute(
            "SELECT assistant_meta FROM messages WHERE id=?",
            (message_id,),
        )
        row = cur.fetchone()
        if not row:
            return False
        raw = row[0]
        meta: dict[str, Any]
        if isinstance(raw, str) and raw.strip():
            try:
                meta = json.loads(raw)
                if not isinstance(meta, dict):
                    meta = {}
            except json.JSONDecodeError:
                meta = {}
        else:
            meta = {}
        meta.update(patch)
        conn.execute(
            "UPDATE messages SET assistant_meta=? WHERE id=?",
            (json.dumps(meta, ensure_ascii=False), message_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def list_messages(session_id: str) -> list[dict[str, Any]]:
    conn = sqlite.connect()
    try:
        cur = conn.execute(
            """
            SELECT id, session_id, role, content, sql_text, assistant_meta, created_at
            FROM messages WHERE session_id=? ORDER BY created_at ASC
            """,
            (session_id,),
        )
        out: list[dict[str, Any]] = []
        for r in cur.fetchall():
            d = dict(r)
            meta_raw = d.get("assistant_meta")
            if isinstance(meta_raw, str) and meta_raw.strip():
                try:
                    d["assistant_meta"] = json.loads(meta_raw)
                except json.JSONDecodeError:
                    d["assistant_meta"] = None
            else:
                d["assistant_meta"] = None
            out.append(d)
        return out
    finally:
        conn.close()
