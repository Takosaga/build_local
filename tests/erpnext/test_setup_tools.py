import pytest
from unittest.mock import MagicMock
from erpnext.setup_tools import (
    create_company,
    enable_modules,
    set_tax_rate,
    create_customer,
    create_item,
    create_supplier,
)


def test_create_company_posts_correct_doctype(mock_adapter):
    create_company(mock_adapter, name="Bloom Flowers", currency="GBP", fiscal_year_start="01-01")
    mock_adapter.post.assert_called_once()
    call_args = mock_adapter.post.call_args
    assert call_args[0][0] == "/api/resource/Company"
    payload = call_args[0][1]
    assert payload["company_name"] == "Bloom Flowers"
    assert payload["default_currency"] == "GBP"


def test_create_company_returns_success_string(mock_adapter):
    result = create_company(mock_adapter, name="Bloom Flowers", currency="GBP", fiscal_year_start="01-01")
    assert "Bloom Flowers" in result
    assert "created" in result.lower()


def test_set_tax_rate_returns_success(mock_adapter):
    result = set_tax_rate(mock_adapter, rate=20.0, account_name="VAT 20%")
    assert "20" in result


def test_create_customer_returns_success(mock_adapter):
    result = create_customer(mock_adapter, name="Jane Smith", phone="07700900000")
    assert "Jane Smith" in result
    mock_adapter.post.assert_called_once()
    payload = mock_adapter.post.call_args[0][1]
    assert payload["customer_name"] == "Jane Smith"


def test_create_item_posts_to_item_endpoint(mock_adapter):
    result = create_item(mock_adapter, name="Rose Bouquet", price=25.0, item_group="Products")
    mock_adapter.post.assert_called_once()
    payload = mock_adapter.post.call_args[0][1]
    assert payload["item_name"] == "Rose Bouquet"
    assert payload["standard_rate"] == 25.0


def test_enable_modules_calls_system_settings(mock_adapter):
    result = enable_modules(mock_adapter, modules=["Selling", "Stock", "Accounts"])
    assert "enabled" in result.lower()
    mock_adapter.post.assert_called()


def test_create_supplier_success(mock_adapter):
    result = create_supplier(mock_adapter, name="City Wholesale", phone="01234567890")
    assert "City Wholesale" in result
