# Wizard Flow Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the blank-screen wizard and realign step-advance logic with the v3 design so the AI always speaks first and the user is never left guessing.

**Architecture:** Four independent tasks in order — add `get_greet_prompt`, fix `/chat` step-advance + `/wizard/finalise`, add `GET /wizard/greet`, update wizard template and JS. Each task produces a tested, committed change.

**Tech Stack:** FastAPI, Jinja2, SQLite (`db.session`), httpx (LM Studio client), pytest + pytest-asyncio + respx, vanilla JS

---

## File Map

| File | Role in this change |
|------|---------------------|
| `llm/prompts.py` | Add `get_greet_prompt(step, business_name, business_type, location)` |
| `main.py` | Fix `/chat` step-advance ordering; guard `/wizard/finalise`; add `GET /wizard/greet`; pass `step_name` to template |
| `ui/templates/wizard.html` | Add `id="wizard-chat"`; fix Finalise button condition; add step indicator; disable inputs |
| `ui/static/app.js` | Auto-greet on DOM load; handle `step_changed` SSE event |
| `tests/llm/test_prompts.py` | New — tests for `get_greet_prompt` |
| `tests/test_wizard_routes.py` | New — tests for `/wizard/greet`, `/chat` step-advance, `/wizard/finalise` guard |

---

## Task 1: Add `get_greet_prompt` to `llm/prompts.py`

**Files:**
- Modify: `llm/prompts.py`
- Create: `tests/llm/test_prompts.py`

- [ ] **Step 1: Write failing tests**

Create `tests/llm/test_prompts.py`:

```python
from llm.prompts import get_greet_prompt


def test_greet_prompt_step1_contains_data_decision_question():
    prompt = get_greet_prompt(1, "Bloom Flowers", "flower shop", "Manchester")
    assert "import" in prompt.lower() or "demo" in prompt.lower()
    assert "Bloom Flowers" in prompt


def test_greet_prompt_step2_contains_inventory_question():
    prompt = get_greet_prompt(2, "Bloom Flowers", "flower shop", "Manchester")
    assert "inventor" in prompt.lower() or "stock" in prompt.lower()
    assert "Bloom Flowers" in prompt


def test_greet_prompt_step3_contains_summary_instruction():
    prompt = get_greet_prompt(3, "Bloom Flowers", "flower shop", "Manchester")
    assert "summar" in prompt.lower() or "configured" in prompt.lower()
    assert "Bloom Flowers" in prompt
    assert "Finalise Setup" in prompt


def test_greet_prompt_unknown_step_raises():
    import pytest
    with pytest.raises(ValueError):
        get_greet_prompt(99, "X", "Y", "Z")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest tests/llm/test_prompts.py -v
```

Expected: `ImportError` or `AttributeError` — `get_greet_prompt` does not exist yet.

- [ ] **Step 3: Implement `get_greet_prompt` in `llm/prompts.py`**

Append to the bottom of `llm/prompts.py` (after the existing `get_ongoing_prompt` function):

```python
_GREET_PROMPTS = {
    1: (
        "You are helping a small business owner set up ERPNext. "
        "Their business is {business_name}, a {business_type} in {location}. "
        "Ask them ONE friendly question: do they have existing customer or product data "
        "they would like to import, or would they prefer to start with a demo setup? "
        "Ask nothing else."
    ),
    2: (
        "You are helping {business_name} (a {business_type} in {location}) set up ERPNext. "
        "Ask your first question to understand how their business operates. "
        "One question only. Start with inventory: do they manage stock, or do they work to order?"
    ),
    3: (
        "Summarise what has been configured for {business_name} based on the conversation "
        "history so far. Present it clearly in plain language — modules, data choices, tax, "
        "and any other details discussed. Then invite the user to change anything before "
        "finalising. End with exactly: "
        "'When you are happy with everything, click Finalise Setup below.'"
    ),
}


def get_greet_prompt(step: int, business_name: str, business_type: str, location: str) -> str:
    if step not in _GREET_PROMPTS:
        raise ValueError(f"No greet prompt for step {step}")
    return _GREET_PROMPTS[step].format(
        business_name=business_name,
        business_type=business_type,
        location=location,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest tests/llm/test_prompts.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/takosaga/Projects/build_local && git add llm/prompts.py tests/llm/test_prompts.py
git commit -m "feat: add get_greet_prompt for wizard step-specific opening messages"
```

---

## Task 2: Fix `/chat` step-advance and guard `/wizard/finalise`

**Files:**
- Modify: `main.py`
- Create: `tests/test_wizard_routes.py`

**Background:** The current `/chat` handler (line 90) calls `increment_questions_asked()` unconditionally for all setup-mode messages. This poisons the question counter before step 2 begins. The `/chat` step-advance check for step 2→3 (`current_step == 2`) was also unreachable because the step never reached 2. The `/wizard/finalise` endpoint has no step guard.

> **Important:** The unconditional `increment_questions_asked()` call at `main.py:90` is removed by replacing the entire `/chat` handler in Step 3. The new handler only calls `increment_questions_asked()` inside the `elif current_step == 2` guard — this is the fix. `wizard/flow.py` itself does not change; the function stays, only the call site moves.

- [ ] **Step 1: Write failing tests**

Create `tests/test_wizard_routes.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from main import app


@pytest.fixture
async def client():
    # Reset wizard state before each test so steps don't bleed across tests.
    from wizard.state import reset as reset_wizard
    reset_wizard()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _start_wizard(client):
    """Helper: submit the step-0 form to reach step 1."""
    await client.post("/wizard/start", data={
        "business_name": "Test Shop",
        "business_type": "retail",
        "location": "London",
        "employees": "2-5",
    })


# --- /chat step-advance tests ---

async def test_chat_at_step1_advances_to_step2_after_one_reply(client):
    await _start_wizard(client)
    with patch("main.run_tool_loop", return_value="Great choice!"):
        resp = await client.post("/chat", json={"message": "demo setup please"})
    assert resp.status_code == 200
    # Consume the SSE stream
    body = resp.text
    assert "step_changed" in body

    # State should now be step 2
    from wizard.state import get_state
    assert get_state().current_step == 2


async def test_chat_at_step1_resets_question_counter(client):
    await _start_wizard(client)
    with patch("main.run_tool_loop", return_value="OK"):
        await client.post("/chat", json={"message": "demo"})
    from wizard.state import get_state
    assert get_state().business_data.get("_questions_asked", 0) == 0


async def test_chat_at_step2_increments_question_counter(client):
    await _start_wizard(client)
    # Advance to step 2
    with patch("main.run_tool_loop", return_value="OK"):
        await client.post("/chat", json={"message": "demo"})
    # Now at step 2 — send a message
    with patch("main.run_tool_loop", return_value="Do you track stock?"):
        await client.post("/chat", json={"message": "yes we stock items"})
    from wizard.state import get_state
    assert get_state().business_data.get("_questions_asked", 0) == 1


async def test_chat_at_step1_does_not_increment_question_counter(client):
    await _start_wizard(client)
    # Manually set questions_asked to 3 to prove step-1 does NOT increment it
    from wizard.state import update_business_data
    update_business_data({"_questions_asked": 3})
    with patch("main.run_tool_loop", return_value="OK"):
        await client.post("/chat", json={"message": "demo"})
    from wizard.state import get_state
    # After step 1→2 advance, counter is reset to 0 (not incremented to 4)
    assert get_state().business_data.get("_questions_asked", 0) == 0


# --- /wizard/finalise guard ---

async def test_finalise_rejected_before_step3(client):
    await _start_wizard(client)
    # Still at step 1 — finalise should fail
    resp = await client.post("/wizard/finalise")
    assert resp.status_code == 400


async def test_finalise_accepted_at_step3(client):
    from wizard.state import advance_step
    await _start_wizard(client)
    advance_step()  # step 1→2
    advance_step()  # step 2→3
    resp = await client.post("/wizard/finalise")
    assert resp.status_code == 200
    from wizard.state import get_state
    assert get_state().is_complete is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest tests/test_wizard_routes.py -v
```

Expected: All tests FAIL (step advance not implemented, finalise has no guard).

- [ ] **Step 3: Rewrite the `/chat` handler and `/wizard/finalise` in `main.py`**

Replace the `/chat` handler (lines 67–117) with:

```python
@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty message")

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
    else:
        system_prompt = get_ongoing_prompt(
            business_name=state.business_data.get("name", "your business"),
            business_type=state.business_data.get("type", "business"),
        )
        tools = get_ongoing_tools()

    response_text = await asyncio.to_thread(
        run_tool_loop,
        messages=history,
        tools=tools,
        adapter=adapter,
        system_prompt=system_prompt,
    )

    save_message("assistant", response_text)

    # Step-advance checks — always run AFTER saving the assistant response.
    step_changed = False
    current_step = get_state().current_step

    if mode == "setup":
        if current_step == 1:
            # Step 1 → 2: advance after first user reply; reset counter and greeted flag.
            advance_step()
            update_business_data({"_questions_asked": 0, "_greeted_step": None})
            step_changed = True
        elif current_step == 2:
            # Step 2 → 3: advance after 5 questions.
            increment_questions_asked()
            if should_advance_from_info_step():
                advance_step()
                step_changed = True

    async def token_stream():
        for char in response_text:
            yield f"data: {json.dumps({'delta': char})}\n\n"
            await asyncio.sleep(0)
        if step_changed:
            yield f"data: {json.dumps({'step_changed': True})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")
```

Replace `/wizard/finalise` (lines 120–123) with:

```python
@app.post("/wizard/finalise")
async def wizard_finalise():
    state = get_state()
    if state.current_step < 3:
        raise HTTPException(status_code=400, detail="Setup not yet at review step.")
    mark_complete()
    return {"status": "ok"}
```

Also add the missing import at the top of `main.py` — `update_business_data` is already imported from `wizard.state`. Confirm `advance_step` and `update_business_data` are both in the import line:

```python
from wizard.state import get_state, update_business_data, mark_complete, reset, advance_step
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest tests/test_wizard_routes.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest -v
```

Expected: All existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/takosaga/Projects/build_local && git add main.py tests/test_wizard_routes.py
git commit -m "fix: step-advance logic in /chat — restrict counter to step 2, advance step 1→2 after first reply, guard /wizard/finalise"
```

---

## Task 3: Add `GET /wizard/greet` endpoint

**Files:**
- Modify: `main.py`
- Modify: `tests/test_wizard_routes.py`

**Background:** On page load, the frontend calls `GET /wizard/greet`. The endpoint generates the AI's opening message for the current step and streams it as SSE. It is idempotent — on page refresh it returns the cached last assistant message without re-running the LLM.

- [ ] **Step 1: Add failing tests to `tests/test_wizard_routes.py`**

Append to `tests/test_wizard_routes.py`:

```python
# --- /wizard/greet tests ---

async def test_greet_step1_streams_sse_and_saves_message(client):
    await _start_wizard(client)  # puts us at step 1
    with patch("main.run_tool_loop", return_value="Do you have existing data?"):
        resp = await client.get("/wizard/greet")
    assert resp.status_code == 200
    assert "Do you have existing data?" in resp.text
    assert "[DONE]" in resp.text

    from db.session import load_conversation
    history = load_conversation()
    assert any(m["role"] == "assistant" and "existing data" in m["content"] for m in history)


async def test_greet_idempotent_on_refresh(client):
    await _start_wizard(client)
    with patch("main.run_tool_loop", return_value="First greet") as mock_llm:
        await client.get("/wizard/greet")
        # Second call — LLM should NOT be called again
        resp = await client.get("/wizard/greet")
        assert mock_llm.call_count == 1

    assert "First greet" in resp.text


async def test_greet_out_of_range_step_returns_done_only(client):
    # Step 0 — no greet needed
    resp = await client.get("/wizard/greet")
    assert resp.status_code == 200
    assert "[DONE]" in resp.text
    # Should NOT call LLM
    from db.session import load_conversation
    assert load_conversation() == []


async def test_greet_step3_passes_full_history_to_llm(client):
    await _start_wizard(client)
    # Seed some history
    from db.session import save_message
    save_message("user", "we have existing data")
    save_message("assistant", "Great, I'll import it.")

    # Advance to step 3
    from wizard.state import advance_step
    advance_step()  # 1→2
    advance_step()  # 2→3

    captured_messages = []
    def capture_llm(messages, **kwargs):
        captured_messages.extend(messages)
        return "Here is your summary."

    with patch("main.run_tool_loop", side_effect=capture_llm):
        await client.get("/wizard/greet")

    # Full history was passed — captured_messages should include the seeded messages
    contents = [m.get("content", "") for m in captured_messages]
    assert any("existing data" in c for c in contents), "Step 3 greet must receive full conversation history"
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest tests/test_wizard_routes.py::test_greet_step1_streams_sse_and_saves_message tests/test_wizard_routes.py::test_greet_idempotent_on_refresh tests/test_wizard_routes.py::test_greet_out_of_range_step_returns_done_only -v
```

Expected: FAIL — `GET /wizard/greet` does not exist.

- [ ] **Step 3: Add `GET /wizard/greet` to `main.py`**

Add these imports at the top of `main.py` (alongside existing LLM imports):

```python
from llm.prompts import get_setup_prompt, get_ongoing_prompt, get_greet_prompt
```

Add the endpoint after the existing `/wizard/start` route:

```python
_STEP_NAMES = {1: "Data Decision", 2: "Gathering Information", 3: "Review"}


@app.get("/wizard/greet")
async def wizard_greet():
    state = get_state()
    current_step = state.current_step

    # Out-of-range: return empty stream
    if current_step not in (1, 2, 3):
        async def empty_stream():
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    # Idempotency: if already greeted for this step, replay last assistant message
    greeted_step = state.business_data.get("_greeted_step")
    if greeted_step == current_step:
        history = load_conversation(limit=40)
        cached = next(
            (m["content"] for m in reversed(history) if m["role"] == "assistant"),
            ""
        )
        async def cached_stream():
            for char in cached:
                yield f"data: {json.dumps({'delta': char})}\n\n"
                await asyncio.sleep(0)
            yield "data: [DONE]\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # Fresh greet: call LLM
    greet_prompt = get_greet_prompt(
        step=current_step,
        business_name=state.business_data.get("name", "your business"),
        business_type=state.business_data.get("type", "business"),
        location=state.business_data.get("location", ""),
    )
    # Pass full history for step 3 (summary needs context); empty list for steps 1 and 2
    history = load_conversation(limit=40) if current_step == 3 else []
    adapter = ERPNextAdapter()

    response_text = await asyncio.to_thread(
        run_tool_loop,
        messages=history,
        tools=[],
        adapter=adapter,
        system_prompt=greet_prompt,
    )

    save_message("assistant", response_text)
    update_business_data({"_greeted_step": current_step})

    async def greet_stream():
        for char in response_text:
            yield f"data: {json.dumps({'delta': char})}\n\n"
            await asyncio.sleep(0)
        yield "data: [DONE]\n\n"

    return StreamingResponse(greet_stream(), media_type="text/event-stream")
```

Also update the `GET /` route to pass `step_name` to the wizard template:

```python
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    state = get_state()
    if state.is_complete:
        return templates.TemplateResponse(request, "chat.html", {
            "business_name": state.business_data.get("name", "Your Business"),
        })
    step_names = {1: "Data Decision", 2: "Gathering Information", 3: "Review"}
    return templates.TemplateResponse(request, "wizard.html", {
        "step": state.current_step,
        "business_data": state.business_data,
        "step_name": step_names.get(state.current_step, ""),
    })
```

- [ ] **Step 4: Run greet tests to verify they pass**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest tests/test_wizard_routes.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/takosaga/Projects/build_local && git add main.py tests/test_wizard_routes.py
git commit -m "feat: add GET /wizard/greet — idempotent SSE greeting per wizard step"
```

---

## Task 4: Update `wizard.html` — step indicator, id, disabled inputs, finalise fix

**Files:**
- Modify: `ui/templates/wizard.html`

No automated tests for template changes — verify manually by running the app. The changes are mechanical and low-risk.

- [ ] **Step 1: Apply all four changes to `wizard.html`**

Replace the full content of `ui/templates/wizard.html` with:

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
<div class="chat-container" id="wizard-chat">
  <p class="step-indicator">Step {{ step }} of 3 — {{ step_name }}</p>
  <div id="messages" class="messages"></div>
  <div id="spinner" class="spinner hidden">AI is thinking…</div>
  <form id="chat-form" class="chat-input">
    <input type="text" id="user-input" placeholder="Type your reply…" autocomplete="off" disabled>
    <button type="submit" disabled>Send</button>
  </form>
  {% if step == 3 %}
  <div class="finalise-bar">
    <button onclick="finaliseSetup()" class="btn-primary">✅ Finalise Setup</button>
  </div>
  {% endif %}
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
cd /home/takosaga/Projects/build_local && git add ui/templates/wizard.html
git commit -m "feat: wizard.html — step indicator, id for greet scoping, disabled inputs, fix finalise condition"
```

---

## Task 5: Update `app.js` — auto-greet on load and `step_changed` handling

**Files:**
- Modify: `ui/static/app.js`

No automated tests — JS is tested manually. The changes are additive and isolated to the wizard flow.

- [ ] **Step 1: Rewrite `app.js` with greet and step_changed logic**

Replace the full contents of `ui/static/app.js` with:

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

// --- Chat interface helpers ---
const messagesEl = document.getElementById('messages');
const spinner = document.getElementById('spinner');
const userInput = document.getElementById('user-input');
const sendButton = document.querySelector('#chat-form button[type="submit"]');

function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

async function streamSSE(url, method, body, onDelta, onDone) {
  // Shared SSE streaming logic used by both greet and chat.
  // Returns true if a step_changed event was seen.
  let stepChanged = false;
  const opts = { method };
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }

  const resp = await fetch(url, opts);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (data === '[DONE]') break;
      try {
        const parsed = JSON.parse(data);
        if (parsed.delta) onDelta(parsed.delta);
        if (parsed.step_changed) stepChanged = true;
      } catch {}
    }
  }

  onDone();
  return stepChanged;
}

// --- Auto-greet on wizard chat pages ---
const wizardChat = document.getElementById('wizard-chat');
if (wizardChat) {
  (async () => {
    const assistantEl = appendMessage('assistant', '');
    let buffer = '';

    try {
      const stepChanged = await streamSSE(
        '/wizard/greet', 'GET', null,
        (delta) => {
          buffer += delta;
          assistantEl.textContent = buffer;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        },
        () => {
          if (userInput) userInput.disabled = false;
          if (sendButton) sendButton.disabled = false;
        }
      );
      if (stepChanged) {
        location.reload();
      }
    } catch {
      assistantEl.textContent = 'Could not connect to the assistant. Please refresh.';
      if (userInput) userInput.disabled = false;
      if (sendButton) sendButton.disabled = false;
    }
  })();
}

// --- Chat form submission ---
const chatForm = document.getElementById('chat-form');
if (chatForm) {
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;
    userInput.value = '';
    userInput.disabled = true;
    if (sendButton) sendButton.disabled = true;

    appendMessage('user', message);
    spinner.classList.remove('hidden');

    const assistantEl = appendMessage('assistant', '');
    let buffer = '';

    try {
      const stepChanged = await streamSSE(
        '/chat', 'POST', { message },
        (delta) => {
          buffer += delta;
          assistantEl.textContent = buffer;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        },
        () => {
          spinner.classList.add('hidden');
          userInput.disabled = false;
          if (sendButton) sendButton.disabled = false;
        }
      );
      if (stepChanged) {
        location.reload();
      }
    } catch {
      assistantEl.textContent = 'Something went wrong. Please try again.';
      spinner.classList.add('hidden');
      userInput.disabled = false;
      if (sendButton) sendButton.disabled = false;
    }
  });
}

// --- Wizard controls ---
async function finaliseSetup() {
  const resp = await fetch('/wizard/finalise', { method: 'POST' });
  if (resp.ok) {
    location.href = '/';
  } else {
    alert('Setup is not ready to finalise yet.');
  }
}

async function resetWizard() {
  if (!confirm('Restart the setup wizard? Your ERPNext data will be preserved.')) return;
  await fetch('/wizard/reset', { method: 'POST' });
  location.href = '/';
}
```

- [ ] **Step 2: Run full test suite one final time**

```bash
cd /home/takosaga/Projects/build_local && uv run pytest -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/build_local && git add ui/static/app.js
git commit -m "feat: app.js — auto-greet on wizard load, step_changed reload, shared streamSSE helper"
```

---

## Manual Smoke Test

After all tasks are complete, verify the full flow:

1. `uv run python main.py` (ensure LM Studio and ERPNext are running, or stub them)
2. Open `http://localhost:8080`
3. Fill in Step 0 form → click Continue. Confirm: page reloads and AI sends the data-decision question immediately. Input is disabled until AI finishes.
4. Answer the question. Confirm: page reloads, "Step 2 of 3 — Gathering Information" shown, AI asks inventory question.
5. Answer 5 times. Confirm: page reloads to Review step, AI presents a summary and prompts to finalise.
6. Click "Finalise Setup". Confirm: redirects to the ongoing chat page.
