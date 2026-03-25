import pytest
from unittest.mock import MagicMock


@pytest.fixture()
def mock_adapter():
    adapter = MagicMock()
    adapter.post.return_value = {"data": {"name": "ok"}}
    adapter.put.return_value = {"data": {"name": "ok"}}
    adapter.get.return_value = {"data": []}
    return adapter


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    import db.session as session
    monkeypatch.setattr(session, "DB_PATH", tmp_path / "test.db")
    session.init_db()
    yield
