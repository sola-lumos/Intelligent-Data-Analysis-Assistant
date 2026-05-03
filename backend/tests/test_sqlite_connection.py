import sqlite3

from app.db import sqlite


def test_sqlite_memory_select() -> None:
    conn = sqlite.connect(":memory:")
    cur = conn.execute("SELECT 1 AS n")
    row = cur.fetchone()
    assert row is not None
    assert row["n"] == 1  # row_factory Row
    conn.close()


def test_ensure_parent_creates(tmp_path, monkeypatch) -> None:
    db = tmp_path / "nested" / "app.db"
    monkeypatch.setattr("app.db.sqlite.settings.sqlite_db_path", str(db))
    sqlite.ensure_parent_dir_exists()
    assert db.parent.is_dir()


def test_list_tables_missing_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "fresh.db"
    monkeypatch.setattr(
        "app.db.sqlite.settings.sqlite_db_path", str(db_path)
    )
    conn = sqlite.connect()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    assert rows == []
