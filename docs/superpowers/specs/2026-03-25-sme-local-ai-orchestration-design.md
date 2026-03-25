# SME Local AI Orchestration — Design Spec
Date: 2026-03-25

## Overview

A local AI orchestration layer that helps small and medium enterprise (SME) owners set up and interact with ERPNext using plain language. The system runs entirely on the business owner's machine — no cloud, no technical knowledge required.

The business owner interacts through a local web UI (served by a Python FastAPI backend). A local LLM (Qwen 3.5-9B via LM Studio) understands their instructions and executes predefined tool functions that call the ERPNext REST API.

---

## Scope

**In scope (Phase 1):**
- In-store / local business operations only
- Linux and macOS only
- ERPNext as the ERP/CRM system
- Setup wizard (one-time) + ongoing chat assistant
- Predefined tool calling (no dynamic API generation)

**Out of scope (future phases):**
- Online/e-commerce integrations
- Windows support
- RAG / vector search over business data
- Multi-user / multi-device access

---

## Architecture

Five components, all running on the user's machine:

```
Browser (UI)
    ⇅
FastAPI Backend  ⇄  LM Studio (Qwen 3.5-9B @ http://127.0.0.1:1234)
                 ⇄  ERPNext (Frappe REST API, local instance)
```

**Request cycle:**
1. User types message in browser chat
2. FastAPI adds message to conversation history
3. History + tool definitions sent to LM Studio (OpenAI-compatible API)
4. LM Studio returns text response OR one or more tool calls
5. If tool calls: FastAPI executes them against ERPNext REST API
6. Tool results appended to history, sent back to LM Studio
7. LM Studio generates final natural language response
8. FastAPI streams response to browser

---

## Setup Wizard Flow

A one-time flow the business owner runs when first launching the app.

### Step 1 — Simple Form
Collects business basics: name, type, location, number of employees.

### Step 2 — Data Decision (AI Chat)
AI asks: *"Do you have existing business data to import, or would you like to start with a demo setup?"*
- **Import path:** AI guides user through CSV upload, maps columns, imports customers/items/suppliers
- **Demo path:** AI creates sample data and configures ERPNext modules automatically

### Step 3 — Additional Info Gathering (AI Chat)
AI asks follow-up questions one at a time, tailored to business type. Examples:
- Do you manage stock/inventory, or is everything made to order?
- Do you need to track suppliers and purchase orders?
- How many staff members handle sales?

Scoped to local in-store operations only. AI stops asking when it has sufficient information to configure ERPNext.

### Step 4 — Review Before Finalising
AI presents a summary of everything it will configure:
- Modules to enable/disable
- Business profile settings
- Sample or imported data summary
- Tax rate and fiscal year

Business owner can request changes in plain language ("change the tax rate to 10%", "add the HR module") before committing. AI adjusts and re-presents the summary.

### Step 5 — Finalise Setup
User clicks **Finalise Setup**. AI applies all configuration via tool calls.

Post-finalise, the UI confirms setup is complete and offers three options:
- **Change a setting** — chat with AI to adjust anything
- **Restart Setup Wizard** — start over completely
- **Start chatting** — proceed to the ongoing assistant

The Restart Setup Wizard option is also accessible at any time from the settings menu.

---

## Ongoing Chat Assistant

After setup, the business owner interacts with the AI in a persistent chat interface to query data and perform actions.

**Example queries:**
- "What were my top-selling items last month?"
- "Who are my best customers?"
- "How much stock do I have of roses?"

**Example actions:**
- "Create an invoice for Sarah Jones for 3 bouquets at £25 each"
- "Add a new supplier called City Wholesale"
- "Draft an email to my customers about our Easter sale"

---

## Tool Library

### Setup Tools
| Tool | Purpose |
|---|---|
| `create_company` | Set company name, currency, fiscal year |
| `enable_modules` | Enable/disable ERPNext modules |
| `setup_chart_of_accounts` | Configure accounts by business type |
| `create_item` / `create_items_bulk` | Create product/service items |
| `create_customer` / `create_customers_bulk` | Create customer records |
| `create_supplier` | Create supplier records |
| `import_csv` | Import existing data from uploaded spreadsheet |
| `set_tax_rate` | Set default tax rate |

### Query Tools (read-only)
| Tool | Purpose |
|---|---|
| `get_sales_summary` | Sales totals for a date range |
| `get_top_customers` | Best customers by spend |
| `get_inventory_status` | Stock levels (all items or specific item) |
| `get_low_stock_items` | Items below a threshold |
| `get_customer_history` | Past orders for a customer |

### Action Tools (write)
| Tool | Purpose |
|---|---|
| `create_invoice` | Create a sales invoice |
| `create_purchase_order` | Create a purchase order |
| `update_item_price` | Change a product price |
| `draft_content` | LLM generates emails/descriptions (no ERPNext call) |

---

## Error Handling

| Failure | User-facing message |
|---|---|
| LM Studio not running | "The AI model isn't running. Please open LM Studio and load the model." |
| ERPNext not reachable | "Can't reach your business data. Is ERPNext running?" |
| Tool call fails | AI receives the error and explains it in plain language — no raw stack traces |
| CSV import has bad rows | Shows which rows failed; user can skip or fix and retry |
| Setup interrupted | Wizard resumes from last completed step on next open |

---

## Project Structure

```
build_local/
├── pyproject.toml            # Dependencies (uv reads this)
├── installer.py              # Checks uv, creates venv, installs deps, starts server, opens browser
├── main.py                   # FastAPI app — routes, startup
├── config.py                 # LM Studio URL, ERPNext URL, model name
├── llm/
│   ├── client.py             # LM Studio API calls, tool call loop
│   ├── tools.py              # Tool definitions (JSON schema sent to LLM)
│   └── prompts.py            # System prompts (setup mode vs. ongoing mode)
├── erpnext/
│   ├── adapter.py            # ERPNext REST API wrapper + auth
│   ├── setup_tools.py        # Setup-phase tool functions
│   └── ongoing_tools.py      # Query + action tool functions
├── wizard/
│   ├── state.py              # Wizard state machine (which step, what's completed)
│   └── flow.py               # Step logic + resume-on-restart
├── db/
│   └── session.py            # SQLite — conversation history + setup state
└── ui/
    ├── static/               # CSS, JS
    └── templates/
        ├── wizard.html       # Setup wizard UI
        └── chat.html         # Ongoing chat interface
```

---

## Runtime Dependencies

| Dependency | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Web server and API |
| `httpx` | Async HTTP calls to LM Studio and ERPNext |
| `jinja2` | HTML template rendering |
| `python-multipart` | CSV file upload handling |
| `sqlite3` (stdlib) | Conversation and state persistence |

---

## Installer Behaviour

`installer.py` runs once and:
1. Checks that `uv` is installed — prints install instructions if not (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
2. Checks that LM Studio is running at `http://127.0.0.1:1234`
3. Checks that ERPNext is reachable
4. Runs `uv venv` + `uv pip install` to set up the Python environment
5. Starts the FastAPI server
6. Opens `http://localhost:8000` in the default browser

**Platform support:** Linux and macOS only (Phase 1).

---

## LLM Configuration

- **Model:** `qwen/qwen3.5-9b` via LM Studio
- **Endpoint:** `http://127.0.0.1:1234` (OpenAI-compatible)
- **Context window:** 131,072 tokens
- **Tool calling:** Predefined JSON schema tools passed in each request
- **System prompt:** Switches between setup mode and ongoing assistant mode depending on wizard state

---

## Testing Approach

- Tool functions unit-tested with a mocked ERPNext adapter (no live instance required)
- Wizard state machine tested in isolation — verify each step transitions correctly
- Full end-to-end tested manually against a local ERPNext dev instance
