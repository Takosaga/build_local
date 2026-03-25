import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/app.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS wizard_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_step INTEGER DEFAULT 0,
                completed_steps TEXT DEFAULT '[]',
                business_data TEXT DEFAULT '{}',
                is_complete INTEGER DEFAULT 0
            );
        """)
        conn.execute("INSERT OR IGNORE INTO wizard_state (id) VALUES (1)")


def load_conversation(limit: int = 40) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def save_message(role: str, content: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
        )


def load_wizard_state() -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM wizard_state WHERE id = 1").fetchone()
    return {
        "current_step": row["current_step"],
        "completed_steps": json.loads(row["completed_steps"]),
        "business_data": json.loads(row["business_data"]),
        "is_complete": bool(row["is_complete"]),
    }


def save_wizard_state(
    current_step: int,
    completed_steps: list,
    business_data: dict,
    is_complete: bool = False,
):
    with get_connection() as conn:
        conn.execute(
            """UPDATE wizard_state SET
                current_step = ?,
                completed_steps = ?,
                business_data = ?,
                is_complete = ?
               WHERE id = 1""",
            (
                current_step,
                json.dumps(completed_steps),
                json.dumps(business_data),
                int(is_complete),
            ),
        )
