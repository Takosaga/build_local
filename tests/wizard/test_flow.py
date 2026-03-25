import pytest


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    import db.session as session
    monkeypatch.setattr(session, "DB_PATH", tmp_path / "test.db")
    session.init_db()


def test_get_mode_returns_setup_when_wizard_incomplete():
    from wizard.flow import get_mode
    assert get_mode() == "setup"


def test_get_mode_returns_ongoing_after_completion():
    from wizard.state import mark_complete
    from wizard.flow import get_mode
    mark_complete()
    assert get_mode() == "ongoing"


def test_questions_asked_starts_at_zero():
    from wizard.flow import get_questions_asked, increment_questions_asked
    assert get_questions_asked() == 0


def test_increment_questions_asked():
    from wizard.flow import get_questions_asked, increment_questions_asked
    increment_questions_asked()
    increment_questions_asked()
    assert get_questions_asked() == 2


def test_should_advance_from_info_step_after_5_questions():
    from wizard.flow import should_advance_from_info_step, increment_questions_asked
    for _ in range(5):
        increment_questions_asked()
    assert should_advance_from_info_step() is True


def test_should_not_advance_before_5_questions():
    from wizard.flow import should_advance_from_info_step, increment_questions_asked
    increment_questions_asked()
    assert should_advance_from_info_step() is False
