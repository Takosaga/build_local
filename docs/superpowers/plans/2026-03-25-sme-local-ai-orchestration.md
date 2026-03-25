# SME Local AI Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python/FastAPI orchestration layer that lets non-technical SME owners set up and interact with ERPNext using plain language via a local LLM.

**Architecture:** FastAPI backend (127.0.0.1:8080) serves a browser UI. User messages go to LM Studio (Qwen 3.5-9B at 127.0.0.1:1234) with predefined tool definitions. The LLM returns tool calls that FastAPI executes against the ERPNext v15 REST API. Responses stream back to the browser via Server-Sent Events.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, httpx, Jinja2, python-dotenv, sqlite3 (stdlib), uv for environment management. Tests: pytest, pytest-asyncio, respx (httpx mocking).

---

## File Map

```
build_local/
├── pyproject.toml            # All dependencies
├── .gitignore
├── config.py                 # Loads .env settings
├── main.py                   # FastAPI app, routes, SSE endpoint
├── installer.py              # Prereq checks, .env writer, server launcher
├── data/
│   └── app.db                # SQLite (created at runtime, not committed)
├── db/
│   └── session.py            # SQLite init, conversation + wizard state CRUD
├── erpnext/
│   ├── adapter.py            # Frappe REST API wrapper (GET/POST/PUT + auth)
│   ├── setup_tools.py        # Setup-phase tool functions
│   └── ongoing_tools.py      # Query + action tool functions
├── llm/
│   ├── tools.py              # JSON schema tool definitions sent to LLM
│   ├── prompts.py            # System prompts for setup vs ongoing mode
│   └── client.py             # LM Studio API, tool call loop, SSE stream
├── wizard/
│   ├── state.py              # Wizard step transitions, SQLite-backed
│   └── flow.py               # Step logic, question counting, mode routing
└── ui/
    ├── static/
    │   ├── style.css
    │   └── app.js            # SSE client, spinner, chat rendering
    └── templates/
        ├── base.html         # Shared layout
        ├── wizard.html       # Setup wizard UI
        └── chat.html         # Ongoing chat interface
tests/
├── conftest.py               # Shared fixtures (mock adapter, test DB)
├── test_session.py
├── erpnext/
│   ├── test_adapter.py
│   ├── test_setup_tools.py
│   └── test_ongoing_tools.py
├── llm/
│   ├── test_tools.py
│   └── test_client.py
└── wizard/
    ├── test_state.py
    └── test_flow.py
```

---

## Task 1: Project Foundation

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `config.py`
- Create: `db/__init__.py`, `db/session.py`
- Create: `tests/conftest.py`, `tests/test_session.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "build-local"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "httpx>=0.27.0",
    "jinja2>=3.1.4",
    "python-multipart>=0.0.9",
    "python-dotenv>=1.0.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "respx>=0.21.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `.gitignore`**

```
.env
.venv/
__pycache__/
*.pyc
data/
.pytest_cache/
*.egg-info/
dist/
```

- [ ] **Step 3: Create `config.py`**

```python
from dotenv import load_dotenv
import os

load_dotenv()

ERPNEXT_URL = os.getenv("ERPNEXT_URL", "http://localhost:8000")
ERPNEXT_API_KEY = os.getenv("ERPNEXT_API_KEY", "")
ERPNEXT_API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3.5-9b")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8080"))
```

- [ ] **Step 4: Create `db/__init__.py`** (empty file)

- [ ] **Step 5: Write failing tests for `db/session.py`**

Create `tests/test_session.py`:

```python
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    """Redirect DB to a temp file for each test."""
    import db.session as session
    monkeypatch.setattr(session, "DB_PATH", tmp_path / "test.db")
    session.init_db()
    yield


def test_init_db_creates_tables():
    from db.session import get_connection
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {t["name"] for t in tables}
    assert "messages" in names
    assert "wizard_state" in names


def test_save_and_load_message():
    from db.session import save_message, load_conversation
    save_message("user", "hello")
    save_message("assistant", "hi there")
    history = load_conversation()
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "hello"}
    assert history[1] == {"role": "assistant", "content": "hi there"}


def test_load_conversation_respects_limit():
    from db.session import save_message, load_conversation
    for i in range(50):
        save_message("user", f"message {i}")
    history = load_conversation(limit=40)
    assert len(history) == 40


def test_wizard_state_defaults():
    from db.session import load_wizard_state
    state = load_wizard_state()
    assert state["current_step"] == 0
    assert state["completed_steps"] == []
    assert state["business_data"] == {}
    assert state["is_complete"] is False


def test_save_and_load_wizard_state():
    from db.session import save_wizard_state, load_wizard_state
    save_wizard_state(
        current_step=2,
        completed_steps=[0, 1],
        business_data={"name": "Bloom Flowers"},
        is_complete=False,
    )
    state = load_wizard_state()
    assert state["current_step"] == 2
    assert state["completed_steps"] == [0, 1]
    assert state["business_data"]["name"] == "Bloom Flowers"
```

- [ ] **Step 6: Run tests — verify they fail**

```bash
uv run pytest tests/test_session.py -v
```
Expected: `ModuleNotFoundError: No module named 'db.session'`

- [ ] **Step 7: Create `db/session.py`**

```python
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/app.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS wizard_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_step INTEGER DEFAULT 0,
                completed_steps TEXT DEFAULT '[]',
                business_data TEXT DEFAULT '{}',
                is_complete INTEGER DEFAULT 0
            );
        """)
        conn.execute("INSERT OR IGNORE INTO wizard_state (id) VALUES (1)")


def load_conversation(limit: int = 40) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def save_message(role: str, content: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
        )


def load_wizard_state() -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM wizard_state WHERE id = 1").fetchone()
    return {
        "current_step": row["current_step"],
        "completed_steps": json.loads(row["completed_steps"]),
        "business_data": json.loads(row["business_data"]),
        "is_complete": bool(row["is_complete"]),
    }


def save_wizard_state(
    current_step: int,
    completed_steps: list,
    business_data: dict,
    is_complete: bool = False,
):
    with get_connection() as conn:
        conn.execute(
            """UPDATE wizard_state SET
                current_step = ?,
                completed_steps = ?,
                business_data = ?,
                is_complete = ?
               WHERE id = 1""",
            (
                current_step,
                json.dumps(completed_steps),
                json.dumps(business_data),
                int(is_complete),
            ),
        )
```

- [ ] **Step 8: Run tests — verify they pass**

```bash
uv run pytest tests/test_session.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 9: Create `tests/conftest.py`** with shared DB fixture for reuse

```python
import pytest


@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    import db.session as session
    monkeypatch.setattr(session, "DB_PATH", tmp_path / "test.db")
    session.init_db()
    yield
```

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml .gitignore config.py db/ tests/
git commit -m "feat: project foundation — config, SQLite session, tests"
```

---

## Task 2: ERPNext Adapter

**Files:**
- Create: `erpnext/__init__.py`
- Create: `erpnext/adapter.py`
- Create: `tests/erpnext/__init__.py`, `tests/erpnext/test_adapter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/erpnext/test_adapter.py`:

```python
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
```

- [ ] **Step 2: Run — verify failure**

```bash
uv run pytest tests/erpnext/test_adapter.py -v
```
Expected: `ModuleNotFoundError: No module named 'erpnext'`

- [ ] **Step 3: Create `erpnext/__init__.py`** (empty)

- [ ] **Step 4: Create `erpnext/adapter.py`**

```python
import httpx
import config


class ERPNextError(Exception):
    pass


class ERPNextAdapter:
    def __init__(self):
        self.base_url = config.ERPNEXT_URL
        self.headers = {
            "Authorization": f"token {config.ERPNEXT_API_KEY}:{config.ERPNEXT_API_SECRET}",
            "Content-Type": "application/json",
        }

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        with httpx.Client() as client:
            resp = client.get(
                f"{self.base_url}{endpoint}", headers=self.headers, params=params
            )
        if not resp.is_success:
            raise ERPNextError(f"ERPNext GET {endpoint} failed {resp.status_code}: {resp.text}")
        return resp.json()

    def post(self, endpoint: str, data: dict) -> dict:
        with httpx.Client() as client:
            resp = client.post(
                f"{self.base_url}{endpoint}", headers=self.headers, json=data
            )
        if not resp.is_success:
            raise ERPNextError(f"ERPNext POST {endpoint} failed {resp.status_code}: {resp.text}")
        return resp.json()

    def put(self, endpoint: str, data: dict) -> dict:
        with httpx.Client() as client:
            resp = client.put(
                f"{self.base_url}{endpoint}", headers=self.headers, json=data
            )
        if not resp.is_success:
            raise ERPNextError(f"ERPNext PUT {endpoint} failed {resp.status_code}: {resp.text}")
        return resp.json()

    def is_reachable(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/method/ping")
            return resp.is_success
        except Exception:
            return False
```

- [ ] **Step 5: Run — verify all pass**

```bash
uv run pytest tests/erpnext/test_adapter.py -v
```
Expected: 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add erpnext/ tests/erpnext/
git commit -m "feat: ERPNext adapter with token auth and error handling"
```

---

## Task 3: ERPNext Setup Tools

**Files:**
- Create: `erpnext/setup_tools.py`
- Create: `tests/erpnext/test_setup_tools.py`

The setup tools wrap adapter calls for wizard use. Each returns a plain-text result string for the LLM.

- [ ] **Step 1: Write failing tests**

Create `tests/erpnext/test_setup_tools.py`:

```python
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


@pytest.fixture()
def mock_adapter():
    adapter = MagicMock()
    adapter.post.return_value = {"data": {"name": "ok"}}
    adapter.put.return_value = {"data": {"name": "ok"}}
    adapter.get.return_value = {"data": []}
    return adapter


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
```

- [ ] **Step 2: Run — verify failure**

```bash
uv run pytest tests/erpnext/test_setup_tools.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `erpnext/setup_tools.py`**

```python
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
    # Frappe stores active modules in the Module Def doctype
    for module in modules:
        try:
            adapter.post("/api/resource/Module Def", {"module_name": module, "app_name": "erpnext"})
        except Exception:
            pass  # Module may already exist
    return f"Modules enabled: {', '.join(modules)}."


def setup_chart_of_accounts(adapter: ERPNextAdapter, company: str, business_type: str) -> str:
    # ERPNext auto-creates chart of accounts on company creation; this triggers a refresh
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
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/erpnext/test_setup_tools.py -v
```
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add erpnext/setup_tools.py tests/erpnext/test_setup_tools.py
git commit -m "feat: ERPNext setup tools (company, items, customers, suppliers)"
```

---

## Task 4: ERPNext Ongoing Tools

**Files:**
- Create: `erpnext/ongoing_tools.py`
- Create: `tests/erpnext/test_ongoing_tools.py`

- [ ] **Step 1: Write failing tests**

Create `tests/erpnext/test_ongoing_tools.py`:

```python
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
```

- [ ] **Step 2: Run — verify failure**

```bash
uv run pytest tests/erpnext/test_ongoing_tools.py -v
```

- [ ] **Step 3: Create `erpnext/ongoing_tools.py`**

```python
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
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/erpnext/test_ongoing_tools.py -v
```

- [ ] **Step 5: Commit**

```bash
git add erpnext/ongoing_tools.py tests/erpnext/test_ongoing_tools.py
git commit -m "feat: ERPNext ongoing tools (query, invoice, purchase order, price)"
```

---

## Task 5: LLM Tool Definitions & Prompts

**Files:**
- Create: `llm/__init__.py`
- Create: `llm/tools.py`
- Create: `llm/prompts.py`
- Create: `tests/llm/__init__.py`, `tests/llm/test_tools.py`

- [ ] **Step 1: Write failing tests**

Create `tests/llm/test_tools.py`:

```python
from llm.tools import get_all_tools, TOOL_NAMES


def test_all_tools_are_valid_openai_schema():
    tools = get_all_tools()
    assert len(tools) > 0
    for tool in tools:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_tool_names_match_definitions():
    tools = get_all_tools()
    defined_names = {t["function"]["name"] for t in tools}
    for name in TOOL_NAMES:
        assert name in defined_names, f"Tool {name} in TOOL_NAMES but not in get_all_tools()"


def test_write_tools_are_marked():
    from llm.tools import WRITE_TOOLS
    assert "create_invoice" in WRITE_TOOLS
    assert "create_purchase_order" in WRITE_TOOLS
    assert "update_item_price" in WRITE_TOOLS
    assert "get_sales_summary" not in WRITE_TOOLS


def test_setup_tools_are_marked():
    from llm.tools import SETUP_TOOLS
    assert "create_company" in SETUP_TOOLS
    assert "enable_modules" in SETUP_TOOLS
    assert "create_invoice" not in SETUP_TOOLS
```

- [ ] **Step 2: Run — verify failure**

```bash
uv run pytest tests/llm/test_tools.py -v
```

- [ ] **Step 3: Create `llm/__init__.py`** (empty)

- [ ] **Step 4: Create `llm/tools.py`**

```python
# Tool definitions in OpenAI function-calling format.
# Sent with every LLM request so the model knows what actions are available.

SETUP_TOOLS = {
    "create_company", "enable_modules", "setup_chart_of_accounts",
    "create_item", "create_items_bulk", "create_customer", "create_customers_bulk",
    "create_supplier", "set_tax_rate",
}

WRITE_TOOLS = {"create_invoice", "create_purchase_order", "update_item_price"}

TOOL_NAMES = SETUP_TOOLS | WRITE_TOOLS | {
    "get_sales_summary", "get_top_customers", "get_inventory_status",
    "get_low_stock_items", "get_customer_history", "draft_content",
}

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_company",
            "description": "Create the company record in ERPNext with name, currency and fiscal year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Legal company name"},
                    "currency": {"type": "string", "description": "ISO currency code, e.g. GBP"},
                    "fiscal_year_start": {"type": "string", "description": "Month-day, e.g. 01-01"},
                },
                "required": ["name", "currency", "fiscal_year_start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enable_modules",
            "description": "Enable a list of ERPNext modules for the company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Module names, e.g. ['Selling', 'Stock', 'Accounts']",
                    }
                },
                "required": ["modules"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_tax_rate",
            "description": "Set the default tax rate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rate": {"type": "number", "description": "Tax percentage, e.g. 20.0"},
                    "account_name": {"type": "string", "description": "Tax account name, e.g. 'VAT 20%'"},
                },
                "required": ["rate", "account_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_customer",
            "description": "Create a single customer record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_customers_bulk",
            "description": "Create multiple customer records at once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "phone": {"type": "string"},
                                "email": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    }
                },
                "required": ["customers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_item",
            "description": "Create a single product or service item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "item_group": {"type": "string"},
                },
                "required": ["name", "price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_items_bulk",
            "description": "Create multiple items at once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "price": {"type": "number"},
                                "item_group": {"type": "string"},
                            },
                            "required": ["name", "price"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_supplier",
            "description": "Create a supplier record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Get total sales for a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "to_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["from_date", "to_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_customers",
            "description": "Get the top customers by total spend.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of customers to return (default 5)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_status",
            "description": "Get current stock levels. Omit item_code to get all items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock_items",
            "description": "Get items below a stock threshold.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {"type": "integer", "description": "Stock level below which to flag items"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_history",
            "description": "Get order history for a specific customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                },
                "required": ["customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_invoice",
            "description": "Create a sales invoice. Only call after user has confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_code": {"type": "string"},
                                "qty": {"type": "number"},
                                "rate": {"type": "number"},
                            },
                            "required": ["item_code", "qty", "rate"],
                        },
                    },
                },
                "required": ["customer", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_purchase_order",
            "description": "Create a purchase order. Only call after user has confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_code": {"type": "string"},
                                "qty": {"type": "number"},
                                "rate": {"type": "number"},
                            },
                            "required": ["item_code", "qty", "rate"],
                        },
                    },
                },
                "required": ["supplier", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_item_price",
            "description": "Update the price of an item. Only call after user has confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": {"type": "string"},
                    "new_price": {"type": "number"},
                },
                "required": ["item_code", "new_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_content",
            "description": "Generate written content such as emails, product descriptions, or announcements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content_type": {
                        "type": "string",
                        "enum": ["email", "product_description", "announcement"],
                    },
                    "context": {"type": "string", "description": "Details to include in the content"},
                },
                "required": ["content_type", "context"],
            },
        },
    },
]


def get_all_tools() -> list[dict]:
    return _TOOL_DEFINITIONS


def get_setup_tools() -> list[dict]:
    return [t for t in _TOOL_DEFINITIONS if t["function"]["name"] in SETUP_TOOLS]


def get_ongoing_tools() -> list[dict]:
    return [t for t in _TOOL_DEFINITIONS if t["function"]["name"] not in SETUP_TOOLS]
```

- [ ] **Step 5: Create `llm/prompts.py`**

```python
SETUP_SYSTEM_PROMPT = """You are a friendly AI assistant helping a small business owner set up ERPNext for their business.

You are currently in setup mode. Your goals:
1. Gather information about the business through natural conversation.
2. Use the available tools to configure ERPNext based on what you learn.
3. Ask one question at a time. Be friendly, concise, and non-technical.
4. When you have enough information, use tools to configure ERPNext, then summarise what you've done.

Business context: {business_name}, {business_type}, located in {location}.

Current setup step: {current_step}
Questions asked so far: {questions_asked} of 5 maximum.

After 5 questions or when you have sufficient information, stop asking and proceed to configure ERPNext."""


ONGOING_SYSTEM_PROMPT = """You are a helpful business assistant for {business_name}, a {business_type} business.

You help the owner by:
- Answering questions about their business data (sales, customers, stock)
- Helping with tasks like creating invoices and purchase orders
- Drafting emails, product descriptions, and other business content

Rules:
- Be concise and friendly. Avoid jargon.
- For any action that writes data (creating invoices, purchase orders, changing prices), ALWAYS describe what you are about to do and ask for confirmation BEFORE calling the tool. Wait for the user to say yes before proceeding.
- If the user says no or cancels, acknowledge it: "No problem, I've cancelled that." Do not retry unless asked.
- If a tool call fails, explain what went wrong in plain language. Do not show error codes or stack traces."""


def get_setup_prompt(business_name: str, business_type: str, location: str, questions_asked: int, current_step: int) -> str:
    return SETUP_SYSTEM_PROMPT.format(
        business_name=business_name,
        business_type=business_type,
        location=location,
        questions_asked=questions_asked,
        current_step=current_step,
    )


def get_ongoing_prompt(business_name: str, business_type: str) -> str:
    return ONGOING_SYSTEM_PROMPT.format(
        business_name=business_name,
        business_type=business_type,
    )
```

- [ ] **Step 6: Run — verify all pass**

```bash
uv run pytest tests/llm/test_tools.py -v
```
Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add llm/ tests/llm/
git commit -m "feat: LLM tool definitions and system prompts"
```

---

## Task 6: LLM Client

**Files:**
- Create: `llm/client.py`
- Create: `tests/llm/test_client.py`

The client runs the tool call loop synchronously, then returns the final text. It also dispatches tool calls to the correct erpnext function.

- [ ] **Step 1: Write failing tests**

Create `tests/llm/test_client.py`:

```python
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
```

- [ ] **Step 2: Run — verify failure**

```bash
uv run pytest tests/llm/test_client.py -v
```

- [ ] **Step 3: Create `llm/client.py`**

```python
import json
import httpx
import config
from erpnext.adapter import ERPNextAdapter
from erpnext import setup_tools, ongoing_tools


# Maps tool name → function(adapter, **kwargs) → str
_TOOL_DISPATCH: dict[str, callable] = {
    "create_company": setup_tools.create_company,
    "enable_modules": setup_tools.enable_modules,
    "setup_chart_of_accounts": setup_tools.setup_chart_of_accounts,
    "set_tax_rate": setup_tools.set_tax_rate,
    "create_customer": setup_tools.create_customer,
    "create_customers_bulk": setup_tools.create_customers_bulk,
    "create_item": setup_tools.create_item,
    "create_items_bulk": setup_tools.create_items_bulk,
    "create_supplier": setup_tools.create_supplier,
    "get_sales_summary": ongoing_tools.get_sales_summary,
    "get_top_customers": ongoing_tools.get_top_customers,
    "get_inventory_status": ongoing_tools.get_inventory_status,
    "get_low_stock_items": ongoing_tools.get_low_stock_items,
    "get_customer_history": ongoing_tools.get_customer_history,
    "create_invoice": ongoing_tools.create_invoice,
    "create_purchase_order": ongoing_tools.create_purchase_order,
    "update_item_price": ongoing_tools.update_item_price,
}

MAX_LOOP_ITERATIONS = 10


def validate_tool_call(tool_call: dict) -> bool:
    """Return True if tool_call has the required fields and valid JSON arguments."""
    try:
        fn = tool_call.get("function", {})
        if not tool_call.get("id") or not fn.get("name") or "arguments" not in fn:
            return False
        json.loads(fn["arguments"])
        return True
    except (json.JSONDecodeError, AttributeError):
        return False


def execute_tool_call(tool_call: dict, adapter: ERPNextAdapter) -> str:
    """Execute a validated tool call and return a plain-text result."""
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])

    # draft_content is handled by the LLM itself — no ERPNext call needed
    if name == "draft_content":
        return f"[Draft content request: {args.get('context', '')}]"

    fn = _TOOL_DISPATCH.get(name)
    if fn is None:
        return f"Unknown tool: {name}"

    try:
        return fn(adapter, **args)
    except Exception as e:
        return f"Tool '{name}' failed: {str(e)}"


def _call_lm_studio(messages: list[dict], tools: list[dict]) -> dict:
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{config.LM_STUDIO_URL}/v1/chat/completions",
            json={
                "model": config.LM_STUDIO_MODEL,
                "messages": messages,
                "tools": tools,
                "stream": False,
            },
        )
    resp.raise_for_status()
    return resp.json()


def run_tool_loop(
    messages: list[dict],
    tools: list[dict],
    adapter: ERPNextAdapter,
    system_prompt: str,
) -> str:
    """
    Run the LM Studio tool call loop synchronously.
    Returns the final text response from the LLM.
    """
    loop_messages = [{"role": "system", "content": system_prompt}] + messages

    for _ in range(MAX_LOOP_ITERATIONS):
        try:
            response = _call_lm_studio(loop_messages, tools)
        except httpx.ConnectError:
            return "The AI model isn't running. Please open LM Studio and load the model."
        except Exception as e:
            return f"Could not reach the AI model: {str(e)}"

        choice = response["choices"][0]
        finish_reason = choice.get("finish_reason", "stop")
        message = choice["message"]

        if finish_reason == "stop" or not message.get("tool_calls"):
            return message.get("content") or "I couldn't generate a response. Please try again."

        # Process tool calls
        tool_calls = message["tool_calls"]
        loop_messages.append({"role": "assistant", "tool_calls": tool_calls, "content": None})

        tool_results = []
        for tc in tool_calls:
            if not validate_tool_call(tc):
                # Retry once with a correction prompt
                loop_messages.append({
                    "role": "user",
                    "content": "Your last response had an invalid tool call format. Please try again with valid JSON arguments.",
                })
                break
            result = execute_tool_call(tc, adapter)
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })
        else:
            loop_messages.extend(tool_results)

    return "I'm having trouble completing that request. Please try again."


def is_lm_studio_reachable() -> bool:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{config.LM_STUDIO_URL}/v1/models")
        return resp.is_success
    except Exception:
        return False
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/llm/test_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add llm/client.py tests/llm/test_client.py
git commit -m "feat: LLM client — tool call loop, dispatch, validation"
```

---

## Task 7: Wizard State Machine

**Files:**
- Create: `wizard/__init__.py`
- Create: `wizard/state.py`
- Create: `wizard/flow.py`
- Create: `tests/wizard/__init__.py`, `tests/wizard/test_state.py`, `tests/wizard/test_flow.py`

- [ ] **Step 1: Write failing tests for `wizard/state.py`**

Create `tests/wizard/test_state.py`:

```python
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
```

- [ ] **Step 2: Run — verify failure**

```bash
uv run pytest tests/wizard/test_state.py -v
```

- [ ] **Step 3: Create `wizard/__init__.py`** (empty)

- [ ] **Step 4: Create `wizard/state.py`**

```python
from dataclasses import dataclass, field
import db.session as session


@dataclass
class WizardState:
    current_step: int
    completed_steps: list[int]
    business_data: dict
    is_complete: bool


def get_state() -> WizardState:
    raw = session.load_wizard_state()
    return WizardState(**raw)


def advance_step(business_data: dict | None = None):
    state = get_state()
    if business_data:
        merged = {**state.business_data, **business_data}
    else:
        merged = state.business_data
    completed = list(set(state.completed_steps + [state.current_step]))
    session.save_wizard_state(
        current_step=state.current_step + 1,
        completed_steps=completed,
        business_data=merged,
    )


def update_business_data(data: dict):
    state = get_state()
    merged = {**state.business_data, **data}
    session.save_wizard_state(
        current_step=state.current_step,
        completed_steps=state.completed_steps,
        business_data=merged,
    )


def mark_complete():
    state = get_state()
    session.save_wizard_state(
        current_step=state.current_step,
        completed_steps=state.completed_steps,
        business_data=state.business_data,
        is_complete=True,
    )


def reset():
    session.save_wizard_state(
        current_step=0,
        completed_steps=[],
        business_data={},
        is_complete=False,
    )
```

- [ ] **Step 5: Run — verify state tests pass**

```bash
uv run pytest tests/wizard/test_state.py -v
```

- [ ] **Step 6: Write failing tests for `wizard/flow.py`**

Create `tests/wizard/test_flow.py`:

```python
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
```

- [ ] **Step 7: Create `wizard/flow.py`**

```python
"""
Flow logic: determines the current mode (setup vs ongoing) and
enforces the maximum question count during info-gathering step.
Question count is stored in wizard business_data to persist across restarts.
"""
from wizard.state import get_state, update_business_data

QUESTION_KEY = "_questions_asked"
MAX_QUESTIONS = 5


def get_mode() -> str:
    """Returns 'setup' or 'ongoing'."""
    return "ongoing" if get_state().is_complete else "setup"


def get_questions_asked() -> int:
    state = get_state()
    return state.business_data.get(QUESTION_KEY, 0)


def increment_questions_asked():
    count = get_questions_asked()
    update_business_data({QUESTION_KEY: count + 1})


def should_advance_from_info_step() -> bool:
    return get_questions_asked() >= MAX_QUESTIONS
```

- [ ] **Step 8: Run all wizard tests**

```bash
uv run pytest tests/wizard/ -v
```
Expected: all 11 tests PASS

- [ ] **Step 9: Commit**

```bash
git add wizard/ tests/wizard/
git commit -m "feat: wizard state machine and flow logic"
```

---

## Task 8: FastAPI App & UI

**Files:**
- Create: `main.py`
- Create: `ui/templates/base.html`
- Create: `ui/templates/wizard.html`
- Create: `ui/templates/chat.html`
- Create: `ui/static/style.css`
- Create: `ui/static/app.js`

- [ ] **Step 1: Create `main.py`**

```python
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

import config
from db.session import init_db, save_message, load_conversation
from erpnext.adapter import ERPNextAdapter
from llm.client import run_tool_loop, is_lm_studio_reachable
from llm.tools import get_setup_tools, get_ongoing_tools
from llm.prompts import get_setup_prompt, get_ongoing_prompt
from wizard.state import get_state, update_business_data, mark_complete, reset
from wizard.flow import get_mode, increment_questions_asked, should_advance_from_info_step


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="ui/static"), name="static")
templates = Jinja2Templates(directory="ui/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    state = get_state()
    if state.is_complete:
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "business_name": state.business_data.get("name", "Your Business"),
        })
    return templates.TemplateResponse("wizard.html", {
        "request": request,
        "step": state.current_step,
        "business_data": state.business_data,
    })


@app.post("/wizard/start")
async def wizard_start(
    business_name: str = Form(...),
    business_type: str = Form(...),
    location: str = Form(...),
    employees: str = Form(...),
):
    update_business_data({
        "name": business_name,
        "type": business_type,
        "location": location,
        "employees": employees,
    })
    from wizard.state import advance_step
    advance_step()
    return {"status": "ok", "step": 1}


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "").strip()
    if not user_message:
        return {"error": "Empty message"}

    save_message("user", user_message)
    history = load_conversation(limit=40)

    state = get_state()
    mode = get_mode()
    adapter = ERPNextAdapter()

    if mode == "setup":
        system_prompt = get_setup_prompt(
            business_name=state.business_data.get("name", "your business"),
            business_type=state.business_data.get("type", "business"),
            location=state.business_data.get("location", ""),
            questions_asked=state.business_data.get("_questions_asked", 0),
            current_step=state.current_step,
        )
        tools = get_setup_tools()
        increment_questions_asked()
    else:
        system_prompt = get_ongoing_prompt(
            business_name=state.business_data.get("name", "your business"),
            business_type=state.business_data.get("type", "business"),
        )
        tools = get_ongoing_tools()

    # Run tool loop synchronously in thread pool to avoid blocking event loop
    response_text = await asyncio.to_thread(
        run_tool_loop,
        messages=history,
        tools=tools,
        adapter=adapter,
        system_prompt=system_prompt,
    )

    save_message("assistant", response_text)

    # Check if wizard should auto-advance from info-gathering step
    if mode == "setup" and should_advance_from_info_step() and state.current_step == 2:
        from wizard.state import advance_step
        advance_step()

    async def token_stream():
        for char in response_text:
            yield f"data: {json.dumps({'delta': char})}\n\n"
            await asyncio.sleep(0)
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")


@app.post("/wizard/upload")
async def wizard_upload(file: UploadFile = File(...), doctype: str = Form(...)):
    """Accept a CSV file upload and pass it to the import_csv setup tool."""
    import csv
    import io
    from erpnext.setup_tools import import_csv as tool_import_csv
    contents = await file.read()
    text = contents.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    adapter = ERPNextAdapter()
    result = tool_import_csv(adapter, rows=rows, doctype=doctype)
    return {"result": result}


@app.post("/wizard/finalise")
async def wizard_finalise():
    mark_complete()
    return {"status": "ok"}


@app.post("/wizard/reset")
async def wizard_reset():
    reset()
    return {"status": "ok"}


@app.get("/health")
async def health():
    adapter = ERPNextAdapter()
    return {
        "lm_studio": is_lm_studio_reachable(),
        "erpnext": adapter.is_reachable(),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=config.FASTAPI_PORT, reload=False)
```

- [ ] **Step 2: Create `ui/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Business Assistant{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <div class="header-inner">
      <span class="logo">🏪 Business Assistant</span>
      {% if show_settings %}
      <nav>
        <a href="#" onclick="resetWizard()">Restart Setup</a>
      </nav>
      {% endif %}
    </div>
  </header>
  <main>
    {% block content %}{% endblock %}
  </main>
  <script src="/static/app.js"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: Create `ui/templates/wizard.html`**

```html
{% extends "base.html" %}
{% block title %}Setup — Business Assistant{% endblock %}
{% block content %}

{% if step == 0 %}
<div class="wizard-form">
  <h1>Welcome! Let's set up your business.</h1>
  <p class="subtitle">This takes about 5 minutes. We'll configure everything for you.</p>
  <form id="start-form">
    <label>Business name <input type="text" name="business_name" required placeholder="e.g. Bloom Flower Shop"></label>
    <label>Business type <input type="text" name="business_type" required placeholder="e.g. Flower Shop, Café, Hair Salon"></label>
    <label>City / region <input type="text" name="location" required placeholder="e.g. Manchester"></label>
    <label>Number of employees
      <select name="employees">
        <option>Just me</option>
        <option>2–5</option>
        <option>6–15</option>
        <option>16+</option>
      </select>
    </label>
    <button type="submit">Continue →</button>
  </form>
</div>

{% else %}
<div class="chat-container">
  <div id="messages" class="messages"></div>
  <div id="spinner" class="spinner hidden">AI is thinking…</div>
  <form id="chat-form" class="chat-input">
    <input type="text" id="user-input" placeholder="Type your reply…" autocomplete="off">
    <button type="submit">Send</button>
  </form>
  {% if step >= 4 %}
  <div class="finalise-bar">
    <button onclick="finaliseSetup()" class="btn-primary">✅ Finalise Setup</button>
  </div>
  {% endif %}
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 4: Create `ui/templates/chat.html`**

```html
{% extends "base.html" %}
{% set show_settings = true %}
{% block title %}{{ business_name }} — Business Assistant{% endblock %}
{% block content %}
<div class="chat-container">
  <div id="messages" class="messages"></div>
  <div id="spinner" class="spinner hidden">AI is thinking…</div>
  <form id="chat-form" class="chat-input">
    <input type="text" id="user-input" placeholder="Ask me anything about your business…" autocomplete="off">
    <button type="submit">Send</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Create `ui/static/style.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body { font-family: system-ui, sans-serif; background: #f8fafc; color: #1e293b; min-height: 100vh; }

header { background: #1e293b; color: white; padding: 0 1.5rem; height: 56px; display: flex; align-items: center; }
.header-inner { display: flex; justify-content: space-between; align-items: center; width: 100%; max-width: 800px; margin: 0 auto; }
.logo { font-weight: 600; font-size: 1.1rem; }
nav a { color: #94a3b8; text-decoration: none; font-size: 0.9rem; }
nav a:hover { color: white; }

main { max-width: 800px; margin: 2rem auto; padding: 0 1rem; }

.wizard-form { background: white; border-radius: 12px; padding: 2rem; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.wizard-form h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
.subtitle { color: #64748b; margin-bottom: 1.5rem; }
.wizard-form label { display: flex; flex-direction: column; gap: 6px; margin-bottom: 1rem; font-weight: 500; font-size: 0.95rem; }
.wizard-form input, .wizard-form select { padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 1rem; }
.wizard-form button[type=submit] { background: #6366f1; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 1rem; cursor: pointer; margin-top: 0.5rem; }
.wizard-form button[type=submit]:hover { background: #4f46e5; }

.chat-container { display: flex; flex-direction: column; height: calc(100vh - 120px); background: white; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.08); overflow: hidden; }
.messages { flex: 1; overflow-y: auto; padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.msg { max-width: 80%; padding: 10px 14px; border-radius: 12px; font-size: 0.95rem; line-height: 1.5; white-space: pre-wrap; }
.msg.user { background: #6366f1; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
.msg.assistant { background: #f1f5f9; color: #1e293b; align-self: flex-start; border-bottom-left-radius: 4px; }
.spinner { padding: 0.75rem 1.5rem; color: #64748b; font-size: 0.9rem; font-style: italic; }
.hidden { display: none; }
.chat-input { display: flex; gap: 8px; padding: 1rem; border-top: 1px solid #e2e8f0; }
.chat-input input { flex: 1; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 1rem; outline: none; }
.chat-input input:focus { border-color: #6366f1; }
.chat-input button { background: #6366f1; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 1rem; }
.chat-input button:hover { background: #4f46e5; }
.finalise-bar { padding: 1rem; border-top: 1px solid #e2e8f0; text-align: center; }
.btn-primary { background: #10b981; color: white; border: none; padding: 12px 32px; border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 600; }
.btn-primary:hover { background: #059669; }
```

- [ ] **Step 6: Create `ui/static/app.js`**

```javascript
// --- Wizard Step 0: form submission ---
const startForm = document.getElementById('start-form');
if (startForm) {
  startForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = new FormData(startForm);
    await fetch('/wizard/start', { method: 'POST', body: data });
    location.reload();
  });
}

// --- Chat interface ---
const chatForm = document.getElementById('chat-form');
const messagesEl = document.getElementById('messages');
const spinner = document.getElementById('spinner');
const userInput = document.getElementById('user-input');

function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

if (chatForm) {
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;
    userInput.value = '';

    appendMessage('user', message);
    spinner.classList.remove('hidden');

    const assistantEl = appendMessage('assistant', '');
    let buffer = '';

    try {
      const resp = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') break;
            try {
              const parsed = JSON.parse(data);
              if (parsed.delta) {
                buffer += parsed.delta;
                assistantEl.textContent = buffer;
                messagesEl.scrollTop = messagesEl.scrollHeight;
              }
            } catch {}
          }
        }
      }
    } catch (err) {
      assistantEl.textContent = 'Something went wrong. Please try again.';
    } finally {
      spinner.classList.add('hidden');
    }
  });
}

// --- Wizard controls ---
async function finaliseSetup() {
  await fetch('/wizard/finalise', { method: 'POST' });
  location.href = '/';
}

async function resetWizard() {
  if (!confirm('Restart the setup wizard? Your ERPNext data will be preserved.')) return;
  await fetch('/wizard/reset', { method: 'POST' });
  location.href = '/';
}
```

- [ ] **Step 7: Smoke test — start the server and verify it loads**

```bash
# Create a minimal .env for testing
echo "ERPNEXT_URL=http://localhost:8000
ERPNEXT_API_KEY=test
ERPNEXT_API_SECRET=test
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen/qwen3.5-9b
FASTAPI_PORT=8080" > .env

uv run uvicorn main:app --host 127.0.0.1 --port 8080
```

Open `http://localhost:8080` in browser. Expected: wizard form renders without errors. Stop server with Ctrl+C.

- [ ] **Step 8: Commit**

```bash
git add main.py ui/
git commit -m "feat: FastAPI app, SSE chat endpoint, wizard and chat UI"
```

---

## Task 9: Installer

**Files:**
- Create: `installer.py`

- [ ] **Step 1: Create `installer.py`**

```python
#!/usr/bin/env python3
"""
SME Local AI Orchestration — Installer
Checks prerequisites, writes .env, sets up Python environment, starts server.
"""
import subprocess
import sys
import os
import webbrowser
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None  # Not yet installed — we'll check uv first


def print_step(n: int, text: str):
    print(f"\n[{n}] {text}")


def print_ok(text: str):
    print(f"    ✓ {text}")


def print_fail(text: str):
    print(f"    ✗ {text}")


def fail(message: str):
    print(f"\n❌  {message}")
    sys.exit(1)


def check_uv():
    print_step(1, "Checking uv is installed...")
    result = subprocess.run(["uv", "--version"], capture_output=True)
    if result.returncode != 0:
        print_fail("uv not found.")
        print("""
    Install uv with:
        curl -LsSf https://astral.sh/uv/install.sh | sh
    Then re-run this installer.
""")
        sys.exit(1)
    print_ok(f"uv found: {result.stdout.decode().strip()}")


def check_lm_studio():
    print_step(2, "Checking LM Studio is running...")
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=5)
        print_ok("LM Studio is running at http://127.0.0.1:1234")
    except Exception:
        print_fail("LM Studio not reachable at http://127.0.0.1:1234")
        print("""
    Please:
    1. Open LM Studio
    2. Load the 'qwen/qwen3.5-9b' model
    3. Start the local server (Server tab → Start Server)
    Then re-run this installer.
""")
        sys.exit(1)


def prompt_erpnext_url() -> str:
    print_step(3, "ERPNext URL")
    url = input("    Enter your ERPNext URL [http://localhost:8000]: ").strip()
    return url or "http://localhost:8000"


def check_erpnext(url: str):
    print_step(4, f"Checking ERPNext is reachable at {url}...")
    try:
        import urllib.request
        urllib.request.urlopen(f"{url}/api/method/ping", timeout=5)
        print_ok("ERPNext is running.")
    except Exception:
        print_fail(f"ERPNext not reachable at {url}")
        print(f"""
    Please make sure ERPNext is running and accessible at {url}.
    If you installed via bench: run 'bench start' in your frappe-bench directory.
    If you used Docker: make sure the containers are running.
    Then re-run this installer.
""")
        sys.exit(1)


def prompt_credentials() -> tuple[str, str]:
    print_step(5, "ERPNext API credentials")
    print("""
    To find your API key and secret in ERPNext:
    1. Log into ERPNext
    2. Go to Settings → My Profile (top right)
    3. Scroll to 'API Access'
    4. Click 'Generate Keys' if none exist
""")
    api_key = input("    Paste your API Key: ").strip()
    api_secret = input("    Paste your API Secret: ").strip()
    if not api_key or not api_secret:
        fail("API key and secret are required.")
    return api_key, api_secret


def write_env(erpnext_url: str, api_key: str, api_secret: str):
    print_step(6, "Writing .env configuration...")
    env_content = f"""ERPNEXT_URL={erpnext_url}
ERPNEXT_API_KEY={api_key}
ERPNEXT_API_SECRET={api_secret}
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen/qwen3.5-9b
FASTAPI_PORT=8080
"""
    Path(".env").write_text(env_content)
    # Ensure .gitignore includes .env
    gitignore = Path(".gitignore")
    if gitignore.exists() and ".env" not in gitignore.read_text():
        with gitignore.open("a") as f:
            f.write("\n.env\n")
    print_ok(".env written.")


def setup_venv():
    print_step(7, "Setting up Python environment with uv...")
    subprocess.run(["uv", "venv"], check=True)
    subprocess.run(["uv", "sync"], check=True)
    print_ok("Python environment ready.")


def start_server():
    print_step(8, "Starting the app server...")
    server_process = subprocess.Popen(
        ["uv", "run", "python", "main.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    if server_process.poll() is not None:
        fail("Server failed to start. Check that port 8080 is not in use.")
    print_ok("Server running at http://localhost:8080")
    return server_process


def main():
    print("\n=== SME Business Assistant — Setup ===\n")
    print("Platform:", sys.platform)
    if sys.platform.startswith("win"):
        fail("Windows is not supported in Phase 1. Please use Linux or macOS.")

    check_uv()
    check_lm_studio()
    erpnext_url = prompt_erpnext_url()
    check_erpnext(erpnext_url)
    api_key, api_secret = prompt_credentials()
    write_env(erpnext_url, api_key, api_secret)
    setup_venv()
    start_server()

    print("\n✅  Setup complete!\n")
    print("   Opening http://localhost:8080 in your browser...\n")
    webbrowser.open("http://localhost:8080")
    print("   The app will keep running in the background.")
    print("   To stop it, close this terminal.\n")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nStopping server...")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify installer is executable and runs correctly**

```bash
chmod +x installer.py
python installer.py --help 2>&1 || python installer.py
```

Expected: prints setup header, then checks for uv. If uv is installed, proceeds to LM Studio check.

- [ ] **Step 3: Commit**

```bash
git add installer.py
git commit -m "feat: installer — prereq checks, .env writer, server launcher"
```

---

## Task 10: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS. If any fail, fix before proceeding.

- [ ] **Step 2: Verify server starts cleanly**

With LM Studio and ERPNext running:
```bash
uv run python main.py
```
Open `http://localhost:8080`. Verify wizard form renders. Check `/health` endpoint returns status for both services.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verified full test suite passes"
```
