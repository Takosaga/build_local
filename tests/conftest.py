import pytest


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    import db.session as session
    monkeypatch.setattr(session, "DB_PATH", tmp_path / "test.db")
    session.init_db()
    yield
