import pytest
import respx
import httpx
import json
from unittest.mock import MagicMock
from llm.client import run_tool_loop, execute_tool_call, validate_tool_call


def make_lm_response(content=None, tool_calls=None, finish_reason="stop"):
    choice = {"finish_reason": finish_reason, "message": {"role": "assistant"}}
    if content:
        choice["message"]["content"] = content
    if tool_calls:
        choice["message"]["tool_calls"] = tool_calls
        choice["message"]["content"] = None
    return {"choices": [choice]}


@respx.mock
def test_run_tool_loop_returns_text_on_stop(monkeypatch):
    import config
    monkeypatch.setattr(config, "LM_STUDIO_URL", "http://127.0.0.1:1234")
    monkeypatch.setattr(config, "LM_STUDIO_MODEL", "test-model")

    respx.post("http://127.0.0.1:1234/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=make_lm_response(content="Hello there!"))
    )
    adapter = MagicMock()
    result = run_tool_loop(
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        adapter=adapter,
        system_prompt="You are helpful.",
    )
    assert result == "Hello there!"


@respx.mock
def test_run_tool_loop_executes_tool_and_continues(monkeypatch):
    import config
    monkeypatch.setattr(config, "LM_STUDIO_URL", "http://127.0.0.1:1234")
    monkeypatch.setattr(config, "LM_STUDIO_MODEL", "test-model")

    tool_call_response = make_lm_response(
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_inventory_status", "arguments": "{}"},
        }],
        finish_reason="tool_calls",
    )
    final_response = make_lm_response(content="You have 50 roses in stock.")

    respx.post("http://127.0.0.1:1234/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json=tool_call_response),
            httpx.Response(200, json=final_response),
        ]
    )

    adapter = MagicMock()
    adapter.get.return_value = {"data": [{"item_code": "Rose", "actual_qty": 50}]}

    result = run_tool_loop(
        messages=[{"role": "user", "content": "What stock do I have?"}],
        tools=[],
        adapter=adapter,
        system_prompt="You are helpful.",
    )
    assert "roses" in result.lower() or "50" in result


def test_validate_tool_call_accepts_valid():
    tc = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_inventory_status", "arguments": "{}"},
    }
    assert validate_tool_call(tc) is True


def test_validate_tool_call_rejects_missing_fields():
    assert validate_tool_call({"id": "call_1"}) is False
    assert validate_tool_call({"function": {"name": "x"}}) is False


def test_validate_tool_call_rejects_invalid_json_args():
    tc = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_inventory_status", "arguments": "{invalid json}"},
    }
    assert validate_tool_call(tc) is False


def test_execute_tool_call_routes_to_correct_function():
    adapter = MagicMock()
    adapter.get.return_value = {"data": []}
    tc = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_inventory_status", "arguments": "{}"},
    }
    result = execute_tool_call(tc, adapter)
    assert isinstance(result, str)
    adapter.get.assert_called_once()
