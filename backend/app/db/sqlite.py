"""SQLite helpers (Phase 1: connectivity only; read-only guard in Phase 3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import settings


def get_db_path() -> Path:
    return Path(settings.sqlite_db_path).resolve()


def connect(uri: str | None = None) -> sqlite3.Connection:
    path = uri or str(get_db_path())
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.DatabaseError:
        pass
    return conn


def ensure_parent_dir_exists() -> None:
    get_db_path().parent.mkdir(parents=True, exist_ok=True)
