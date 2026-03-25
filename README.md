# SME Business Assistant

A local AI assistant that helps small business owners set up and use ERPNext using plain language. Everything runs on your machine — no cloud required.

You interact through a browser chat interface. A local LLM understands your instructions and carries them out in ERPNext on your behalf.

**Supported platforms:** Linux, macOS

---

## Prerequisites

Before running the installer, you need three things already installed and running:

1. **[uv](https://docs.astral.sh/uv/)** — Python environment manager
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **[LM Studio](https://lmstudio.ai/)** with `qwen/qwen3.5-9b` loaded and the local server started
   - Open LM Studio → load `qwen/qwen3.5-9b` → Server tab → Start Server

3. **ERPNext v15** running locally (via [bench](https://frappeframework.com/docs/user/en/bench) or Docker) and accessible at `http://localhost:8000`

   **Docker quick start:**
   ```bash
   docker compose -f pwd.yml up -d
   ```
   Wait for ERPNext to be ready, then log in at `http://localhost:8000` with `Administrator` / `admin`.
   Generate API keys before running the installer.

**Minimum hardware:** 16 GB RAM, modern CPU (Apple Silicon recommended on macOS)

---

## Quick Start

```bash
python installer.py
```

The installer will:
1. Verify uv, LM Studio, and ERPNext are reachable
2. Ask for your ERPNext URL and API credentials
3. Set up the Python environment
4. Start the server and open `http://localhost:8080` in your browser

### Finding your ERPNext API credentials

1. Log into ERPNext
2. Top right → My Profile → Settings
3. Scroll to **API Access** → click **Generate Keys**
4. Copy the API Key and API Secret when prompted by the installer

---

## First Run

The app opens a **setup wizard** that walks you through configuring ERPNext for your business:

1. **Business basics** — name, type, location, number of employees
2. **Data decision** — import existing data from CSV, or start with a demo setup
3. **Business questions** — the AI asks a few follow-up questions (max 5)
4. **Review** — the AI summarises everything it will configure; you can request changes
5. **Finalise** — click Finalise Setup and the AI applies the configuration

After setup, you're dropped into the ongoing chat assistant where you can query your data and perform actions in plain language.

---

## Running Without the Installer

If you already have a `.env` file configured:

```bash
uv sync
uv run python main.py
```

Then open `http://localhost:8080`.

### `.env` format

```
ERPNEXT_URL=http://localhost:8000
ERPNEXT_API_KEY=your_key
ERPNEXT_API_SECRET=your_secret
LM_STUDIO_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen/qwen3.5-9b
FASTAPI_PORT=8080
```

---

## Development

```bash
uv sync --all-groups   # installs dev dependencies too
uv run pytest tests/   # run the test suite
```

---

## Architecture

```
Browser (UI)
    ⇅
FastAPI (127.0.0.1:8080)  ⇄  LM Studio / Qwen 3.5-9B (127.0.0.1:1234)
                           ⇄  ERPNext v15 (Frappe REST API)
```

The server binds to `127.0.0.1` only and is not accessible to other devices on the network.
