import pytest
import respx
import httpx
from erpnext.adapter import ERPNextAdapter, ERPNextError


@pytest.fixture()
def adapter(monkeypatch):
    import config
    monkeypatch.setattr(config, "ERPNEXT_URL", "http://localhost:8000")
    monkeypatch.setattr(config, "ERPNEXT_API_KEY", "testkey")
    monkeypatch.setattr(config, "ERPNEXT_API_SECRET", "testsecret")
    return ERPNextAdapter()


@respx.mock
def test_get_success(adapter):
    respx.get("http://localhost:8000/api/resource/Customer").mock(
        return_value=httpx.Response(200, json={"data": [{"name": "Test Customer"}]})
    )
    result = adapter.get("/api/resource/Customer")
    assert result == {"data": [{"name": "Test Customer"}]}


@respx.mock
def test_get_raises_on_4xx(adapter):
    respx.get("http://localhost:8000/api/resource/Customer").mock(
        return_value=httpx.Response(401, json={"message": "Unauthorized"})
    )
    with pytest.raises(ERPNextError, match="401"):
        adapter.get("/api/resource/Customer")


@respx.mock
def test_post_success(adapter):
    respx.post("http://localhost:8000/api/resource/Customer").mock(
        return_value=httpx.Response(200, json={"data": {"name": "New Customer"}})
    )
    result = adapter.post("/api/resource/Customer", {"customer_name": "New Customer"})
    assert result["data"]["name"] == "New Customer"


@respx.mock
def test_put_success(adapter):
    respx.put("http://localhost:8000/api/resource/Item/ITEM-001").mock(
        return_value=httpx.Response(200, json={"data": {"name": "ITEM-001"}})
    )
    result = adapter.put("/api/resource/Item/ITEM-001", {"standard_rate": 25.0})
    assert result["data"]["name"] == "ITEM-001"


@respx.mock
def test_is_reachable_true(adapter):
    respx.get("http://localhost:8000/api/method/ping").mock(
        return_value=httpx.Response(200, json={"message": "pong"})
    )
    assert adapter.is_reachable() is True


@respx.mock
def test_is_reachable_false_on_connection_error(adapter):
    respx.get("http://localhost:8000/api/method/ping").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert adapter.is_reachable() is False


def test_auth_header_uses_token_format(adapter):
    assert adapter.headers["Authorization"] == "token testkey:testsecret"
