from erpnext.adapter import ERPNextAdapter


def create_company(adapter: ERPNextAdapter, name: str, currency: str, fiscal_year_start: str) -> str:
    adapter.post("/api/resource/Company", {
        "company_name": name,
        "abbr": name[:3].upper(),
        "default_currency": currency,
        "country": "United Kingdom",
    })
    return f"Company '{name}' created with currency {currency}."


def enable_modules(adapter: ERPNextAdapter, modules: list[str]) -> str:
    for module in modules:
        try:
            adapter.post("/api/resource/Module Def", {"module_name": module, "app_name": "erpnext"})
        except Exception:
            pass  # Module may already exist
    return f"Modules enabled: {', '.join(modules)}."


def setup_chart_of_accounts(adapter: ERPNextAdapter, company: str, business_type: str) -> str:
    adapter.post("/api/method/erpnext.accounts.doctype.account.account.sync_chart_of_accounts_with_template", {
        "company": company,
    })
    return f"Chart of accounts configured for {business_type} business."


def set_tax_rate(adapter: ERPNextAdapter, rate: float, account_name: str) -> str:
    adapter.post("/api/resource/Account", {
        "account_name": account_name,
        "account_type": "Tax",
        "tax_rate": rate,
    })
    return f"Tax account '{account_name}' set at {rate}%."


def create_customer(adapter: ERPNextAdapter, name: str, phone: str = "", email: str = "") -> str:
    data = {"customer_name": name, "customer_type": "Individual", "customer_group": "All Customer Groups"}
    if phone:
        data["mobile_no"] = phone
    if email:
        data["email_id"] = email
    adapter.post("/api/resource/Customer", data)
    return f"Customer '{name}' created."


def create_customers_bulk(adapter: ERPNextAdapter, customers: list[dict]) -> str:
    created = []
    failed = []
    for c in customers:
        try:
            create_customer(adapter, **c)
            created.append(c["name"])
        except Exception as e:
            failed.append(f"{c['name']} ({e})")
    result = f"Created {len(created)} customers."
    if failed:
        result += f" Failed: {', '.join(failed)}."
    return result


def create_item(adapter: ERPNextAdapter, name: str, price: float, item_group: str = "All Item Groups") -> str:
    adapter.post("/api/resource/Item", {
        "item_name": name,
        "item_code": name,
        "item_group": item_group,
        "standard_rate": price,
        "is_sales_item": 1,
    })
    return f"Item '{name}' created at price {price}."


def create_items_bulk(adapter: ERPNextAdapter, items: list[dict]) -> str:
    created = []
    failed = []
    for item in items:
        try:
            create_item(adapter, **item)
            created.append(item["name"])
        except Exception as e:
            failed.append(f"{item['name']} ({e})")
    result = f"Created {len(created)} items."
    if failed:
        result += f" Failed: {', '.join(failed)}."
    return result


def create_supplier(adapter: ERPNextAdapter, name: str, phone: str = "", email: str = "") -> str:
    data = {"supplier_name": name, "supplier_group": "All Supplier Groups", "supplier_type": "Company"}
    if phone:
        data["mobile_no"] = phone
    adapter.post("/api/resource/Supplier", data)
    return f"Supplier '{name}' created."
