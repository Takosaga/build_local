import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from main import app


@pytest.fixture
async def client():
    # Reset wizard state before each test so steps don't bleed across tests.
    from wizard.state import reset as reset_wizard
    reset_wizard()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _start_wizard(client):
    """Helper: submit the step-0 form to reach step 1."""
    await client.post("/wizard/start", data={
        "business_name": "Test Shop",
        "business_type": "retail",
        "location": "London",
        "employees": "2-5",
    })


# --- /chat step-advance tests ---

async def test_chat_at_step1_advances_to_step2_after_one_reply(client):
    await _start_wizard(client)
    with patch("main.run_tool_loop", return_value="Great choice!"):
        resp = await client.post("/chat", json={"message": "demo setup please"})
    assert resp.status_code == 200
    # Consume the SSE stream
    body = resp.text
    assert "step_changed" in body

    # State should now be step 2
    from wizard.state import get_state
    assert get_state().current_step == 2


async def test_chat_at_step1_resets_question_counter(client):
    await _start_wizard(client)
    with patch("main.run_tool_loop", return_value="OK"):
        await client.post("/chat", json={"message": "demo"})
    from wizard.state import get_state
    assert get_state().business_data.get("_questions_asked", 0) == 0


async def test_chat_at_step2_increments_question_counter(client):
    await _start_wizard(client)
    # Advance to step 2
    with patch("main.run_tool_loop", return_value="OK"):
        await client.post("/chat", json={"message": "demo"})
    # Now at step 2 — send a message
    with patch("main.run_tool_loop", return_value="Do you track stock?"):
        await client.post("/chat", json={"message": "yes we stock items"})
    from wizard.state import get_state
    assert get_state().business_data.get("_questions_asked", 0) == 1


async def test_chat_at_step1_does_not_increment_question_counter(client):
    await _start_wizard(client)
    # Manually set questions_asked to 3 to prove step-1 does NOT increment it
    from wizard.state import update_business_data
    update_business_data({"_questions_asked": 3})
    with patch("main.run_tool_loop", return_value="OK"):
        await client.post("/chat", json={"message": "demo"})
    from wizard.state import get_state
    # After step 1→2 advance, counter is reset to 0 (not incremented to 4)
    assert get_state().business_data.get("_questions_asked", 0) == 0


# --- /wizard/finalise guard ---

async def test_finalise_rejected_before_step3(client):
    await _start_wizard(client)
    # Still at step 1 — finalise should fail
    resp = await client.post("/wizard/finalise")
    assert resp.status_code == 400


async def test_finalise_accepted_at_step3(client):
    from wizard.state import advance_step
    await _start_wizard(client)
    advance_step()  # step 1→2
    advance_step()  # step 2→3
    resp = await client.post("/wizard/finalise")
    assert resp.status_code == 200
    from wizard.state import get_state
    assert get_state().is_complete is True
