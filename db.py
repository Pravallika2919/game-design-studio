"""
db.py — saves every generated Game Design Document in a local SQLite file.

SQLite is built into Python (no install, no server). The data lives in
`gdd_history.db` next to app.py, so it survives restarts.

Table: gdds
    id          INTEGER  primary key (auto)
    idea        TEXT     the user's game idea
    created_at  TEXT     when it was generated
    agents_done INTEGER  how many of the 6 agents finished
    results     TEXT     JSON: {agent name: {"output": ..., "model": ...}}
    options     TEXT     JSON: the customization choices, e.g. {"genre": "RPG"}
"""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.getenv("GDD_DB_PATH", Path(__file__).with_name("gdd_history.db")))


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with closing(_connect()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gdds (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                idea        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                agents_done INTEGER NOT NULL,
                results     TEXT NOT NULL
            )""")
        # Older databases (Step 2) have no `options` column — add it without losing data.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(gdds)")]
        if "options" not in cols:
            conn.execute("ALTER TABLE gdds ADD COLUMN options TEXT NOT NULL DEFAULT '{}'")


def save_gdd(idea: str, results: dict, options: dict | None = None) -> int:
    """Store a GDD (plus the customization choices used) and return its new id."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO gdds (idea, created_at, agents_done, results, options) VALUES (?, ?, ?, ?, ?)",
            (idea, datetime.now().isoformat(timespec="seconds"), len(results),
             json.dumps(results, ensure_ascii=False), json.dumps(options or {}, ensure_ascii=False)),
        )
        return cur.lastrowid


def list_gdds(limit: int = 30) -> list[dict]:
    """Newest first. Does not load the (large) results text."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, idea, created_at, agents_done FROM gdds ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"id": r[0], "idea": r[1], "created_at": r[2], "agents_done": r[3]} for r in rows]


def load_gdd(gdd_id: int) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT idea, created_at, results, options FROM gdds WHERE id = ?", (gdd_id,)
        ).fetchone()
    if not row:
        return None
    return {"idea": row[0], "created_at": row[1], "results": json.loads(row[2]),
            "options": json.loads(row[3] or "{}")}


def delete_gdd(gdd_id: int) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM gdds WHERE id = ?", (gdd_id,))