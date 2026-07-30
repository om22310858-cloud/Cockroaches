"""
Lightweight SQLite persistence layer for chat sessions.

Creates chat_history.db in the same folder the app is run from.
No server needed — Streamlit talks to this file directly.
"""

import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = "chat_history.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
        """
    )
    conn.commit()
    conn.close()


def create_session(first_message: str) -> str:
    """Create a new session, titled from the first ~40 chars of the first message."""
    session_id = str(uuid.uuid4())
    title = (first_message[:40] + "...") if len(first_message) > 40 else first_message
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
        (session_id, title, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return session_id


def save_message(session_id: str, role: str, content: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_all_sessions() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at FROM sessions ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_messages(session_id: str) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def rename_session(session_id: str, new_title: str):
    conn = get_conn()
    conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
    conn.commit()
    conn.close()