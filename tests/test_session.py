import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    """Redirect DB to a temp file for each test."""
    import db.session as session
    monkeypatch.setattr(session, "DB_PATH", tmp_path / "test.db")
    session.init_db()
    yield


def test_init_db_creates_tables():
    from db.session import get_connection
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {t["name"] for t in tables}
    assert "messages" in names
    assert "wizard_state" in names


def test_save_and_load_message():
    from db.session import save_message, load_conversation
    save_message("user", "hello")
    save_message("assistant", "hi there")
    history = load_conversation()
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "hello"}
    assert history[1] == {"role": "assistant", "content": "hi there"}


def test_load_conversation_respects_limit():
    from db.session import save_message, load_conversation
    for i in range(50):
        save_message("user", f"message {i}")
    history = load_conversation(limit=40)
    assert len(history) == 40


def test_wizard_state_defaults():
    from db.session import load_wizard_state
    state = load_wizard_state()
    assert state["current_step"] == 0
    assert state["completed_steps"] == []
    assert state["business_data"] == {}
    assert state["is_complete"] is False


def test_save_and_load_wizard_state():
    from db.session import save_wizard_state, load_wizard_state
    save_wizard_state(
        current_step=2,
        completed_steps=[0, 1],
        business_data={"name": "Bloom Flowers"},
        is_complete=False,
    )
    state = load_wizard_state()
    assert state["current_step"] == 2
    assert state["completed_steps"] == [0, 1]
    assert state["business_data"]["name"] == "Bloom Flowers"
