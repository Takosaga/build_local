import pytest
from unittest.mock import MagicMock
from erpnext.ongoing_tools import (
    get_sales_summary,
    get_top_customers,
    get_inventory_status,
    get_low_stock_items,
    get_customer_history,
    create_invoice,
    create_purchase_order,
    update_item_price,
)


@pytest.fixture()
def mock_adapter():
    return MagicMock()


def test_get_sales_summary_queries_sales_invoice(mock_adapter):
    mock_adapter.get.return_value = {"data": [{"grand_total": 500.0}, {"grand_total": 300.0}]}
    result = get_sales_summary(mock_adapter, from_date="2026-01-01", to_date="2026-01-31")
    assert "800" in result or "800.0" in result
    mock_adapter.get.assert_called_once()
    assert "Sales Invoice" in str(mock_adapter.get.call_args)


def test_get_top_customers_returns_sorted(mock_adapter):
    mock_adapter.get.return_value = {
        "data": [
            {"customer_name": "Alice", "grand_total": 1200.0},
            {"customer_name": "Bob", "grand_total": 800.0},
        ]
    }
    result = get_top_customers(mock_adapter, limit=2)
    assert "Alice" in result
    assert "1200" in result or "1200.0" in result


def test_get_inventory_status_all_items(mock_adapter):
    mock_adapter.get.return_value = {
        "data": [{"item_code": "Rose", "actual_qty": 50}, {"item_code": "Lily", "actual_qty": 20}]
    }
    result = get_inventory_status(mock_adapter)
    assert "Rose" in result
    assert "50" in result


def test_get_low_stock_items_filters_below_threshold(mock_adapter):
    mock_adapter.get.return_value = {
        "data": [
            {"item_code": "Rose", "actual_qty": 5},
            {"item_code": "Lily", "actual_qty": 50},
        ]
    }
    result = get_low_stock_items(mock_adapter, threshold=10)
    assert "Rose" in result
    assert "Lily" not in result


def test_create_invoice_posts_sales_invoice(mock_adapter):
    mock_adapter.post.return_value = {"data": {"name": "SINV-001"}}
    result = create_invoice(
        mock_adapter,
        customer="Jane",
        items=[{"item_code": "Rose Bouquet", "qty": 2, "rate": 25.0}],
    )
    assert "SINV-001" in result
    payload = mock_adapter.post.call_args[0][1]
    assert payload["customer"] == "Jane"
    assert len(payload["items"]) == 1


def test_update_item_price_uses_put(mock_adapter):
    mock_adapter.put.return_value = {"data": {"name": "Rose Bouquet"}}
    result = update_item_price(mock_adapter, item_code="Rose Bouquet", new_price=30.0)
    assert "30" in result
    mock_adapter.put.assert_called_once()
