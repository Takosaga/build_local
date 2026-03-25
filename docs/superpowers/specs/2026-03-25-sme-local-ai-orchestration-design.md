# SME Local AI Orchestration — Design Spec
Date: 2026-03-25

## Overview

A local AI orchestration layer that helps small and medium enterprise (SME) owners set up and interact with ERPNext using plain language. The system runs entirely on the business owner's machine — no cloud required.

The business owner interacts through a local web UI (served by a Python FastAPI backend). A local LLM (Qwen 3.5-9B via LM Studio) understands their instructions and executes predefined tool functions that call the ERPNext REST API.

**Prerequisites (manual, before first run):**
- LM Studio installed and running with `qwen/qwen3.5-9b` loaded
- ERPNext v15 installed locally (via bench or Docker) and accessible
- Minimum hardware: 16 GB RAM, modern CPU (Apple Silicon recommended on macOS)

The installer verifies these prerequisites are reachable and gives clear instructions if they are not. It does not install LM Studio or ERPNext itself.

---

## Scope

**In scope (Phase 1):**
- In-store / local business operations only
- Linux and macOS only
- ERPNext v15 as the ERP/CRM system
- Setup wizard (one-time) + ongoing chat assistant
- Predefined tool calling (no dynamic API generation)

**Out of scope (future phases):**
- Online/e-commerce integrations
- Windows support
- RAG / vector search over business data
- Multi-user / multi-device access
- Automated ERPNext or LM Studio installation

---

## Architecture

Five components, all running on the user's machine:

```
Browser (UI)
    ⇅
FastAPI Backend  ⇄  LM Studio (Qwen 3.5-9B @ http://127.0.0.1:1234)
                 ⇄  ERPNext v15 (Frappe REST API, local instance)
```

FastAPI binds to `127.0.0.1` only — never `0.0.0.0`. The UI and API are not accessible to other devices on the network.

**Request cycle:**
1. User types message in browser chat
2. FastAPI adds message to conversation history
3. History + tool definitions sent to LM Studio (OpenAI-compatible API)
4. LM Studio returns text response OR one or more tool calls
5. If tool calls: FastAPI validates the tool call JSON schema, then executes against ERPNext REST API
6. If LLM output is malformed: retry once with a correction prompt; if still malformed, return a plain-language error to the user
7. Tool results appended to history, sent back to LM Studio
8. LM Studio generates final natural language response
9. FastAPI streams the final response token-by-token to the browser via Server-Sent Events (SSE)

**Multi-step tool calls:** The orchestration layer loops autonomously (steps 4–8) until the LLM produces a final text response. The tool call loop runs synchronously — SSE streaming does not begin until the loop exits and a final text response is ready. During the loop, the browser displays a spinner. Once the loop exits, tokens are streamed one-by-one via SSE to the browser.

**Context window management:** Conversation history is sent as a sliding window — the system prompt is always included, and up to the last 40 messages are kept. Older messages are silently dropped. The 131,072-token context window is not expected to be reached in normal use.

---

## Configuration & Credential Storage

Runtime settings are stored in a `.env` file in the project root, written by the installer during first run. It is never committed to version control (`.gitignore` entry added by installer).

```
ERPNEXT_URL=http://localhost:8000
ERPNEXT_API_KEY=<api_key>
ERPNEXT_API_SECRET=<api_secret>
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen/qwen3.5-9b
FASTAPI_PORT=8080
```

ERPNext authentication uses **API key + secret** (Frappe's token-based auth). During setup, the installer prompts the user to paste their ERPNext API key and secret (with step-by-step instructions for where to find them in the ERPNext UI). These are written to `.env` and never stored elsewhere.

`config.py` loads all settings from `.env` via `python-dotenv` at startup.

---

## Setup Wizard Flow

A one-time flow on first launch. Progress is persisted to SQLite after each step completes — the wizard resumes from the last completed step if interrupted.

### Step 1 — Simple Form
Collects business basics: name, type, location, number of employees.

### Step 2 — Data Decision (AI Chat)
AI asks: *"Do you have existing business data to import, or would you like to start with a demo setup?"*
- **Import path:** AI guides user through CSV upload. Validates columns before import. Shows which rows fail and lets the user skip or fix them. Partial imports are committed row-by-row; failed rows are skipped and logged.
- **Demo path:** AI creates sample data and configures ERPNext modules automatically.

### Step 3 — Additional Info Gathering (AI Chat)
AI asks follow-up questions one at a time, tailored to business type. Maximum 5 questions. Examples:
- Do you manage stock/inventory, or is everything made to order?
- Do you need to track suppliers and purchase orders?
- How many staff members handle sales?

After 5 questions (or sooner if sufficient), the AI moves to Step 4 automatically.

### Step 4 — Review Before Finalising
AI presents a summary of everything it will configure:
- Modules to enable/disable
- Business profile settings
- Sample or imported data summary
- Tax rate and fiscal year

Business owner can request changes in plain language before committing. AI adjusts and re-presents the summary.

### Step 5 — Finalise Setup
User clicks **Finalise Setup**. AI applies all configuration via tool calls sequentially.

Tool calls during finalisation are not transactional — if one fails, already-applied calls are not rolled back. The wizard records which tool calls succeeded and, on re-run, skips already-completed steps. A failed finalisation can be retried safely.

Post-finalise, the UI confirms setup is complete and offers three options:
- **Change a setting** — chat with AI to adjust anything
- **Restart Setup Wizard** — reconfigures modules and settings; existing ERPNext data (customers, items, etc.) is preserved unless the user explicitly asks to clear it
- **Start chatting** — proceed to the ongoing assistant

The Restart Setup Wizard option is accessible at any time from the settings menu.

---

## Ongoing Chat Assistant

After setup, the business owner interacts with the AI in a persistent chat interface to query data and perform actions.

**Write action confirmation:** Before executing any write-action tool (`create_invoice`, `create_purchase_order`, `update_item_price`), the AI presents a plain-language summary of the action and asks for confirmation. Example: *"I'll create an invoice for Sarah Jones for 3 bouquets at £25 each — total £75. Shall I go ahead?"* The action is only executed after the user confirms. If the user declines, the AI acknowledges ("No problem, I've cancelled that.") and returns to the normal chat flow — the action is dropped and not retried unless the user requests it again.

**Conversation persistence:** Full conversation history is written to SQLite after every message and reloaded on app restart.

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

### Action Tools (write — require user confirmation)
| Tool | Purpose |
|---|---|
| `create_invoice` | Create a sales invoice |
| `create_purchase_order` | Create a purchase order |
| `update_item_price` | Change a product price |

### Content Tools (read-only — no confirmation required)
| Tool | Purpose |
|---|---|
| `draft_content` | LLM generates email copy, product descriptions, announcements — returns text only, no ERPNext write |

---

## Error Handling

| Failure | Behaviour |
|---|---|
| LM Studio not running | "The AI model isn't running. Please open LM Studio and load the model." |
| ERPNext not reachable | "Can't reach your business data. Is ERPNext running?" |
| Malformed tool call output | Retry once with correction prompt; if still malformed, show plain-language error |
| Tool call fails (ERPNext error) | AI receives the error and explains it in plain language — no raw stack traces shown |
| CSV import bad rows | Shows which rows failed; user can skip or fix and retry |
| Setup interrupted | Wizard resumes from last completed step on next open |
| Write action tool fails after confirmation | AI explains what failed and offers to retry |

---

## Project Structure

```
build_local/
├── .env                      # Runtime config + ERPNext credentials (never committed)
├── .gitignore                # Includes .env, .venv, __pycache__, data/
├── data/
│   └── app.db                # SQLite database — conversation history + wizard state (never committed)
├── pyproject.toml            # Dependencies (uv reads this)
├── installer.py              # Checks prereqs, writes .env, creates venv, starts server, opens browser
├── main.py                   # FastAPI app — routes, SSE streaming, startup
├── config.py                 # Loads settings from .env via python-dotenv
├── llm/
│   ├── client.py             # LM Studio API calls, tool call loop, SSE streaming
│   ├── tools.py              # Tool definitions (JSON schema sent to LLM)
│   └── prompts.py            # System prompts (setup mode vs. ongoing mode)
├── erpnext/
│   ├── adapter.py            # ERPNext REST API wrapper, API key/secret auth
│   ├── setup_tools.py        # Setup-phase tool functions
│   └── ongoing_tools.py      # Query + action tool functions
├── wizard/
│   ├── state.py              # Wizard state machine, SQLite-backed step tracking
│   └── flow.py               # Step logic, resume-on-restart, max-question enforcement
├── db/
│   └── session.py            # SQLite — conversation history + wizard state persistence
└── ui/
    ├── static/               # CSS, JS (SSE client)
    └── templates/
        ├── wizard.html       # Setup wizard UI
        └── chat.html         # Ongoing chat interface
```

---

## Runtime Dependencies

| Dependency | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Web server, API, SSE streaming |
| `httpx` | Async HTTP to LM Studio and ERPNext |
| `jinja2` | HTML template rendering |
| `python-multipart` | CSV file upload handling |
| `python-dotenv` | Load `.env` config at startup |
| `sqlite3` (stdlib) | Conversation and wizard state persistence |

---

## Installer Behaviour

`installer.py` runs once and:
1. Checks `uv` is installed — prints install command if not: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Checks LM Studio is running at `http://127.0.0.1:1234` — prints instructions if not
3. Prompts user for their ERPNext URL (default: `http://localhost:8000`)
4. Checks ERPNext is reachable by calling `GET <url>/api/method/ping` — prints instructions if unreachable
5. Prompts user for ERPNext API key and secret (with step-by-step instructions for finding them in the ERPNext UI)
6. Writes `.env` file with all runtime config
6. Runs `uv venv` + `uv pip install` to set up the Python environment
7. Starts the FastAPI server on `127.0.0.1:8080`
8. Opens `http://localhost:8080` in the default browser

**Platform support:** Linux and macOS only (Phase 1).

---

## LLM Configuration

- **Model:** `qwen/qwen3.5-9b` via LM Studio
- **Endpoint:** `http://127.0.0.1:1234` (OpenAI-compatible)
- **Context window:** 131,072 tokens — sliding window of last 40 messages used in practice
- **Tool calling:** Predefined JSON schema tools passed in each request; output validated before execution
- **System prompt:** Switches between setup mode and ongoing assistant mode based on wizard completion state

---

## Testing Approach

- Tool functions unit-tested with a mocked ERPNext adapter (no live instance required)
- Wizard state machine tested in isolation — verify each step transitions and persists correctly, including resume-after-interrupt scenarios
- Tool call validation tested with intentionally malformed LLM output
- Full end-to-end tested manually against a local ERPNext v15 dev instance
