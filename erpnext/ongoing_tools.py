from erpnext.adapter import ERPNextAdapter


def get_sales_summary(adapter: ERPNextAdapter, from_date: str, to_date: str) -> str:
    data = adapter.get(
        "/api/resource/Sales Invoice",
        params={
            "filters": f'[["posting_date","Between",["{from_date}","{to_date}"]],["docstatus","=",1]]',
            "fields": '["grand_total","posting_date"]',
            "limit_page_length": 500,
        },
    )
    invoices = data.get("data", [])
    total = sum(i.get("grand_total", 0) for i in invoices)
    return f"Sales from {from_date} to {to_date}: {len(invoices)} invoices, total {total:.2f}."


def get_top_customers(adapter: ERPNextAdapter, limit: int = 5) -> str:
    data = adapter.get(
        "/api/resource/Sales Invoice",
        params={
            "filters": '[["docstatus","=",1]]',
            "fields": '["customer_name","grand_total"]',
            "limit_page_length": 500,
        },
    )
    totals: dict[str, float] = {}
    for inv in data.get("data", []):
        name = inv["customer_name"]
        totals[name] = totals.get(name, 0) + inv.get("grand_total", 0)
    sorted_customers = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    lines = [f"{i+1}. {name}: {total:.2f}" for i, (name, total) in enumerate(sorted_customers)]
    return "Top customers:\n" + "\n".join(lines) if lines else "No sales data found."


def get_inventory_status(adapter: ERPNextAdapter, item_code: str | None = None) -> str:
    params: dict = {
        "fields": '["item_code","actual_qty","warehouse"]',
        "limit_page_length": 200,
    }
    if item_code:
        params["filters"] = f'[["item_code","=","{item_code}"]]'
    data = adapter.get("/api/resource/Bin", params=params)
    items = data.get("data", [])
    if not items:
        return "No stock data found."
    lines = [f"{i['item_code']}: {i.get('actual_qty', 0)} units" for i in items]
    return "Inventory:\n" + "\n".join(lines)


def get_low_stock_items(adapter: ERPNextAdapter, threshold: int = 10) -> str:
    data = adapter.get(
        "/api/resource/Bin",
        params={
            "fields": '["item_code","actual_qty"]',
            "filters": f'[["actual_qty","<",{threshold}]]',
            "limit_page_length": 200,
        },
    )
    items = data.get("data", [])
    # Filter client-side to handle mocked responses that may return all items
    items = [i for i in items if i.get("actual_qty", 0) < threshold]
    if not items:
        return f"No items below {threshold} units."
    lines = [f"{i['item_code']}: {i.get('actual_qty', 0)} units" for i in items]
    return f"Low stock items (below {threshold}):\n" + "\n".join(lines)


def get_customer_history(adapter: ERPNextAdapter, customer_name: str) -> str:
    data = adapter.get(
        "/api/resource/Sales Invoice",
        params={
            "filters": f'[["customer_name","=","{customer_name}"],["docstatus","=",1]]',
            "fields": '["name","posting_date","grand_total"]',
            "limit_page_length": 20,
            "order_by": "posting_date desc",
        },
    )
    invoices = data.get("data", [])
    if not invoices:
        return f"No purchase history for {customer_name}."
    lines = [f"{i['posting_date']}: {i['name']} — {i.get('grand_total', 0):.2f}" for i in invoices]
    return f"History for {customer_name}:\n" + "\n".join(lines)


def create_invoice(adapter: ERPNextAdapter, customer: str, items: list[dict]) -> str:
    result = adapter.post(
        "/api/resource/Sales Invoice",
        {
            "customer": customer,
            "items": items,
            "docstatus": 1,
        },
    )
    name = result.get("data", {}).get("name", "unknown")
    return f"Invoice {name} created for {customer}."


def create_purchase_order(adapter: ERPNextAdapter, supplier: str, items: list[dict]) -> str:
    result = adapter.post(
        "/api/resource/Purchase Order",
        {
            "supplier": supplier,
            "items": items,
            "docstatus": 1,
        },
    )
    name = result.get("data", {}).get("name", "unknown")
    return f"Purchase order {name} created for {supplier}."


def update_item_price(adapter: ERPNextAdapter, item_code: str, new_price: float) -> str:
    adapter.put(
        f"/api/resource/Item/{item_code}",
        {"standard_rate": new_price},
    )
    return f"Price for '{item_code}' updated to {new_price:.2f}."
