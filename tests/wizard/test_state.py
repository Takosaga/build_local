import pytest


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    import db.session as session
    monkeypatch.setattr(session, "DB_PATH", tmp_path / "test.db")
    session.init_db()


def test_initial_state_is_step_zero():
    from wizard.state import get_state
    state = get_state()
    assert state.current_step == 0
    assert state.is_complete is False


def test_advance_step_increments_and_marks_completed():
    from wizard.state import get_state, advance_step
    advance_step(business_data={"name": "Bloom"})
    state = get_state()
    assert state.current_step == 1
    assert 0 in state.completed_steps


def test_mark_complete_sets_flag():
    from wizard.state import mark_complete, get_state
    mark_complete()
    state = get_state()
    assert state.is_complete is True


def test_update_business_data_merges():
    from wizard.state import update_business_data, get_state
    update_business_data({"name": "Bloom"})
    update_business_data({"type": "Flower Shop"})
    state = get_state()
    assert state.business_data["name"] == "Bloom"
    assert state.business_data["type"] == "Flower Shop"


def test_reset_returns_to_step_zero():
    from wizard.state import advance_step, reset, get_state
    advance_step()
    advance_step()
    reset()
    state = get_state()
    assert state.current_step == 0
    assert state.completed_steps == []
    assert state.is_complete is False
